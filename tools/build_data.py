"""Generate every data file of the site from the statescope repository. Nothing in data/ is written by hand.

    python -B tools/build_data.py --repo <statescope checkout> --hf-home <Hugging Face cache with the Qwen3.5-0.8B tokenizer>
                                  --result <folder with result.json and result.safetensors>

Reads only. Needs torch, safetensors and transformers (the tokenizer decodes the demonstration items; no model is loaded, CPU only).
--result is the folder that `python demo/line_count.py --release <weights> --out <folder>` wrote.

Sources, all relative to --repo:
  README.md                                  facts stated in prose (found by a pattern around the number, never retyped)
  release/qwen35-08b-v2/MODEL_CARD.md        the spliced-in loss table, kept as the card's own strings
  release/qwen35-08b-v2/MANIFEST.json        sizes, steps, penalties, numbers recorded at training
  release/qwen35-08b-v2/reader_fvu.json      FVU measured by the repository on all held-out tokens
  release/qwen35-08b-v2/layers_table.md      compared with the generated per-layer strings (must be equal)
  release/qwen35-08b-v2/line_count_table.md, line_count_link_table.md     compared with the generated shares (must be equal)
  demo/line_count.py                         the chosen head, transforms and groups (constants)
  demo/line_count_items.safetensors          token ids of the item pairs
  <result>/result.json, result.safetensors   shares, firing rates, per-item margins, gates

Writes data/facts.json, layers.json, splice.json, demo.json and items-<cell>.json.

The Qwen3.5-4B section is optional. It is built when the checkout holds release/qwen35-4b/reader_fvu.json and MODEL_CARD.md and
  --weights-4b <folder>  a folder of the 4B weights repository that holds ALWAYS_ON.json
is given. Then data/layers-4b.json is written and the facts get keys that start with "b4.". Otherwise the file is removed and
tools/build_page.py leaves the section out.
"""
from __future__ import annotations

import argparse
import json
import os
import re

import torch
from safetensors.torch import load_file

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
REL = "release/qwen35-08b-v2"
README, CARD, MANIFEST, READER_FVU = "README.md", f"{REL}/MODEL_CARD.md", f"{REL}/MANIFEST.json", f"{REL}/reader_fvu.json"
SCRIPT, ITEMS = "demo/line_count.py", "demo/line_count_items.safetensors"
RESULT_JSON, RESULT_ST = "result.json of one run of demo/line_count.py", "result.safetensors of one run of demo/line_count.py"
REL4 = "release/qwen35-4b"
ALWAYS_ON = "ALWAYS_ON.json of the Qwen3.5-4B weights repository"
LEAD = ("count:100", 47, 7)     # the text of the page's first figure: cell, item, number of last lines. Chosen by hand as a readable example.


def comma(n: int) -> str:
    return f"{n:,}"


def fixed(x: float, digits: int) -> str:
    """fixed-point string; a negative zero is written without its sign"""
    s = f"{x:.{digits}f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def write(name: str, obj: dict) -> None:
    path = os.path.join(DATA, name)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote data/{name}  {os.path.getsize(path):,} bytes")


def md_table(text: str, first_header: str) -> list[list[str]]:
    """the body rows of the markdown table whose header row starts with `first_header`"""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"| {first_header} |"))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return rows


class Facts:
    """key -> display string, with the file each one was read from"""

    def __init__(self, repo: str) -> None:
        self.repo, self.items, self.text = repo, {}, {}

    def read(self, rel: str) -> str:
        if rel not in self.text:
            with open(os.path.join(self.repo, rel)) as f:
                self.text[rel] = f.read()
        return self.text[rel]

    def add(self, key: str, display: str, source: str, how: str) -> None:
        assert key not in self.items, key
        self.items[key] = {"display": display, "source": source, "how": how}

    def find(self, rel: str, pattern: str, keys: list[str], text: str | None = None) -> None:
        """one pattern, one capture group per key; the pattern must match exactly once in the file (or in `text`, named `rel`)"""
        found = re.findall(pattern, self.read(rel) if text is None else text)
        assert len(found) == 1, f"{rel}: {len(found)} matches for {pattern!r}"
        groups = found[0] if isinstance(found[0], tuple) else (found[0],)
        assert len(groups) == len(keys), (pattern, groups)
        for key, value in zip(keys, groups):
            self.add(key, value, rel, f"text matched by /{pattern}/")


