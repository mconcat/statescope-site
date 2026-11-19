"""Spot-check: re-derive numbers from the source files without the code of tools/build_data.py, and compare them with what the
page's data files and the built page hold.

    python -B tools/check_numbers.py --repo <statescope checkout> --result <folder with result.json and result.safetensors>
                                     --hf-home <Hugging Face cache with the Qwen3.5-0.8B tokenizer>
                                     [--weights-4b <folder of the Qwen3.5-4B weights with ALWAYS_ON.json>]

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
    ap.add_argument("--weights-4b", help="needed when the site has data/layers-4b.json")
    ap.add_argument("--steer", help="folder with steer.json, steer_margins.safetensors, count_curve.json and count_readout.json; needed when the site has those figures")
    ap.add_argument("--examples-4b", help="the project's notes of selected results; needed when the site has data/examples-4b.json")
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
    for n, (key, sentence, text, name) in enumerate((("fvu.tokens", "The splits for the 0.8B set contain {} tokens per layer", readme, "README"),
                                                     ("splice.clean_ce", "Clean cross-entropy was {}.", card, "model card"),
                                                     ("rule.inside_min", "The rule requires at least {} of the whole share inside the frame", readme, "README")), start=19):
        check(f"{n}. the {name} holds the sentence with the page's value of {key}", True, sentence.format(facts[key]["display"]) in text)

    # 22-24: how the paired texts are made, and the text of the first figure, from the token ids
    def lines_of(ids) -> list[str]:
        return tok.decode(ids.tolist()).split("\n")

    fills, widest, short = [], [], []
    for cell, width in (("count:60", 60), ("count:100", 100), ("width:100", 100)):
        for i in range(items[f"{cell}/ids"].shape[0]):
            clean, corrupt = lines_of(items[f"{cell}/ids"][i]), lines_of(items[f"{cell}/cor"][i])
            short.append(width - len(clean[-1]))
            if cell.startswith("count"):
                fills.append(len(corrupt[-1]) / width)
            else:
                widest.append(max(len(line) for line in corrupt[1:]) / width)
    check("22. corrupt texts: smallest and largest fill of the last line in the count cells (per cent), widest line in the width cell (times the width), "
          "and how short the clean last line is at most",
          (f"{min(fills) * 100:.0f}", f"{max(fills) * 100:.0f}", f"{max(widest):.2f}", str(max(short))),
          tuple(facts[k]["display"] for k in ("demo.corrupt_fill_low", "demo.corrupt_fill_high", "demo.width_factor", "demo.clean_short_max")))
    lead = demo["lead"]
    cell_index = [c["key"] for c in demo["cells"]].index(lead["cell"])
    row = cell_index * demo["items"] + lead["item"]
    shown = site(demo["cells"][cell_index]["file"])["items"][lead["item"]]
    check("23. characters in the line at every token of the first figure's text, from the script's labels",
          [int(v) for v in T["label/chars"][row].tolist()], shown["chars"])
    from html.parser import HTMLParser

    class Lead(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.inside, self.depth, self.text, self.on = False, 0, [], {"a": 0, "b": 0, "c": 0}
            self.tok = False

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "div" and "ttext" in a.get("class", "").split() and "data-items" in a:
                self.inside, self.depth = True, 0
            if self.inside and tag == "div":
                self.depth += 1
            cls = a.get("class", "").split()
            self.tok = self.inside and tag == "span" and "tok" in cls
            if self.tok:
                for letter in self.on:
                    self.on[letter] += letter in cls

        def handle_endtag(self, tag):
            if self.inside and tag == "div":
                self.depth -= 1
                if self.depth == 1 and self.text and self.text[-1] != "\n":
                    self.text.append("\n")
                self.inside = self.depth > 0
            self.tok = False

        def handle_data(self, data):
            if self.tok:
                self.text.append(data.replace("\u23ce", ""))

    parsed = Lead()
    parsed.feed(page)
    want_lines = tok.decode(items[f"{lead['cell']}/ids"][lead["item"]].tolist()).split("\n")[-lead["lines"]:]
    n_tokens = 0
    count = 0
    for j in range(len(shown["clean"]) - 1, -1, -1):          # tokens of the last lines
        count += shown["clean"][j] == "\n"
        if count == lead["lines"]:
            break
        n_tokens += 1
    tail = slice(len(shown["clean"]) - n_tokens, None)
    gates = (int((T["gate/l8"][row, tail, 0] > 0).sum()), int((T["gate/l9"][row, tail, 0] > 0).sum()), int((T["gate/l9"][row, tail, 1] > 0).sum()))
    check("24. the first figure in the built page: its text (decoded from the token ids) and the number of tokens marked for each of the three transforms",
          ("\n".join(want_lines), gates), ("".join(parsed.text).rstrip("\n"), (parsed.on["a"], parsed.on["b"], parsed.on["c"])))

    # 25-26: the Qwen3.5-4B section, when the site has it
    if os.path.exists(os.path.join(HERE, "data", "layers-4b.json")):
        four = site("layers-4b.json")["rows"]
        with open(repo("release/qwen35-4b/reader_fvu.json")) as f:
            fvu4 = json.load(f)["layers"]
        with open(repo("release/qwen35-4b/MANIFEST.json")) as f:
            manifest4 = json.load(f)["layers"]
        check("25. 4B: state FVU at resid_post.16 and MLP FVU at layer 31, position 0 dropped; transforms alive at layer 31",
              (f"{fvu4['16']['resid_post.16']['position_0_dropped']:.4f}", f"{fvu4['31']['mlp']['position_0_dropped']:.4f}",
               f"{manifest4['31']['mlp']['alive']} of {manifest4['31']['mlp']['transforms']}"),
              (four[16]["dropped"]["state_post"], four[31]["dropped"]["mlp"], four[31]["alive_text"]))
        assert args.weights_4b, "--weights-4b is needed to check the always-on counts"
        with open(os.path.join(args.weights_4b, "ALWAYS_ON.json")) as f:
            always = json.load(f)["layers"]
        best = max(always, key=lambda k: always[k]["energy_share_on_90pct"])
        check("26. 4B: always-on transforms at layer 13 (web text / training mix), and the layer with the largest share of write energy",
              (f"{len(always['13']['on_90pct'])} / {always['13']['training_mix_heldout_counts']['on_90pct']}", best, f"{always[best]['energy_share_on_90pct']:.2f}"),
              (four[13]["always_text"], facts["b4.energy_max_layer"]["display"], facts["b4.energy_max"]["display"]))

    # 27-30: the dose figure and the two count figures, from the files of their runs
    if os.path.exists(os.path.join(HERE, "data", "steer.json")):
        assert args.steer, "--steer is needed to check the dose figure"
        held = site("steer.json")
        S = load_file(os.path.join(args.steer, "steer_margins.safetensors"))
        cell, arm, alpha = "width:100", "head_o", "0.75"
        m_c, m_x, m = (S[f"margin/{cell}/{k}"].double() for k in ("m_c", "m_x", f"{arm}@{alpha}"))
        i = held["alphas"].index(alpha)
        a = held["cells"][cell]["arms"][arm]
        check(f"27. dose figure: share, mean margin and the margin of item 12 recomputed from the run's margins: {cell}, {arm}, dose {alpha}",
              (f3(float((m_c - m).mean() / (m_c - m_x).mean())), f2(float(m.mean())), f2(float(m[12]))), (a["share"][i], a["mean"][i], a["items"][i][12]))
        i1 = held["alphas"].index("1")
        check("28. dose figure: dose 1 is the demonstration's swap (share on all items, L8 transform 189, count:60), and dose 0 is the clean run (item 5)",
              (demo["shares"]["count:60"]["l8/t189"]["all"]["s"], demo["margins"]["count:60"]["clean"][5]),
              (held["cells"]["count:60"]["arms"]["l8/t189"]["share"][i1], held["cells"]["count:60"]["arms"]["l8/t189"]["items"][held["alphas"].index("0")][5]))
    if os.path.exists(os.path.join(HERE, "data", "count-curve.json")):
        assert args.steer, "--steer is needed to check the count figures"
        with open(os.path.join(args.steer, "count_curve.json")) as f:
            cc = json.load(f)
        with open(os.path.join(args.steer, "count_readout.json")) as f:
            cr = json.load(f)
        held, heldr = site("count-curve.json"), site("count-readout.json")
        check("29. count curve: the point of count 40 in texts wrapped at 100, its tokens, and the share of variance in the plane",
              (f3(cc["widths"]["100"]["projection"][40][0]), f3(cc["widths"]["100"]["projection"][40][1]), f"{cc['widths']['100']['tokens_active'][40]:,}",
               f3(sum(cc["plane"]["variance_share_of_components"][:2]))),
              (held["widths"]["100"]["x"][40], held["widths"]["100"]["y"][40], held["widths"]["100"]["tokens"][40], facts["curve.plane"]["display"]))
        check("30. count readout: threshold of transform 1749, its mean gate input and firing rate at 95 characters (width 100), R² of transform 410 (width 60)",
              (f3(cr["threshold"]["1749"]), f2(cr["widths"]["100"]["1749"]["mean_gate_input"][95]), f2(cr["widths"]["100"]["1749"]["firing_rate"][95]),
               f3(cr["widths"]["60"]["410"]["r2_gate_input_on_frame_part"])),
              (heldr["threshold"]["1749"], heldr["widths"]["100"]["1749"]["gate"][95], heldr["widths"]["100"]["1749"]["rate"][95], facts["read.t410_r2_w60"]["display"]))
    # 31-32: the 4B examples: numbers from the 4B model card, samples from the notes
    if os.path.exists(os.path.join(HERE, "data", "used-4b.json")):
        with open(repo("release/qwen35-4b/MODEL_CARD.md")) as f:
            card4 = f.read()
        used = site("used-4b.json")
        sentences = (f"The rate of correct rules rose from {used['rule']['bars'][0]['value']} to {used['rule']['bars'][1]['value']}.",
                     f"It flipped from ABA to ABB in {used['aba']['flips'][0]['value']} of prompts.",
                     f"sixteen {used['aba']['ranges'][2]['lo']} to {used['aba']['ranges'][2]['hi']}.",
                     f"the MLP reconstruction carried {used['js']['bars'][0]['value']} of the MLP's contribution, with an interval of {used['js']['bars'][0]['lo']} to {used['js']['bars'][0]['hi']}.")
        check("31. 4B examples: the 4B model card holds the sentences with the page's values", [True] * len(sentences), [x in card4 for x in sentences])
    if os.path.exists(os.path.join(HERE, "data", "examples-4b.json")):
        assert args.examples_4b, "--examples-4b is needed to check the samples"
        with open(args.examples_4b) as f:
            notes = f.read()
        ex = site("examples-4b.json")
        check("32. 4B examples: the generated function and the four natural-text contexts stand in the notes, character for character",
              [True] * 5, [ex["rule_sample"] in notes] + [c in notes for c in ex["contexts"]["aba"] + ex["contexts"]["less"]])

    print(f"\n{sum(results)} of {len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
