"""Spot-check: re-derive numbers from the source files without the code of tools/build_data.py, and compare them with what the
page's data files and the built page hold.

    python -B tools/check_numbers.py --repo <statescope checkout> --result <folder with result.json and result.safetensors>
                                     --hf-home <Hugging Face cache with the Qwen3.5-0.8B tokenizer>

Shares are recomputed from the per-item margins with the formula and the bootstrap of demo/line_count.py's docstring and share().
Exit status 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import torch
from safetensors.torch import load_file

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL = "release/qwen35-08b-v2"
results: list[bool] = []


def check(name: str, derived, held) -> None:
    ok = derived == held
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: from the sources {derived!r}; in the site's files {held!r}")


def site(name: str) -> dict:
    with open(os.path.join(HERE, "data", name)) as f:
        return json.load(f)


def f3(x: float) -> str:
    s = f"{x:.3f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def f2(x: float) -> str:
    s = f"{x:.2f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def share(m_clean, m_patched, m_corrupt, n_boot=1000):
    num, den = m_clean - m_patched, m_clean - m_corrupt
    draw = torch.randint(0, len(num), (n_boot, len(num)), generator=torch.Generator().manual_seed(0))
    ratio = num[draw].mean(1) / den[draw].mean(1)
    return [float(num.mean() / den.mean()), float(ratio.quantile(0.025)), float(ratio.quantile(0.975))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--hf-home", required=True)
    args = ap.parse_args()
    torch.set_num_threads(4)
    repo = lambda rel: os.path.join(args.repo, rel)
    with open(repo(f"{REL}/reader_fvu.json")) as f:
        fvu = json.load(f)["layers"]
    with open(repo(f"{REL}/MANIFEST.json")) as f:
        manifest = json.load(f)["layers"]
    with open(repo(f"{REL}/MODEL_CARD.md")) as f:
        card = f.read()
    with open(repo("README.md")) as f:
        readme = f.read()
    with open(os.path.join(args.result, "result.json")) as f:
        result = json.load(f)
    T = load_file(os.path.join(args.result, "result.safetensors"))
    layers, splice, demo, facts = site("layers.json"), site("splice.json"), site("demo.json"), site("facts.json")["facts"]
    with open(os.path.join(HERE, "index.html")) as f:
        page = f.read()

    # 1-5: numbers per layer
    check("1. state FVU, resid_mid, layer 9, position 0 dropped", f"{fvu['9']['resid_mid.9']['position_0_dropped']:.4f}", layers["rows"][9]["dropped"]["state_mid"])
    check("2. state FVU, resid_post, layer 17, position 0 included", f"{fvu['17']['resid_post.17']['with_position_0']:.4f}", layers["rows"][17]["with_p0"]["state_post"])
    check("3. MLP FVU, layer 23, position 0 dropped", f"{fvu['23']['mlp']['position_0_dropped']:.4f}", layers["rows"][23]["dropped"]["mlp"])
    check("4. MLP transforms alive, layer 14", f"{manifest['14']['mlp']['alive']} of {manifest['14']['mlp']['transforms']}", layers["rows"][14]["alive_text"])
    check("5. MLP transforms on per token, layer 23, and MLP FVU recorded at training, layer 2",
          (f"{manifest['23']['mlp']['heldout_l0']:.1f}", f"{manifest['2']['mlp']['heldout_fvu']:.4f}"),
          (layers["rows"][23]["on_per_token"], layers["rows"][2]["mlp_train"]))
    row = re.search(r"^\| 9 \| (\S+) \| (\S+) \| (\S+) \|", card, flags=re.M).groups()
    check("6. the card's table row of layer 9 (three FVU columns) is in the built page's table",
          True, "<tr><td>9</td>" + "".join(f"<td>{v}</td>" for v in row) in page)

    # 7: spliced-in loss, the card's strings
    row21 = re.search(r"^\| 21 \| (\+[\d.]+) \| (\+[\d.]+) \|$", card, flags=re.M).groups()
    check("7. spliced-in loss, layer 21, both columns", row21, (splice["rows"][21]["state"], splice["rows"][21]["mlp"]))

    # 8-10: shares recomputed from the per-item margins
    def recomputed(cell: str, arm: str, half: str):
        m_c, m_x, m = T[f"margin/{cell}/m_c"], T[f"margin/{cell}/m_x"], T[f"margin/{cell}/{arm}"]
        index = torch.arange(len(m_c))
        sel = {"all": index >= 0, "even": index % 2 == 0, "odd": index % 2 == 1}[half]
        return [f3(v) for v in share(m_c[sel], m[sel], m_x[sel])]

    for n, (cell, arm, half) in enumerate((("count:100", "l9/t1749", "even"), ("width:100", "head_o", "odd"), ("count:60", "link/mix/g4885/F2", "all")), start=8):
        e = demo["shares"][cell][arm][half]
        check(f"{n}. share and interval recomputed from margins: {cell}, {arm}, {half}", recomputed(cell, arm, half), [e["s"], e["slo"], e["shi"]])
    wrong = 0
    count = 0
    for cell in demo["shares"]:
        for arm in demo["shares"][cell]:
            for half in ("all", "even", "odd"):
                e = demo["shares"][cell][arm][half]
                count += 1
                wrong += recomputed(cell, arm, half) != [e["s"], e["slo"], e["shi"]]
    check(f"11. all {count} shares with intervals recomputed from margins; number that differ", 0, wrong)

    # 12-13: per-item margins and the means behind one share
    check("12. margins of single items (count:60 item 17 with the L8 transform 189 swap; width:100 item 40 clean; count:100 item 3 corrupt)",
          (f2(float(T["margin/count:60/l8/t189"][17])), f2(float(T["margin/width:100/m_c"][40])), f2(float(T["margin/count:100/m_x"][3]))),
          (demo["margins"]["count:60"]["arms"]["l8/t189"][17], demo["margins"]["width:100"]["clean"][40], demo["margins"]["count:100"]["corrupt"][3]))
    even = torch.arange(64) % 2 == 0
    m_c, m_x, m = (T[f"margin/count:60/{k}"].double()[even] for k in ("m_c", "m_x", "l8/t189"))
    check("13. mean(m_clean - m_patched) and mean(m_clean - m_corrupt): count:60, L8 transform 189, even",
          (f3(float((m_c - m).mean())), f3(float((m_c - m_x).mean()))),
          (demo["means"]["count:60"]["even"]["num"]["l8/t189"], demo["means"]["count:60"]["even"]["den"]))

    # 14: firing rates recomputed from the gates and the token labels (count cells = the first 128 texts)
    n = 128
    usable = T["label/known"][:n].bool().clone()
    usable[:, 0] = False
    other = usable & ~T["label/line_first"][:n].bool() & ~T["label/newline"][:n].bool()
    chars = T["label/chars"][:n]
    on410 = T["gate/l9"][:n, :, 0] > 0
    on189 = T["gate/l8"][:n, :, 0] > 0
    rate = float(on410[other & (chars >= 30) & (chars < 40)].float().mean())
    first = float(on189[usable & T["label/line_first"][:n].bool()].float().mean())
    held410 = {b["bin"]: b["rate"] for b in demo["firing_rate"]["L9 transform 410"]["by_chars_in_line"]}["30-39"]
    check("14. firing rates from gates and labels: L9 transform 410 at 30-39 characters; L8 transform 189 on line-first tokens",
          (f2(rate), f3(first)), (held410, demo["firing_rate"]["L8 transform 189"]["line_first"]))

    # 15: energy fraction and the random-frame row of the link table
    largest = max(abs(result["shares"]["count:100"][f"link/mix/rand{j}/T2"]["even"][0]) for j in range(5))
    held = [r for r in demo["link_table"]["even"] if r["part"] == "random"][0]["cells"]["count:100"]["T2"]
    check("15. energy of transform 189's swapped write inside group 11586's frame; largest random-frame share, count:100, two transforms",
          (f3(result["energy_fraction_t189_swap"]["group"]), f3(largest)), (facts["demo.energy_group"]["display"], held))

    # 16: one item text and its gates
    os.environ["HF_HOME"], os.environ["HF_HUB_OFFLINE"] = args.hf_home, "1"
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-0.8B")
    items = load_file(repo("demo/line_count_items.safetensors"))
    shown = site("items-count100.json")["items"][5]
    check("16. text of count:100 item 5, clean and corrupt, decoded from the token ids",
          (tok.decode(items["count:100/ids"][5].tolist()), tok.decode(items["count:100/cor"][5].tolist())),
          ("".join(shown["clean"]), "".join(shown["corrupt"])))
    shown = site("items-width100.json")["items"][9]
    check("17. tokens of width:100 item 9 at which L9 transform 410's gate is open (count), and whether it is open at the last token",
          (int((T["gate/l9"][128 + 9, :, 0] > 0).sum()), bool(T["gate/l9"][128 + 9, -1, 0] > 0)),
          (shown["gate"]["410"].count("1"), shown["gate"]["410"][-1] == "1"))

    # 18-19: facts stated in prose, read again with plain string search
    check("18. groups, directions per group and active groups from the manifest",
          (f"{manifest['3']['state']['groups']:,}", str(manifest["3"]["state"]["group_size"]), str(manifest["3"]["state"]["k"])),
          (facts["state.groups"]["display"], facts["state.group_size"]["display"], facts["state.active"]["display"]))
    for n, (key, sentence) in enumerate((("fvu.tokens", "The splits contain {} tokens per layer"), ("splice.clean_ce", "on text with clean cross-entropy {}."),
                                         ("rule.inside_min", "must keep at least {} of the whole share")), start=19):
        check(f"{n}. the README holds the sentence with the page's value of {key}", True, sentence.format(facts[key]["display"]) in readme)

    print(f"\n{sum(results)} of {len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