# ---------------------------------------------------------------------------------------------- facts stated in prose and in the manifest
def text_facts(facts: Facts, manifest: dict, reader_fvu: dict) -> None:
    f = facts
    f.find(CARD, r"for each of the (\d+) layers of `Qwen/Qwen3\.5-0\.8B`\. The model has width (\d+)\. The base-model revision is `([0-9a-f]{40})`\.",
           ["model.layers", "model.width", "model.revision"])
    f.find(README, r"The 0\.8B set contains (\d+) files\. Its state dictionaries occupy about ([\d.]+) GiB, and its MLP dictionaries occupy about ([\d.]+) GiB\.",
           ["set.files", "set.state_gib", "set.mlp_gib"])
    f.find(README, r"Each layer's dictionary was trained on ([\d,]+) tokens over ([\d,]+) steps\.", ["state.train_tokens", "state.train_steps"])
    f.find(README, r"The 0\.8B set has (\d+) transforms of rank (\d+), (\d+) of rank (\d+), (\d+) of rank (\d+), ([\d,]+) of rank (\d+) and ([\d,]+) of rank (\d+)\.",
           ["mlp.tier1_n", "mlp.tier1_rank", "mlp.tier2_n", "mlp.tier2_rank", "mlp.tier3_n", "mlp.tier3_rank", "mlp.tier4_n", "mlp.tier4_rank",
            "mlp.tier5_n", "mlp.tier5_rank"])
    f.find(README, r"Training used ([\d,]+) steps of (\d+) tokens, or ([\d.]+) million tokens, per layer\. The learning rate was ([\d.e+-]+)\.",
           ["mlp.train_steps", "mlp.step_tokens", "mlp.train_million_tokens", "mlp.learning_rate"])
    f.find(README, r"The chance value for a 4-dimensional frame in ([\d,]+) dimensions is ([\d.]+)\.", ["demo.chance_dims", "demo.chance_value"])
    f.find(README, r"Single-item margins of dictionary swaps are reproducible to about ([\d.]+)\. Shares are reproducible to about ([\d.]+)\.",
           ["demo.margin_repro", "demo.share_repro"])
    f.find(README, r"A (1e-6) relative difference between implementations flips some rounded elements\.", ["demo.relative_difference"])
    f.find(README, r"The rule requires at least ([\d.]+) of the whole share inside the frame, at most ([\d.]+) of it and at most ([\d.]+) in the rest, and at most "
                   r"([\d.]+) in random frames, in both count cells\.", ["rule.inside_min", "rule.rest_max_fraction", "rule.rest_max", "rule.random_max"])
    f.find(README, r"because it recorded a share of ([\d.]+) for the rest in `count:100` through those two transforms", ["rule.recorded_rest"])
    f.find(CARD, r"in nats on text with clean cross-entropy ([\d.]+)\.", ["splice.clean_ce"])
    f.find(CARD, r"It took the first (\d+) documents of at least (\d+) tokens and the first (\d+) tokens of each", ["splice.documents", "splice.min_tokens", "splice.tokens_each"])
    f.find(CARD, r"The loss was averaged over positions (\d+) to (\d+), or ([\d,]+) positions\.", ["splice.first_position", "splice.last_position", "splice.positions"])
    f.find(CARD, r"For the state dictionary at layer (\d+), the recorded increase was (\+[\d.]+) for this set against (\+[\d.]+) for the earlier set\.",
           ["splice.example_layer", "splice.l9_state_here", "splice.l9_state_earlier"])
    f.find(README, r"with the bootstrap interval from ([\d.]+) % to ([\d.]+) % in parentheses", ["demo.interval_low", "demo.interval_high"])
    f.find(README, r"At layer (\d+), `resid_mid`, state FVU is ([\d.]+) with position 0 and ([\d.]+) without it\. At layer 0",
           ["fvu.example_layer", "fvu.example_with_p0_readme", "fvu.example_dropped_readme"])
    example = re.findall(r"```python\n(import torch\n.*?)```", f.read(CARD), flags=re.S)
    assert example and "from statescope.reader import" in example[0] and "Qwen/Qwen3.5-0.8B" in example[0]
    f.add("reader.example", example[0].rstrip("\n"), CARD, "the first python block of the card, unchanged")
    f.find(CARD, r"At layer 23, the released MLP dictionary had the smaller increase, (\+[\d.]+) against (\+[\d.]+) for the earlier set\.",
           ["splice.l23_mlp_here", "splice.l23_mlp_earlier"])
    # what the tests showed, and what a reader can run
    f.find(README, r'`pytest -m "not legacy"` runs the (\d+) tests that need no private data\.', ["check.tests"])
    f.find(CARD, r"This covered (\d+) layers and (\d+) splits of ([\d,]+) tokens at (\d+) sites\. Of ([\d,]+) tokens, (\d+) selected a different group set\. "
                 r"Each had its 24th and 25th group norms within ([\d.e-]+)\. Raw reconstructions elsewhere agreed within ([\d.e-]+) relative\. "
                 r"All (\d+) of the trainer's held-out FVU numbers in its own units were reproduced within ([\d.e-]+)\.",
           ["check.state_layers", "check.state_splits", "check.state_split_tokens", "check.state_sites", "check.state_tokens", "check.state_differ",
            "check.state_norm_gap", "check.state_recon", "check.state_fvu_n", "check.state_fvu"])
    f.find(CARD, r"The MLP reader was compared with the unmodified public forward pass at (\d+) layers\. There was (\d+) differing gate decision, "
                 r"at layer (\d+)\. Outputs on other tokens agreed within ([\d.e-]+) relative\.",
           ["check.mlp_layers", "check.mlp_differ", "check.mlp_differ_layer", "check.mlp_out"])
    f.find(CARD, r"matched the forward pass within ([\d.e-]+) relative\.", ["check.mlp_sum"])
    f.find(CARD, r"agreed with the original project's table within ([\d.e-]+) at all 24 layers and both sites\. The limit was ([\d.e-]+)\.",
           ["check.fvu_agree", "check.fvu_limit"])
    f.find(CARD, r"Every demonstration share agreed within ([\d.]+) with the original harness's reference run and the original project's recorded "
                 r"numbers\. There were (\d+) swaps x (\d+) cells x (\d+) halves = (\d+) comparisons\. The original registration's tolerance was ([\d.]+)\.",
           ["check.share_agree", "check.share_swaps", "check.share_cells", "check.share_halves", "check.share_n", "check.share_limit"])
    f.find(README, r"A fresh clone, a new environment and a fresh download reproduce the demonstration byte for byte with torch ([\w.+]+) and transformers ([\d.]+)\.",
           ["check.tested_torch", "check.tested_transformers"])
    f.find(README, r"With newer library versions, torch ([\w.+]+) and transformers ([\d.]+), shares differ by at most ([\d.]+)\.",
           ["check.new_torch", "check.new_transformers", "check.new_share_diff"])
    f.find(README, r"With newer library versions, the demonstration's shares moved by up to about ([\d.]+),", ["check.new_share_about"])
    f.find(CARD, r"The (\d+) files occupy about ([\d.]+) gibibytes", ["set.all_files", "set.total_gib"])
    assert "It ran in under two minutes on one RTX 5090, including model loading." in f.read(README)
    assert "Rules R8 and R9 were written and committed before the runs they judge." in f.read(CARD)
    assert "All comparisons ran on one machine with one RTX 5090." in f.read(README)
    # how the paired texts are made (item_files() measures the same numbers on the texts and compares)
    f.find(README, r"In every cell, the clean text's last line is full, at most (\d+) characters short of the width, so a line break is due\.", ["demo.clean_short_max"])
    f.find(README, r"chosen so that the line holds between (\d+)% and (\d+)% of the width at the last word, and the preceding lines are wrapped backward from that "
                   r"word at the same width, moving their line breaks too\.", ["demo.corrupt_fill_low", "demo.corrupt_fill_high"])
    f.find(README, r"the corrupt text's last line starts at the same word as the clean text's, and the preceding lines are wrapped backward at ([\d.]+) times the "
                   r"width\.", ["demo.width_factor"])

    layers = manifest["layers"]
    state, mlp = [layers[str(i)]["state"] for i in range(len(layers))], [layers[str(i)]["mlp"] for i in range(len(layers))]
    for key, field in (("state.groups", "groups"), ("state.group_size", "group_size"), ("state.active", "k")):
        values = {s[field] for s in state}
        assert len(values) == 1
        f.add(key, comma(values.pop()), MANIFEST, f"layers.*.state.{field}, the same at every layer")
    values = {m["transforms"] for m in mlp}
    assert len(values) == 1
    f.add("mlp.transforms", comma(values.pop()), MANIFEST, "layers.*.mlp.transforms, the same at every layer")
    assert len(layers) == int(f.items["model.layers"]["display"])
    assert {comma(s["steps"]) for s in state} == {f.items["state.train_steps"]["display"]}
    f.add("set.model", manifest["model"], MANIFEST, "model")
    f.add("set.frozen", manifest["frozen"], MANIFEST, "frozen")
    penalties = [m["penalty"] for m in mlp]
    assert len(set(penalties[:-1])) == 1 and penalties[-1] != penalties[0]
    f.add("mlp.penalty_main", f"{penalties[0]:.1e}", MANIFEST, "layers.0..22.mlp.penalty, the same at these layers")
    f.add("mlp.penalty_last", f"{penalties[-1]:.1e}", MANIFEST, "layers.23.mlp.penalty")
    f.add("mlp.penalty_main_last_layer", str(len(layers) - 2), MANIFEST, "index of the last layer with the main penalty")
    f.add("model.last_layer", str(len(layers) - 1), MANIFEST, "index of the last layer")
    f.add("model.first_layer", min(layers, key=int), MANIFEST, "index of the first layer")

    tokens = {v["tokens"] for v in reader_fvu["layers"].values()}
    p0 = {v["position_0_tokens"] for v in reader_fvu["layers"].values()}
    assert len(tokens) == 1 and len(p0) == 1
    f.add("fvu.tokens", comma(tokens.pop()), READER_FVU, "layers.*.tokens, the same at every layer")
    f.add("fvu.position_0_tokens", comma(p0.pop()), READER_FVU, "layers.*.position_0_tokens, the same at every layer")
    assert len(reader_fvu["splits"]) == 4, "the page's word 'four' no longer holds"
    at = f.items["fvu.example_layer"]["display"]                              # the layer the README gives as its example
    example = reader_fvu["layers"][at][f"resid_mid.{at}"]
    f.add("fvu.l6_mid_with_p0", fixed(example["with_position_0"], 4), READER_FVU, f"layers.{at}.resid_mid.{at}.with_position_0")
    f.add("fvu.l6_mid_dropped", fixed(example["position_0_dropped"], 4), READER_FVU, f"layers.{at}.resid_mid.{at}.position_0_dropped")
    assert f.items["fvu.l6_mid_with_p0"]["display"] == f.items.pop("fvu.example_with_p0_readme")["display"]
    assert f.items["fvu.l6_mid_dropped"]["display"] == f.items.pop("fvu.example_dropped_readme")["display"]
    # The README says the MLP numbers with and without position 0 "differ by at most 0.014 at any layer". The largest difference in
    # reader_fvu.json rounds to that value but is slightly above it, so the page does not repeat the sentence; it shows both numbers.
    largest = max(abs(v["mlp"]["with_position_0"] - v["mlp"]["position_0_dropped"]) for v in reader_fvu["layers"].values())
    stated = re.findall(r"For the MLP dictionary, the two differ by at most ([\d.]+) at any layer\.", f.read(README))
    assert len(stated) == 1 and fixed(largest, 3) == stated[0], (largest, stated)


# ---------------------------------------------------------------------------------------------- numbers per layer
def layers_data(facts: Facts, manifest: dict, reader_fvu: dict) -> dict:
    rows = []
    for i in range(len(manifest["layers"])):
        m, r = manifest["layers"][str(i)]["mlp"], reader_fvu["layers"][str(i)]
        mid, post, mlp = r[f"resid_mid.{i}"], r[f"resid_post.{i}"], r["mlp"]
        rows.append({
            "layer": i,
            "dropped": {"state_mid": fixed(mid["position_0_dropped"], 4), "state_post": fixed(post["position_0_dropped"], 4),
                        "mlp": fixed(mlp["position_0_dropped"], 4)},
            "with_p0": {"state_mid": fixed(mid["with_position_0"], 4), "state_post": fixed(post["with_position_0"], 4),
                        "mlp": fixed(mlp["with_position_0"], 4)},
            "mlp_train": fixed(m["heldout_fvu"], 4), "on_per_token": fixed(m["heldout_l0"], 1),
            "alive": m["alive"], "transforms": m["transforms"], "alive_text": f"{m['alive']} of {m['transforms']}",
            "penalty": f"{m['penalty']:.1e}"})
    table = md_table(facts.read(f"{REL}/layers_table.md"), "Layer")
    assert len(table) == len(rows)
    for row, cells in zip(rows, table):
        mine = [str(row["layer"]), row["dropped"]["state_mid"], row["dropped"]["state_post"], row["dropped"]["mlp"], row["mlp_train"],
                row["on_per_token"], row["alive_text"], row["penalty"]]
        assert mine == cells, (mine, cells)
    card_table = md_table(facts.read(CARD), "Layer")
    assert card_table == table
    print(f"per-layer strings equal {REL}/layers_table.md and the card's table: {len(rows)} rows x {len(table[0])} columns")
    return {"sources": [READER_FVU, MANIFEST, f"{REL}/layers_table.md (compared, equal)"],
            "columns": {"state_mid": "State FVU, resid_mid", "state_post": "State FVU, resid_post", "mlp": "MLP FVU",
                        "mlp_train": "MLP FVU recorded at training", "on_per_token": "MLP transforms on per token",
                        "alive": "MLP transforms alive", "penalty": "MLP penalty"},
            "rows": rows}


def splice_data(facts: Facts) -> dict:
    card = facts.read(CARD)
    section = card[card.index("## Spliced-in loss"):]
    table = md_table(section, "Layer")
    assert len(table) == int(facts.items["model.layers"]["display"])
    rows = []
    for layer, state, mlp in table:
        assert re.fullmatch(r"\+\d\.\d+", state) and re.fullmatch(r"\+\d\.\d+", mlp), (state, mlp)
        rows.append({"layer": int(layer), "state": state, "mlp": mlp})
    assert rows[int(facts.items["splice.example_layer"]["display"])]["state"] == facts.items["splice.l9_state_here"]["display"]
    assert rows[23]["mlp"] == facts.items["splice.l23_mlp_here"]["display"]
    return {"sources": [f"{CARD}, table of the section 'Spliced-in loss', strings unchanged"],
            "columns": {"state": "State dictionary spliced in at resid_post", "mlp": "MLP dictionary spliced in"}, "rows": rows}


# ---------------------------------------------------------------------------------------------- the demonstration
def script_constants(facts: Facts) -> dict:
    src = facts.read(SCRIPT)

    def one(pattern: str) -> tuple:
        found = re.findall(pattern, src, flags=re.M)
        assert len(found) == 1, pattern
        return found[0] if isinstance(found[0], tuple) else (found[0],)

    c = {"cells": re.findall(r'"([a-z]+:\d+)"', one(r"^CELLS = \((.*)\)$")[0]),
         "count_cells": re.findall(r'"([a-z]+:\d+)"', one(r"^COUNT_CELLS = \((.*)\)$")[0]),
         "head": int(one(r"^HEAD = (\d+)")[0]),
         "l8_transform": int(one(r"^L8_TRANSFORM, L8_GROUP = (\d+), (\d+)")[0]),
         "l8_group": int(one(r"^L8_TRANSFORM, L8_GROUP = (\d+), (\d+)")[1]),
         "l9_transforms": [int(v) for v in one(r"^L9_TRANSFORMS = \((\d+), (\d+)\)")],
         "l9_group": int(one(r"^L9_GROUP = (\d+)")[0]),
         "six": [int(v) for v in re.findall(r"\d+", one(r'^LINK_ROUTES = \{"F2": \(([\d, ]+)\), "T2": L9_TRANSFORMS\}')[0])],
         "frame_dim": int(one(r"^FRAME_DIM = (\d+)")[0]),
         "random_frames": int(one(r"^N_RANDOM_FRAMES = (\d+)")[0]),
         "char_bin": int(one(r"^CHAR_BIN = (\d+)")[0])}
    for key, value in (("demo.head", c["head"]), ("demo.l8_transform", c["l8_transform"]), ("demo.l8_group", c["l8_group"]),
                       ("demo.l9_transform_short", c["l9_transforms"][0]), ("demo.l9_transform_long", c["l9_transforms"][1]),
                       ("demo.l9_group", c["l9_group"]), ("demo.frame_dim", c["frame_dim"]), ("demo.random_frames", c["random_frames"])):
        facts.add(key, str(value), SCRIPT, "constant of the script")
    facts.add("demo.six", ", ".join(str(v) for v in c["six"][:-1]) + f" and {c['six'][-1]}", SCRIPT, "LINK_ROUTES['F2']")
    assert len(c["six"]) == 6 and len(c["cells"]) == 3, "the page's words 'six' and 'three' no longer hold"
    return c


SIX_WORD = "six"            # the README's word for the selected L9 transforms; script_constants() checks that there are six


def arm_list(c: dict) -> list[dict]:
    """every arm of the script with the wording of the README's table rows and of the script's docstrings"""
    head, t189, g8, (t_short, t_long), g9 = c["head"], c["l8_transform"], c["l8_group"], c["l9_transforms"], c["l9_group"]
    mixer = "The clean texts are run with the output of the L9 mixer replaced."
    through = ("The change is added to resid_post.8 and sent through the model's own L9 mixer only; the residual's direct path stays clean.")
    at_mlp = "The clean texts are run with the output of the L9 MLP replaced."
    arms = [
        {"key": "layer_y", "group": "main", "label": "L9 mixer, whole output", "what": f"The L9 mixer's whole output is swapped. {mixer}"},
        {"key": "head_o", "group": "main", "label": f"L9 mixer, head {head} only", "what": f"Only head {head}'s read is swapped. {mixer}"},
        {"key": "l8/full_post8", "group": "main", "label": "resid_post.8, whole, through the L9 mixer", "what": f"All of resid_post.8 is swapped. {through}"},
        {"key": "l8/mlp8_true", "group": "main", "label": "L8 MLP output, through the L9 mixer", "what": f"The L8 MLP's output is swapped. {through}"},
        {"key": "l8/molt8_all", "group": "main", "label": "L8 MLP dictionary, all transforms, through the L9 mixer",
         "what": f"The writes of all transforms of the L8 dictionary are swapped. {through}"},
        {"key": f"l8/t{t189}", "group": "main", "label": f"L8 transform {t189}, through the L9 mixer", "what": f"Only transform {t189}'s write is swapped. {through}"},
        {"key": f"l8/g{g8}", "group": "main", "label": f"state group {g8}, through the L9 mixer", "what": f"Only state group {g8}'s contribution is swapped. {through}"},
        {"key": "l9/mlp9_y", "group": "main", "label": "L9 MLP output", "what": f"The L9 MLP's whole output is swapped. {at_mlp}"},
        {"key": "l9/molt9_all", "group": "main", "label": "L9 MLP dictionary, all transforms",
         "what": f"The writes of all transforms of the L9 dictionary are swapped. {at_mlp}"},
        {"key": f"l9/t{t_short}", "group": "main", "label": f"L9 transform {t_short}", "what": f"Only transform {t_short}'s write is swapped. {at_mlp}"},
        {"key": f"l9/t{t_long}", "group": "main", "label": f"L9 transform {t_long}", "what": f"Only transform {t_long}'s write is swapped. {at_mlp}"}]
    routes = {"F2": (f"through the {SIX_WORD} selected L9 transforms",
                     "The changed resid_mid.9 enters the L9 MLP dictionary, and only the change in the selected transforms' writes is patched at the MLP output."),
              "T2": (f"through transforms {t_short} and {t_long} alone",
                     "The changed resid_mid.9 enters the L9 MLP dictionary, and only the change in the selected transforms' writes is patched at the MLP output."),
              "down": ("with everything downstream", "The change is added at the mixer's output and everything downstream follows.")}
    bases = {"mix": "whole mixer swap", "h10o": f"head {head} swap"}
    parts = {"full": "all of it", f"g{g9}": f"only the part inside group {g9}'s frame", f"minus_g{g9}": "the rest"}
    for base, base_label in bases.items():
        for part, part_label in parts.items():
            for route in ("down", "F2", "T2"):
                arms.append({"key": f"link/{base}/{part}/{route}", "group": "link", "label": f"{base_label}, {part_label}, {routes[route][0]}",
                             "what": routes[route][1], "base": base, "part": part, "route": route})
    for j in range(c["random_frames"]):
        for route in ("F2", "T2"):
            arms.append({"key": f"link/mix/rand{j}/{route}", "group": "random",
                         "label": f"whole mixer swap, only the part inside random {c['frame_dim']}-dimensional frame {j + 1} of {c['random_frames']}, {routes[route][0]}",
                         "what": routes[route][1], "base": "mix", "part": f"rand{j}", "route": route})
    return arms


def share_entry(v: list[float]) -> dict:
    return {"v": round(v[0], 4), "lo": round(v[1], 4), "hi": round(v[2], 4), "s": fixed(v[0], 3), "slo": fixed(v[1], 3), "shi": fixed(v[2], 3)}


def demo_data(facts: Facts, c: dict, result: dict, tensors: dict, n_items: int, n_tokens: int) -> dict:
    cells, arms = c["cells"], arm_list(c)
    keys = [a["key"] for a in arms]
    halves = {"all": lambda i: True, "even": lambda i: i % 2 == 0, "odd": lambda i: i % 2 == 1}
    shares, margins, means = {}, {}, {}
    for cell in cells:
        assert set(result["shares"][cell]) == set(keys), cell
        shares[cell] = {k: {h: share_entry(result["shares"][cell][k][h]) for h in halves} for k in keys}
        m_c, m_x = tensors[f"margin/{cell}/m_c"].double(), tensors[f"margin/{cell}/m_x"].double()
        assert len(m_c) == n_items
        margins[cell] = {"clean": [fixed(v, 2) for v in m_c.tolist()], "corrupt": [fixed(v, 2) for v in m_x.tolist()],
                         "arms": {k: [fixed(v, 2) for v in tensors[f"margin/{cell}/{k}"].tolist()] for k in keys}}
        means[cell] = {}
        for h, keep in halves.items():
            sel = torch.tensor([keep(i) for i in range(n_items)])
            den = float((m_c[sel] - m_x[sel]).mean())
            means[cell][h] = {"n": int(sel.sum()), "clean": fixed(float(m_c[sel].mean()), 2), "corrupt": fixed(float(m_x[sel].mean()), 2),
                              "den": fixed(den, 3),
                              "num": {k: fixed(float((m_c[sel] - tensors[f"margin/{cell}/{k}"].double()[sel]).mean()), 3) for k in keys}}

    # the two published tables, rebuilt from result.json and compared with the repository's files
    main_keys = [a["key"] for a in arms if a["group"] == "main"]
    table = md_table(facts.read(f"{REL}/line_count_table.md"), "Swap")
    assert len(table) == len(main_keys)
    labels = {a["key"]: a["label"] for a in arms}
    for key, row in zip(main_keys, table):
        assert row[0].replace("`", "") == labels[key], (row[0], labels[key])
        for cell, text in zip(cells, row[1:]):
            e = shares[cell][key]["even"]
            assert f"{e['s']} ({e['slo']} to {e['shi']})" == text, (key, cell, text, e)
    # the link table for each set of items; the published table is the even-numbered one
    bases = {"mix": "whole mixer swap", f"h{c['head']}o": f"head {c['head']} swap"}
    parts = {"full": "all of it", f"g{c['l9_group']}": f"only the part inside group {c['l9_group']}'s frame", f"minus_g{c['l9_group']}": "the rest",
             "random": f"only the part inside a random {c['frame_dim']}-dimensional frame (largest of {c['random_frames']}, absolute)"}
    link_routes = {"F2": f"through the {SIX_WORD} selected L9 transforms", "T2": f"through transforms {c['l9_transforms'][0]} and {c['l9_transforms'][1]} alone",
                   "down": "with everything downstream"}
    link_tables = {}
    for h in halves:
        rows = []
        for base in bases:
            for part in list(parts)[:3]:
                rows.append({"base": base, "part": part,
                             "cells": {cell: {r: shares[cell][f"link/{base}/{part}/{r}"][h]["s"] for r in ("F2", "T2", "down")} for cell in cells}})
        rows.append({"base": "mix", "part": "random",
                     "cells": {cell: {r: fixed(max(abs(result["shares"][cell][f"link/mix/rand{j}/{r}"][h][0]) for j in range(c["random_frames"])), 3)
                                      for r in ("F2", "T2")} for cell in cells}})
        link_tables[h] = rows
    link_rows = link_tables["even"]
    table = md_table(facts.read(f"{REL}/line_count_link_table.md"), "Change at the L9 mixer output")
    assert len(table) == len(link_rows)
    for mine, row in zip(link_rows, table):
        assert row[0] == f"{bases[mine['base']]}, {parts[mine['part']]}", (row[0], mine)
        for cell, text in zip(cells, row[1:]):
            v = mine["cells"][cell]
            assert (f"{v['F2']} / {v['T2']} ({v['down']})" if "down" in v else f"{v['F2']} / {v['T2']}") == text, (mine, cell, text)
    print(f"even-half shares equal {REL}/line_count_table.md ({len(main_keys)} rows) and line_count_link_table.md ({len(link_rows)} rows)")

    firing = {}
    for name, rates in result["firing_rate"].items():
        firing[name] = {"line_first": fixed(rates["line_first"], 3), "newline": fixed(rates["newline"], 3), "other": fixed(rates["other"], 3),
                        "by_chars_in_line": [{"bin": k, "rate": fixed(v, 2)} for k, v in rates["by_chars_in_line"].items()]}
    energy = result["energy_fraction_t189_swap"]
    t189 = firing[f"L8 transform {c['l8_transform']}"]
    facts.add("demo.t189_line_first", t189["line_first"], RESULT_JSON, "firing_rate['L8 transform 189'].line_first")
    facts.add("demo.t189_newline", t189["newline"], RESULT_JSON, "firing_rate['L8 transform 189'].newline")
    facts.add("demo.t189_other", t189["other"], RESULT_JSON, "firing_rate['L8 transform 189'].other")
    facts.add("demo.energy_group", fixed(energy["group"], 3), RESULT_JSON, "energy_fraction_t189_swap.group")
    facts.add("demo.energy_random_max", fixed(max(v for k, v in energy.items() if k.startswith("random")), 3), RESULT_JSON,
              "largest of energy_fraction_t189_swap.random*")
    facts.add("demo.items_per_cell", str(n_items), ITEMS, "first dimension of <cell>/ids")
    facts.add("demo.tokens_per_text", str(n_tokens), ITEMS, "second dimension of <cell>/ids")
    facts.add("demo.items_per_half", str(means[cells[0]]["even"]["n"]), ITEMS, "even-numbered items of one cell")
    facts.add("demo.arms", str(len(keys)), RESULT_JSON, "number of swaps per cell in shares")
    facts.add("demo.lead_cell", LEAD[0], "tools/build_data.py", "LEAD: the text of the page's first figure, chosen by hand")
    facts.add("demo.lead_item", str(LEAD[1]), "tools/build_data.py", "LEAD: the text of the page's first figure, chosen by hand")
    facts.add("demo.lead_lines", str(LEAD[2]), "tools/build_data.py", "LEAD: number of last lines of that text shown")
    for cell in cells:                                                    # the README's sentences about the rest, as facts
        tag = cell.replace(":", "")
        rest = link_rows[2]["cells"][cell]
        facts.add(f"link.rest_six.{tag}", rest["F2"], RESULT_JSON, f"shares['{cell}']['link/mix/minus_g4885/F2'].even")
        facts.add(f"link.rest_two.{tag}", rest["T2"], RESULT_JSON, f"shares['{cell}']['link/mix/minus_g4885/T2'].even")
        facts.add(f"link.rest_down.{tag}", rest["down"], RESULT_JSON, f"shares['{cell}']['link/mix/minus_g4885/down'].even")
    facts.add("link.random_six_max", max(link_rows[-1]["cells"][cell]["F2"] for cell in cells), RESULT_JSON, "largest random-frame share, six transforms, even half")
    facts.add("link.random_two_max", max(link_rows[-1]["cells"][cell]["T2"] for cell in cells), RESULT_JSON, "largest random-frame share, two transforms, even half")

    cell_info = []
    for cell in cells:
        kind, width = cell.split(":")
        cell_info.append({"key": cell, "kind": kind, "width": int(width), "file": f"items-{kind}{width}.json"})
    return {"sources": [RESULT_JSON, RESULT_ST, SCRIPT, f"{REL}/line_count_table.md (compared, equal)", f"{REL}/line_count_link_table.md (compared, equal)"],
            "cells": cell_info, "count_cells": c["count_cells"], "items": n_items, "constants": c, "arms": arms, "shares": shares,
            "means": means, "margins": margins, "link_table": link_tables,
            "link_labels": {"bases": bases, "parts": parts, "routes": link_routes}, "firing_rate": firing,
            "lead": {"cell": LEAD[0], "item": LEAD[1], "lines": LEAD[2]},
            "energy_fraction": {"group": fixed(energy["group"], 3),
                                "random": [fixed(energy[f"random{j}"], 3) for j in range(c["random_frames"])]}}


def item_files(facts: Facts, repo: str, hf_home: str, c: dict, tensors: dict, cell_info: list[dict]) -> None:
    os.environ["HF_HOME"], os.environ["HF_HUB_OFFLINE"] = hf_home, "1"
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-0.8B")
    items = load_file(os.path.join(repo, ITEMS))
    piece = {}
    start = 0
    fill, widest, short = [], [], []                # how the paired texts are made, measured on the texts
    for info in cell_info:
        cell = info["key"]
        ids, cor = items[f"{cell}/ids"], items[f"{cell}/cor"]
        n = ids.shape[0]
        gate8, gate9 = tensors["gate/l8"][start:start + n], tensors["gate/l9"][start:start + n]
        out = []
        for i in range(n):
            texts = {}
            for name, row in (("clean", ids[i].tolist()), ("corrupt", cor[i].tolist())):
                for t in row:
                    if t not in piece:
                        piece[t] = tok.decode([t])
                pieces = [piece[t] for t in row]
                whole = tok.decode(row)
                assert "".join(pieces) == whole, (cell, i, name)
                assert all(ord(ch) < 127 and (ch == "\n" or ord(ch) >= 32) for ch in whole), (cell, i, name)
                texts[name] = pieces
            bits = {str(c["l8_transform"]): "".join("1" if v > 0 else "0" for v in gate8[i, :, 0].tolist())}
            for j, t in enumerate(c["l9_transforms"]):
                bits[str(t)] = "".join("1" if v > 0 else "0" for v in gate9[i, :, j].tolist())
            # characters in the line up to and including each token of the clean text, as the script labelled them; a token
            # before the first line break of the text has no known count
            chars = [int(v) for v in tensors["label/chars"][start + i].tolist()]
            known = "".join("1" if v > 0 else "0" for v in tensors["label/known"][start + i].tolist())
            count = 0
            for j, p in enumerate(texts["clean"]):
                count = 0 if p == "\n" else count + len(p)
                assert known[j] == "0" or chars[j] == count, (cell, i, j)
            out.append({"clean": texts["clean"], "corrupt": texts["corrupt"], "gate": bits, "chars": chars, "known": known})
            clean_text, corrupt_text = "".join(texts["clean"]), "".join(texts["corrupt"])
            clean_last, corrupt_last = clean_text.split("\n")[-1], corrupt_text.split("\n")[-1]
            assert clean_last.endswith(corrupt_last), (cell, i)                    # both texts end on the same words
            assert max(len(line) for line in clean_text.split("\n")[1:]) <= info["width"], (cell, i)
            short.append(info["width"] - len(clean_last))
            if info["kind"] == "count":
                assert len(corrupt_last) < len(clean_last), (cell, i)              # the corrupt last line starts at a later word
                assert max(len(line) for line in corrupt_text.split("\n")[1:]) <= info["width"], (cell, i)
                fill.append(len(corrupt_last) / info["width"])
            else:
                assert corrupt_last == clean_last, (cell, i)                        # the corrupt last line starts at the same word
                widest.append(max(len(line) for line in corrupt_text.split("\n")[1:]) / info["width"])
        start += n
        write(info["file"], {"sources": [ITEMS + " (token ids decoded with the Qwen3.5-0.8B tokenizer, one string per token)",
                                         RESULT_ST + " (gate/l8, gate/l9: gate open on the clean text, per token)"],
                             "attribution": "Re-wrapped excerpts from HuggingFaceFW/fineweb-edu, ODC-By 1.0.",
                             "cell": cell, "width": info["width"], "items": out})
    assert start == tensors["gate/l8"].shape[0]
    # the README's description of the paired texts, measured again on the decoded texts
    assert f"{min(fill) * 100:.0f}" == facts.items["demo.corrupt_fill_low"]["display"], min(fill)
    assert f"{max(fill) * 100:.0f}" == facts.items["demo.corrupt_fill_high"]["display"], max(fill)
    assert f"{max(widest):.2f}" == facts.items["demo.width_factor"]["display"], max(widest)
    assert max(short) == int(facts.items["demo.clean_short_max"]["display"]), max(short)
    print(f"corrupt texts: last line holds {min(fill):.3f} to {max(fill):.3f} of the width in the count cells; "
          f"longest line {max(widest):.2f} times the width in the width cell; the clean last line is at most {max(short)} characters short; "
          "equal to the README's description")
    print("every text: the per-token strings joined equal the decoded text; all characters are printable ASCII or line breaks")


# ---------------------------------------------------------------------------------------------- the Qwen3.5-4B set (optional)
def four_b(facts: Facts, repo: str, weights: str) -> dict:
    """rows per layer of the 4B set, and the facts of its section; every sentence of the README and of the 4B model card that a
    number is read from is matched by pattern, so a changed sentence stops the build"""
    f = facts
    manifest, fvu = json.loads(f.read(f"{REL4}/MANIFEST.json")), json.loads(f.read(f"{REL4}/reader_fvu.json"))
    with open(os.path.join(weights, "ALWAYS_ON.json")) as fh:
        always = json.load(fh)
    assert manifest["model"] == always["model"] == "Qwen/Qwen3.5-4B"
    n = len(manifest["layers"])
    assert len(fvu["layers"]) == n == len(always["layers"]) and len(fvu["splits"]) == 4
    rows = []
    for i in range(n):
        m, r, a = manifest["layers"][str(i)]["mlp"], fvu["layers"][str(i)], always["layers"][str(i)]
        mid, post, mlp = r[f"resid_mid.{i}"], r[f"resid_post.{i}"], r["mlp"]
        rows.append({
            "layer": i,
            "dropped": {"state_mid": fixed(mid["position_0_dropped"], 4), "state_post": fixed(post["position_0_dropped"], 4),
                        "mlp": fixed(mlp["position_0_dropped"], 4)},
            "with_p0": {"state_mid": fixed(mid["with_position_0"], 4), "state_post": fixed(post["with_position_0"], 4),
                        "mlp": fixed(mlp["with_position_0"], 4)},
            "mlp_train": fixed(m["heldout_fvu"], 4), "on_per_token": fixed(m["heldout_l0"], 1),
            "alive": m["alive"], "transforms": m["transforms"], "alive_text": f"{m['alive']} of {m['transforms']}",
            "penalty": f"{m['penalty']:.0e}",
            "always_web": len(a["on_90pct"]), "always_train": a["training_mix_heldout_counts"]["on_90pct"],
            "always_text": f"{len(a['on_90pct'])} / {a['training_mix_heldout_counts']['on_90pct']}",
            "always_energy": fixed(a["energy_share_on_90pct"], 2)})
    table = md_table(f.read(f"{REL4}/layers_table.md"), "Layer")
    assert len(table) == n
    for row, cells in zip(rows, table):
        mine = [str(row["layer"]), row["dropped"]["state_mid"], row["dropped"]["state_post"], row["dropped"]["mlp"], row["mlp_train"],
                row["on_per_token"], row["alive_text"], row["penalty"], row["always_text"]]
        assert mine == cells, (mine, cells)
    print(f"4B per-layer strings equal {REL4}/layers_table.md: {n} rows x {len(table[0])} columns")

    card = f"{REL4}/MODEL_CARD.md"
    f.add("b4.model", manifest["model"], f"{REL4}/MANIFEST.json", "model")
    f.add("b4.copied", manifest["frozen"], f"{REL4}/MANIFEST.json", "frozen (the date this copy was made, see note_frozen)")
    assert "was not frozen" in manifest["note_frozen"]
    f.add("b4.layers", str(n), f"{REL4}/MANIFEST.json", "number of layers")
    for key, field in (("b4.groups", "groups"), ("b4.group_size", "group_size"), ("b4.active", "k")):
        values = {manifest["layers"][str(i)]["state"][field] for i in range(n)}
        assert len(values) == 1
        f.add(key, comma(values.pop()), f"{REL4}/MANIFEST.json", f"layers.*.state.{field}, the same at every layer")
    assert f.items["b4.groups"]["display"] == f.items["state.groups"]["display"] and f.items["b4.active"]["display"] == f.items["state.active"]["display"]
    values = {r["transforms"] for r in rows}
    assert len(values) == 1
    f.add("b4.transforms", comma(values.pop()), f"{REL4}/MANIFEST.json", "layers.*.mlp.transforms, the same at every layer")
    assert len({r["penalty"] for r in rows}) == 1
    f.add("b4.penalty", rows[0]["penalty"], f"{REL4}/MANIFEST.json", "layers.*.mlp.penalty, the same at every layer")
    tokens, p0 = {v["tokens"] for v in fvu["layers"].values()}, {v["position_0_tokens"] for v in fvu["layers"].values()}
    assert len(tokens) == 1 and len(p0) == 1
    f.add("b4.fvu_tokens", comma(tokens.pop()), f"{REL4}/reader_fvu.json", "layers.*.tokens, the same at every layer")
    f.add("b4.always_differ_layers", str(sum(r["always_web"] != r["always_train"] for r in rows)), ALWAYS_ON,
          "number of layers at which the count on the web text sample differs from the count on the training-mix shard")

    f.find(README, r"\| `Qwen/Qwen3\.5-4B` \| (\d+) \| ([\d,]+) \| ([\d,]+) / (\d+) \| ([\d,]+) \| About (\d+) GiB \|",
           ["b4.layers_readme", "b4.width", "b4.groups_readme", "b4.active_readme", "b4.transforms_readme", "b4.total_gib"])
    for key in ("layers", "groups", "active", "transforms"):
        assert f.items.pop(f"b4.{key}_readme")["display"] == f.items[f"b4.{key}"]["display"], key
    f.find(README, r"The 4B set contains (\d+) weight and config files\. Its state dictionaries occupy about ([\d.]+) GiB, and its MLP dictionaries occupy about "
                   r"([\d.]+) GiB\.", ["b4.files", "b4.state_gib", "b4.mlp_gib"])
    f.find(card, r"Middle-layer state FVU is ([\d.]+) to ([\d.]+) for this set, against ([\d.]+) to ([\d.]+) for the 0\.8B set\. The proposed cause, the smaller "
                 r"active fraction of ([\d.]+)% against ([\d.]+)% of the width, is an inference, not a measurement\.",
           ["b4.mid_fvu_low", "b4.mid_fvu_high", "b4.mid_fvu_low_08b", "b4.mid_fvu_high_08b", "b4.active_pct", "b4.active_pct_08b"])
    f.find(card, r"The original project measured spliced-in loss at layer (\d+) only\. The other (\d+) layers were not measured\.", ["b4.probe_layer", "b4.unprobed_layers"])
    f.find(card, r"The original project chose the sparsity penalty at one layer only, layer (\d+)\. No other layer compared penalties\.", ["b4.penalty_layer"])
    assert f.items.pop("b4.penalty_layer")["display"] == f.items["b4.probe_layer"]["display"]
    f.find(card, r"the maximum was ([\d.]+) on the web text sample, at layer (\d+), and ([\d.]+) on the training-mix shard, at layer (\d+)\. On the training-mix shard "
                 r"the share was at least ([\d.]+) at (\d+) of 32 layers\.",
           ["b4.energy_max", "b4.energy_max_layer", "b4.energy_max_train", "b4.energy_max_train_layer", "b4.energy_floor", "b4.energy_layers"])
    best = max(rows, key=lambda r: float(r["always_energy"]))
    assert (best["always_energy"], str(best["layer"])) == (f.items["b4.energy_max"]["display"], f.items["b4.energy_max_layer"]["display"]), best
    f.find(card, r"and (\d+)% at layer 31, where ([\d,]+) of ([\d,]+) were alive\.", ["b4.dead_last_pct", "b4.alive_last", "b4.alive_last_of"])
    assert rows[-1]["alive_text"] == f"{f.items['b4.alive_last']['display'].replace(',', '')} of {f.items['b4.alive_last_of']['display'].replace(',', '')}"
    f.find(card, r"For the state dictionary at `resid_post\.16`, the original project recorded (\+[\d.]+) on held-out text the model itself answered, comprising "
                 r"(\d+) rows and ([\d,]+) positions\. On the same text, the MLP dictionary gave (\+[\d.]+)\.",
           ["b4.splice_state", "b4.splice_rows", "b4.splice_positions", "b4.splice_mlp"])
    for k in ("24", "40", "60"):
        f.find(card, rf"\| {k} \| ([\d.]+) \| (\+[\d.]+) \|", [f"b4.k{k}_fvu", f"b4.k{k}_splice"])
    assert f.items["b4.k24_splice"]["display"] == f.items["b4.splice_state"]["display"]
    for needle in ("The dictionaries trained with 40 and 60 active groups are not in this set.",
                   "No demonstration script exists for this set, and its trainers are not in the repository.",
                   "No unit of this set was read, edited or steered by the experiments behind the smaller companion's documents.",
                   "Nothing here supports a claim that this set's groups or transforms are interpretable in general.",
                   "This repository did not compare `capture` on 4B with the original project's capture.",
                   "This set covers one seed and one model.",
                   "They are not a statement about quality.",
                   "they cannot be re-run from the published files and code",
                   "The held-out activations behind this repository's FVU columns are not published."):
        assert needle in f.read(card), f"the 4B model card no longer holds: {needle}"
    return {"sources": [f"{REL4}/reader_fvu.json", f"{REL4}/MANIFEST.json", f"{REL4}/layers_table.md (compared, equal)", ALWAYS_ON],
            "columns": {"state_mid": "State FVU, resid_mid", "state_post": "State FVU, resid_post", "mlp": "MLP FVU",
                        "mlp_train": "MLP FVU recorded at training", "on_per_token": "MLP transforms on per token",
                        "alive": "MLP transforms alive", "penalty": "MLP penalty",
                        "always": "MLP transforms on at 90% of tokens or more (web text / training mix)",
                        "always_energy": "Share of the summed write energy carried by those transforms on the web text"},
            "rows": rows}


def source_commit(repo: str) -> dict:
    """the commit of the checkout the data was read from, and whether the files read differ from it (read-only git calls)"""
    import subprocess
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=True).stdout.strip()
    tracked = [README, CARD, MANIFEST, READER_FVU, f"{REL}/layers_table.md", f"{REL}/line_count_table.md", f"{REL}/line_count_link_table.md", SCRIPT, ITEMS,
               f"{REL4}/reader_fvu.json", f"{REL4}/MANIFEST.json", f"{REL4}/layers_table.md", f"{REL4}/MODEL_CARD.md"]
    return {"commit": git("rev-parse", "HEAD"), "date": git("log", "-1", "--format=%cI"),
            "files_modified_since_commit": [line[3:] for line in git("status", "--porcelain", "--", *tracked).splitlines()]}


def sha256(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--hf-home", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--weights-4b", help="folder of the Qwen3.5-4B weights repository that holds ALWAYS_ON.json; it adds the 4B section")
    args = ap.parse_args()
    torch.set_num_threads(4)
    os.makedirs(DATA, exist_ok=True)
    result_dir = args.result
    facts = Facts(args.repo)
    manifest, reader_fvu = json.loads(facts.read(MANIFEST)), json.loads(facts.read(READER_FVU))
    with open(os.path.join(result_dir, "result.json")) as f:
        result = json.load(f)
    tensors = load_file(os.path.join(result_dir, "result.safetensors"))
    items = load_file(os.path.join(args.repo, ITEMS))

    text_facts(facts, manifest, reader_fvu)
    constants = script_constants(facts)
    n_items, n_tokens = items[f"{constants['cells'][0]}/ids"].shape
    demo = demo_data(facts, constants, result, tensors, n_items, n_tokens)
    demo["source_sha256"] = {"result.json": sha256(os.path.join(result_dir, "result.json")),
                             "result.safetensors": sha256(os.path.join(result_dir, "result.safetensors")),
                             ITEMS: sha256(os.path.join(args.repo, ITEMS))}
    write("layers.json", layers_data(facts, manifest, reader_fvu))
    write("splice.json", splice_data(facts))
    write("demo.json", demo)
    item_files(facts, args.repo, args.hf_home, constants, tensors, demo["cells"])
    has_4b = all(os.path.exists(os.path.join(args.repo, REL4, name)) for name in ("reader_fvu.json", "MODEL_CARD.md"))
    if has_4b and args.weights_4b:
        write("layers-4b.json", four_b(facts, args.repo, args.weights_4b))
    else:
        if os.path.exists(os.path.join(DATA, "layers-4b.json")):
            os.remove(os.path.join(DATA, "layers-4b.json"))
        print("no Qwen3.5-4B section: " + ("--weights-4b was not given" if has_4b else f"{REL4}/reader_fvu.json or MODEL_CARD.md is not in the checkout"))
    write("facts.json", {"sources": sorted({v["source"] for v in facts.items.values()}), "source_commit": source_commit(args.repo),
                         "facts": facts.items})


if __name__ == "__main__":
    main()
