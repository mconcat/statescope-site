"""Data of the geometry figures and of the trace, read from the folders of five analyses (used by tools/build_data.py --geom).

Each analysis folder holds JSON files written by its own scripts; nothing is retyped here. Coordinates are kept as strings, and
every number that the page states in a sentence becomes a fact with the file and the field it was read from.

  line_count/   f_animation_keyframes.json, f_trace.json, m1_map.json, m1b_levels.json, m2_heads.json, m3_causal.json,
                f0_sheet_raw.json, f4_decision.json, f7_late_readouts.json           -> data/trace.json
  aba_abb/      figure_frame_plane.json, run3_shares.json                             -> data/geom-4b.json "aba"
  random_units/ data/story_lethality.json, story_tables.json, story_exemplification.json  -> data/geom-4b.json "lethality"
  compare_357/  figure_g9719_plane.json, rank_own_outcome.json, rank_spectrum.json    -> data/geom-4b.json "compare"
  steer_9167/   s2_hash_control.json, figure_9167.json                                -> data/geom-4b.json "steer"
"""
from __future__ import annotations

import json
import os
import statistics


def fixed(x: float, digits: int) -> str:
    s = f"{x:.{digits}f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def signed(x: float, digits: int) -> str:
    s = fixed(x, digits)
    return s if s.startswith("-") or float(s) == 0 else "+" + s


def load(folder: str, *rel: str) -> dict:
    with open(os.path.join(folder, *rel)) as f:
        return json.load(f)


# the rows of the trace table that the page shows: (row of f_trace.json, entries of its "numbers" in file order)
TRACE_ROWS = [(0, (0, 2, 7)), (1, (2,)), (2, (0, 4)), (3, (0, 1, 3)), (4, (6, 7)), (5, (0, 1, 2, 8)), (6, (0, 3)), (7, (0,)), (8, (0, 2)), (9, (2, 4, 5))]
# the stops of the animation: every key frame of the file is a measured state; the two mixer writes stored inside a key frame
# (before + write = after) give one more stop each, the state before the write seen in the same frame
CAUSAL_ARMS = {"clean": "clean", "shift40": "shift:40", "shift60": "shift:60", "perm40": "perm:40"}


def line_count(facts, folder: str, demo: dict) -> dict:
    src = lambda name: f"line_count/{name} (an analysis made for this page with the published reader and weights; not part of the repository)"
    add = lambda key, value, name, how: facts.add(key, value, src(name), how)
    kf = load(folder, "f_animation_keyframes.json")
    widths = [str(w) for w in kf["widths"]]
    frames = kf["keyframes"]
    assert [k["id"] for k in frames] == ["resid_post.8", "resid_mid.9", "resid_post.9", "resid_post.10", "resid_post.11", "resid_mid.12", "resid_post.12",
                                         "resid_mid.13", "resid_post.13", "resid_post.21"]
    # the cells every key frame has, per width (a run of consecutive counts)
    counts = {}
    for w in widths:
        common = set(frames[0]["cells"][w]["counts"])
        for k in frames:
            common &= set(k["cells"][w]["counts"])
        counts[w] = sorted(common)
        assert counts[w] == list(range(counts[w][0], counts[w][-1] + 1)) and len(counts[w]) >= 20, w
    stops = []
    for k in frames:
        cells, before = {}, {}
        for w in widths:
            c = k["cells"][w]
            at = {v: i for i, v in enumerate(c["counts"])}
            pts = [c["xyz_aligned"][at[v]] for v in counts[w]]
            cells[w] = {"x": [fixed(p[0], 3) for p in pts], "y": [fixed(p[1], 3) for p in pts]}
            if k.get("write"):
                wc = k["write"]["cells"][w]
                b = [wc["before_xyz_aligned"][at[v]] for v in counts[w]]
                d = [wc["write_xyz_aligned"][at[v]] for v in counts[w]]
                assert max(abs(b[i][j] + d[i][j] - pts[i][j]) for i in range(len(pts)) for j in range(3)) < 2e-3, (k["id"], w)   # before + write = after
                before[w] = {"x": [fixed(p[0], 3) for p in b], "y": [fixed(p[1], 3) for p in b]}
        geometry = {"by_count": fixed(k["geometry"]["by_count"], 2), "by_remaining": fixed(k["geometry"]["by_remaining"], 2)}
        if before:
            g0 = k["write"]["geometry_before"]
            # the state before the write is the previous key frame's state, seen in this key frame's frame
            stops.append({"id": frames[frames.index(k) - 1]["id"], "kind": "before", "group": k["view"]["group"], "curves": before,
                          "geometry": {"by_count": fixed(g0["by_count"], 2), "by_remaining": fixed(g0["by_remaining"], 2)}, "readouts": []})
        readouts = []
        for r in k.get("readouts", []):
            cross = {}
            for kind, per_width in r["crossings"].items():
                cross[kind] = {w: {"x": fixed(v["xyz_aligned"][0], 3), "y": fixed(v["xyz_aligned"][1], 3), "count": fixed(v["count"], 1),
                                   "remaining": fixed(v["remaining"], 1)} for w, v in per_width.items()}
            readouts.append({"layer": r["mlp_layer"], "transform": r["transform"], "direction": [fixed(v, 4) for v in r["direction_xyz_aligned"][:2]],
                             "crossings": cross, "r2": fixed(r["r2_gate_input_on_frame_part"], 2)})
        stops.append({"id": k["id"], "kind": "state", "group": k["view"]["group"], "curves": cells, "geometry": geometry, "readouts": readouts})
    assert len(stops) == 12
    for i, s in enumerate(stops):                                             # what each stop shows, as facts for its label
        add(f"lc.stop{i}_count", s["geometry"]["by_count"], "f_animation_keyframes.json", f"geometry.by_count of {s['id']} ({s['kind']})")
        add(f"lc.stop{i}_remaining", s["geometry"]["by_remaining"], "f_animation_keyframes.json", f"geometry.by_remaining of {s['id']} ({s['kind']})")
    by_id = {k["id"]: k for k in frames}
    res = [by_id[i]["procrustes"]["xyz"]["residual"] for i in ("resid_mid.9", "resid_mid.12")]
    others = [k["procrustes"]["xyz"]["residual"] for k in frames[2:] if k["id"] != "resid_mid.12"]
    add("lc.align_write9", fixed(res[0], 2), "f_animation_keyframes.json", "procrustes.xyz.residual of resid_mid.9")
    add("lc.align_write12", fixed(res[1], 2), "f_animation_keyframes.json", "procrustes.xyz.residual of resid_mid.12")
    add("lc.align_other_max", fixed(max(others), 2), "f_animation_keyframes.json", "largest procrustes.xyz.residual of the other key frames from resid_post.9 on")
    add("lc.keyframes", str(len(frames)), "f_animation_keyframes.json", "number of key frames")
    add("lc.stops", str(len(stops)), "f_animation_keyframes.json", "key frames plus the two states before a stored mixer write")
    import re
    m = re.match(r"(\d+) documents x (\d+) widths, (\d+) tokens each", kf["source"])
    add("lc.documents", m.group(1), "f_animation_keyframes.json", "source")
    add("lc.doc_tokens", m.group(3), "f_animation_keyframes.json", "source")
    add("lc.widths", ", ".join(widths[:-1]) + " and " + widths[-1], "f_animation_keyframes.json", "widths")
    add("lc.n_widths", {5: "five"}[len(widths)], "f_animation_keyframes.json", "number of widths, as a word")

    def crossings(site: str, transform: int, kind: str, field: str) -> list[float]:
        r = next(x for x in by_id[site]["readouts"] if x["transform"] == transform)
        return [v[field] for v in r["crossings"][kind].values()]

    c = demo["constants"]
    short, long_ = c["l9_transforms"]
    up = crossings("resid_mid.9", long_, "up", "count")
    add("lc.t1749_on_low", fixed(min(up), 0), "f_animation_keyframes.json", f"smallest up-crossing count of transform {long_} at resid_mid.9")
    add("lc.t1749_on_high", fixed(max(up), 0), "f_animation_keyframes.json", f"largest up-crossing count of transform {long_}")
    r410 = next(x for x in by_id["resid_mid.9"]["readouts"] if x["transform"] == short)
    add("lc.t410_on_slope", fixed(r410["level_set"]["up"]["a"], 2), "f_animation_keyframes.json", f"level_set.up.a of transform {short}: count at which it switches on = a W + b")
    down = crossings("resid_mid.9", short, "down", "count")
    add("lc.t410_off_low", fixed(min(down), 0), "f_animation_keyframes.json", f"smallest down-crossing count of transform {short}")
    add("lc.t410_off_high", fixed(max(down), 0), "f_animation_keyframes.json", f"largest down-crossing count of transform {short}")
    for site, t, key in (("resid_mid.12", 2069, "t2069"), ("resid_mid.13", 2490, "t2490")):
        rem = crossings(site, t, "up", "remaining")
        add(f"lc.{key}", str(t), "f_animation_keyframes.json", f"the main read-out transform at {site}")
        add(f"lc.{key}_rem_low", fixed(min(rem), 0), "f_animation_keyframes.json", f"smallest remaining characters at the up-crossing of transform {t}")
        add(f"lc.{key}_rem_high", fixed(max(rem), 0), "f_animation_keyframes.json", f"largest remaining characters at the up-crossing of transform {t}")
        add(f"lc.{key}_r2", fixed(next(x for x in by_id[site]["readouts"] if x["transform"] == t)["r2_gate_input_on_frame_part"], 2), "f_animation_keyframes.json",
            f"r2_gate_input_on_frame_part of transform {t}")
    for site, key in (("resid_post.8", "g8"), ("resid_mid.9", "g9"), ("resid_post.10", "g10"), ("resid_post.11", "g11"), ("resid_mid.12", "g12"), ("resid_post.13", "g13")):
        add(f"lc.{key}", str(by_id[site]["view"]["group"]), "f_animation_keyframes.json", f"view.group of {site}")
    assert by_id["resid_mid.9"]["view"]["group"] == c["l9_group"]
    after = kf["after_the_last_key_frame"]
    cells = [x["key"] for x in demo["cells"]]
    for cell in cells:
        tag = cell.replace(":", "")
        add(f"lc.h15_direct.{tag}", fixed(after["direct_share_of_the_margin_difference"][cell], 2), "f_animation_keyframes.json", f"after_the_last_key_frame.direct_share_of_the_margin_difference.{cell}")
        add(f"lc.h15_net.{tag}", fixed(after["net_share_with_everything_downstream"][cell], 2), "f_animation_keyframes.json", f"after_the_last_key_frame.net_share_with_everything_downstream.{cell}")

    # the trace table
    tr = load(folder, "f_trace.json")
    assert tr["cells"] == cells
    table = []
    for row, entries in TRACE_ROWS:
        r = tr["rows"][row]
        names = list(r["numbers"])
        table.append({"step": row + 1, "entries": [{"source_label": names[e], "shares": [fixed(v, 2) for v in r["numbers"][names[e]]]} for e in entries]})

    # numbers of single measurements
    m1, m1b, m2, m3 = load(folder, "m1_map.json"), load(folder, "m1b_levels.json"), load(folder, "m2_heads.json"), load(folder, "m3_causal.json")
    f0, f4, f7 = load(folder, "f0_sheet_raw.json"), load(folder, "f4_decision.json"), load(folder, "f7_late_readouts.json")
    resid = [s for s in m1["sites"] if s.startswith("resid_") and 8 <= int(s.split(".")[1]) <= 13]
    add("lc.components_max", str(max(v["n95_cv"] for s in resid for v in m1["sites"][s]["by_width"].values())), "m1_map.json",
        "largest n95_cv (components for 95 % of the cross-validated variance of the mean curve) at the residual sites of layers 8 to 13")
    add("lc.components_min", str(min(v["n95_cv"] for s in resid for v in m1["sites"][s]["by_width"].values())), "m1_map.json", "smallest n95_cv at the same sites")
    shares = [v["top_groups_by_even_documents"][0][1] for site in m1b["groups"].values() for v in site.values()]
    add("lc.frame_low", fixed(min(shares), 2), "m1b_levels.json", "smallest share of the count curve inside the best group's frame, residual sites of layers 8 to 13")
    add("lc.frame_high", fixed(max(shares), 2), "m1b_levels.json", "largest such share")
    h10, h13, h12 = m2["layers"]["9"]["heads"]["10"], m2["layers"]["12"]["heads"]["13"], m2["layers"]["8"]["heads"]["12"]
    slopes = [abs(v) for v in h10["clock_slope_per_char"].values()]
    add("lc.clock_low", fixed(min(slopes), 3), "m2_heads.json", "layers.9.heads.10.clock_slope_per_char, smallest over the widths")
    add("lc.clock_high", fixed(max(slopes), 3), "m2_heads.json", "largest")
    add("lc.clock_r2", fixed(min(h10["clock_r2"].values()), 3), "m2_heads.json", "layers.9.heads.10.clock_r2, smallest over the widths")
    add("lc.beta_first", fixed(h10["beta"]["first_token"], 3), "m2_heads.json", "layers.9.heads.10.beta.first_token")
    add("lc.h10_curve", fixed(m2["layers"]["9"]["count_share_by_head"][10], 2), "m2_heads.json", "layers.9.count_share_by_head[10]")
    add("lc.h13_curve", fixed(m2["layers"]["12"]["count_share_by_head"][13], 2), "m2_heads.json", "layers.12.count_share_by_head[13]")
    add("lc.h13_gate_fixed", fixed(h13["zfix"]["size_ratio"], 2), "m2_heads.json", "layers.12.heads.13.zfix.size_ratio")
    add("lc.h13_decay", fixed(abs(statistics.mean(h13["clock_slope_per_char"].values())), 3), "m2_heads.json", "layers.12.heads.13.clock_slope_per_char, mean over the widths")
    del h12
    early = ["resid_post.8", "resid_mid.9", "resid_post.9", "resid_post.10", "resid_post.11"]
    ratio = [f0["sites"][s]["tangents"]["size_dW_over_size_dc"] for s in early]
    orth = [f0["sites"][s]["tangents"]["orthogonal_share_of_dW"] for s in early]
    add("lc.sheet_ratio_low", fixed(min(ratio), 2), "f0_sheet_raw.json", "tangents.size_dW_over_size_dc, smallest at the sites from resid_post.8 to resid_post.11")
    add("lc.sheet_ratio_high", fixed(max(ratio), 2), "f0_sheet_raw.json", "largest")
    add("lc.sheet_orth_low", fixed(min(orth), 2), "f0_sheet_raw.json", "tangents.orthogonal_share_of_dW, smallest at the same sites")
    add("lc.sheet_orth_high", fixed(max(orth), 2), "f0_sheet_raw.json", "largest")
    late = [f0["sites"][s]["models"]["r (one-hot)"] for s in ("resid_mid.12", "resid_post.12", "resid_post.13")]
    add("lc.remaining_low", fixed(min(late), 2), "f0_sheet_raw.json", "models['r (one-hot)'] at resid_mid.12, resid_post.12, resid_post.13: smallest")
    add("lc.remaining_high", fixed(max(late), 2), "f0_sheet_raw.json", "largest")
    fits = [m1b["levels"][s]["components"]["1"]["first"] for s in m1b["levels"] if s not in ("mix.8", "resid_post.8", "mix.9", "resid_mid.9", "mlp.9", "resid_post.9", "mix.10", "resid_post.10", "resid_post.11", "mix.12")]
    assert all(0.9 <= f["a"] <= 1.05 for f in fits), [f["a"] for f in fits]
    add("lc.before_end_low", fixed(min(-f["b"] for f in fits), 0), "m1b_levels.json", "level crossing of the first component from the layer-12 MLP on, c* = a W + b: smallest -b")
    add("lc.before_end_high", fixed(max(-f["b"] for f in fits), 0), "m1b_levels.json", "largest -b")
    t100 = m3["targets"]["100"]["arms"]
    add("lc.cz_tokens", f"{m3['targets']['100']['tokens']:,}", "m3_causal.json", "targets.100.tokens")
    bump = t100["shift:40"]["bump_count"]
    add("lc.cz_bump_count", str(bump), "m3_causal.json", "targets.100.arms['shift:40'].bump_count")
    add("lc.cz_bump_margin", fixed(t100["shift:40"]["bump_margin"], 1), "m3_causal.json", "targets.100.arms['shift:40'].bump_margin")
    add("lc.cz_clean_there", fixed(t100["clean"]["mean_margin_by_count_every5"][str(bump)], 1), "m3_causal.json", "the clean arm's mean margin at the same count")
    add("lc.cz_perm_there", fixed(t100["perm:40"]["mean_margin_by_count_every5"][str(bump)], 1), "m3_causal.json", "the permuted-channel arm's mean margin at the same count")
    add("lc.cz_end_clean", signed(t100["clean"]["mean_margin_remaining_0_2"], 1), "m3_causal.json", "targets.100.arms.clean.mean_margin_remaining_0_2")
    add("lc.cz_end_shift", fixed(t100["shift:40"]["mean_margin_remaining_0_2"], 1), "m3_causal.json", "targets.100.arms['shift:40'].mean_margin_remaining_0_2")
    add("lc.cz_cstar_clean", fixed(t100["clean"]["c_star"], 0), "m3_causal.json", "targets.100.arms.clean.c_star (level -3)")
    add("lc.cz_cstar_shift40", fixed(t100["shift:40"]["c_star"], 0), "m3_causal.json", "targets.100.arms['shift:40'].c_star")
    add("lc.cz_cstar_shift60", fixed(t100["shift:60"]["c_star"], 0), "m3_causal.json", "targets.100.arms['shift:60'].c_star")
    add("lc.cz_cstar_perm", fixed(t100["perm:40"]["c_star"], 0), "m3_causal.json", "targets.100.arms['perm:40'].c_star")
    add("lc.cz_read_const_end", fixed(t100["own_mean"]["mean_margin_remaining_0_2"], 1), "m3_causal.json", "targets.100.arms.own_mean.mean_margin_remaining_0_2")
    xs = sorted(int(v) for v in t100["clean"]["mean_margin_by_count_every5"])
    causal = {"counts": [str(v) for v in xs], "arms": {k: [fixed(t100[a]["mean_margin_by_count_every5"][str(v)], 2) for v in xs] for k, a in CAUSAL_ARMS.items()},
              "width": "100", "donors": {"shift40": "40", "shift60": "60", "perm40": "40"}}
    t130 = f7["units"]["mlp20/t130"]
    add("lc.t130_rem_low", fixed(min(t130["crossing_fit"]["remaining_at_crossing"]), 1), "f7_late_readouts.json", "units['mlp20/t130'].crossing_fit.remaining_at_crossing, smallest")
    add("lc.t130_rem_high", fixed(max(t130["crossing_fit"]["remaining_at_crossing"]), 1), "f7_late_readouts.json", "largest")
    add("lc.t130_group", str(t130["groups"][0]["group"]), "f7_late_readouts.json", "units['mlp20/t130'].groups[0].group")
    for name in ("mlp20/t130", "mlp23/t2369"):                                 # the late transforms the page names
        assert name in f7["units"]
        add(f"lc.{name.split('/')[1]}", name.split("/t")[1], "f7_late_readouts.json", f"units['{name}']")
    add("lc.h15_remaining", fixed(f4["units"]["L21h15"]["r_only"], 2), "f4_decision.json", "units.L21h15.r_only")
    print(f"trace: {len(stops)} stops, {sum(len(v) for v in counts.values())} cells per stop, {sum(len(r['entries']) for r in table)} table entries")
    return {"sources": [src(n) for n in ("f_animation_keyframes.json", "f_trace.json", "m3_causal.json")], "widths": widths,
            "counts": {w: [str(counts[w][0]), str(counts[w][-1])] for w in widths}, "stops": stops, "table": table, "cells": cells, "causal": causal}


def four_b_geometry(facts, root: str) -> dict:
    out = {"sources": []}

    def source(name: str) -> str:
        s = f"{name} (an analysis made for this page with the published reader and weights; not part of the repository)"
        if s not in out["sources"]:
            out["sources"].append(s)
        return s

    # ---- the ABA / ABB rule variable: the plane of group 12487 at resid_post.14 and head 14's two read directions
    fig = load(root, "aba_abb", "figure_frame_plane.json")
    second = fig["second_frame_read_by_layer15_head14"]
    add = lambda key, value, how, name="aba_abb/figure_frame_plane.json": facts.add(key, value, source(name), how)
    conds = []
    for c in second["conditions"]:
        entry = {"name": c["name"], "kind": c["kind"], "n": str(c["n_tokens"]), "common": fixed(c["mean"][0], 1), "rule": fixed(c["mean"][1], 1)}
        if c["kind"] != "line":
            step = max(1, len(c["points"]) // 80)
            entry["points"] = [[fixed(p[0], 1), fixed(p[1], 1)] for p in c["points"][::step]]
        conds.append(entry)
    by = {c["name"]: c for c in conds}
    import re
    assert re.search(r"group (\d+) of layer (\d+), site resid_post\.(\d+)", second["what"]).groups() == ("12487", "14", "14")
    add("aba.group", "12487", "second_frame_read_by_layer15_head14.what")
    add("aba.site_layer", "14", "second_frame_read_by_layer15_head14.what")
    for name, key in (("task ABA", "aba"), ("task ABB", "abb"), ("task ABC", "ctrl"), ("sentence, repeated noun", "noun"), ("sentence, new noun", "newnoun")):
        add(f"aba.{key}_common", by[name]["common"], f"conditions['{name}'].mean[0]")
        add(f"aba.{key}_rule", signed(float(by[name]["rule"]), 1), f"conditions['{name}'].mean[1]")
    back1 = [float(c["rule"]) for c in conds if c["kind"] == "line" and c["name"].endswith("lag 1")]
    earlier = [float(c["rule"]) for c in conds if c["kind"] == "line" and int(c["name"].split("lag ")[1]) >= 2]
    add("aba.back1_low", fixed(min(back1), 1), "smallest rule coordinate of the list conditions that repeat the item just before")
    add("aba.back1_high", fixed(max(back1), 1), "largest")
    add("aba.earlier_low", signed(min(earlier), 1), "smallest rule coordinate of the list conditions that repeat an earlier item")
    add("aba.earlier_high", signed(max(earlier), 1), "largest")
    add("aba.line_conditions", str(sum(c["kind"] == "line" for c in conds)), "number of list conditions")
    heads = second["head14_value_path_in_this_frame"][:2]
    assert abs(heads[0]["read_direction_on_common_axis"]) > 0.9 and abs(heads[1]["read_direction_on_rule_axis"]) > 0.85
    for i, h in enumerate(heads, start=1):
        add(f"aba.read{i}_gain", fixed(h["gain"], 3), f"head14_value_path_in_this_frame[{i - 1}].gain")
        add(f"aba.read{i}_inside", fixed(h["share_of_read_direction_inside_plane"], 2), f"head14_value_path_in_this_frame[{i - 1}].share_of_read_direction_inside_plane")
    dest1 = max(heads[0]["write_share_inside_destination_frames"].items(), key=lambda kv: kv[1])
    dest2 = sorted(heads[1]["write_share_inside_destination_frames"].items(), key=lambda kv: -kv[1])[:2]
    add("aba.read1_dest", dest1[0], "the destination frame with the largest share of the first direction's write")
    add("aba.read1_dest_share", fixed(dest1[1], 2), "that share")
    add("aba.read2_dest_a", dest2[0][0], "the destination frame with the largest share of the second direction's write")
    add("aba.read2_dest_b", dest2[1][0], "the second largest")
    add("aba.random_gain", fixed(second["gain_on_random_unit_directions"]["median"], 3), "gain_on_random_unit_directions.median")
    add("aba.random_gain_max", fixed(second["gain_on_random_unit_directions"]["max"], 3), "gain_on_random_unit_directions.max")
    sel = fig["stability"]["selected_rate_test"]
    add("aba.g13", "12112", "the group of the first block (resid_post.13)")
    add("aba.sel_aba", fixed(sel["ABA"], 2), "stability.selected_rate_test.ABA (group 12112 at resid_post.13)")
    add("aba.sel_abb", fixed(sel["ABB"], 2), "stability.selected_rate_test.ABB")
    add("aba.sel_ctrl", fixed(sel["ABC"], 3), "stability.selected_rate_test.ABC")
    shares = load(root, "aba_abb", "run3_shares.json")
    rules = ("ABA->ABB|", "ABB->ABA|")                                        # the prompt's rule moved to the other rule
    moved = [v2["share_of_natural_difference"] for k, v in shares.items() if k.startswith(rules) and k.endswith("|group 12487") for v2 in v["frames"].values()]
    rand = [v2["share_of_natural_difference"] for k, v in shares.items() if k.startswith(rules) and "random" in k for v2 in v["frames"].values()]
    assert len(moved) == 8 and len(rand) == 8, (len(moved), len(rand))
    add("aba.move_low", fixed(min(moved), 2), "smallest share_of_natural_difference in the destination frames, shift inside group 12487's frame", "aba_abb/run3_shares.json")
    add("aba.move_high", fixed(max(moved), 2), "largest", "aba_abb/run3_shares.json")
    add("aba.move_random_low", fixed(min(rand), 2), "the same for a random 4-dimensional frame: smallest", "aba_abb/run3_shares.json")
    add("aba.move_random_high", fixed(max(rand), 2), "largest", "aba_abb/run3_shares.json")
    out["aba"] = {"group": 12487, "site": "resid_post.14", "conditions": conds,
                  "reads": [{"common": fixed(h["read_direction_on_common_axis"], 3), "rule": fixed(h["read_direction_on_rule_axis"], 3), "gain": fixed(h["gain"], 3)} for h in heads]}

    # ---- many example lines: the state at the answer position as a running average
    bel = load(root, "aba_abb", "b_belief_figure.json")
    add = lambda key, value, how, name="aba_abb/b_belief_figure.json": facts.add(key, value, source(name), how)
    hist = bel["histories"]
    lines = len(hist[0]["types"])
    assert len(hist) == 3 ** lines and "resid_mid.15" in bel["what"]
    add("avg.lines", {6: "six"}[lines], "number of example lines of a history, as a word")
    add("avg.histories", str(len(hist)), "number of histories")
    explained = bel["inside_the_examples"]["fin|mid.15"]["explained"]
    add("avg.count_distance", fixed(explained["count distance"], 2), "inside_the_examples['fin|mid.15'].explained['count distance']")
    add("avg.shared_suffix", fixed(explained["shared suffix length"], 2), "inside_the_examples['fin|mid.15'].explained['shared suffix length']")
    h14 = bel["head14"]
    add("avg.attention_third", fixed(h14["attention_to_third_items_total"]["mean"], 2), "head14.attention_to_third_items_total.mean")
    add("avg.mixture_r2", fixed(h14["mixture_r2_for_head14_third_item_write_heldout"], 2), "head14.mixture_r2_for_head14_third_item_write_heldout")
    add("avg.equal_r2", fixed(h14["equal_attention_r2_for_head14_third_item_write_heldout"], 2), "head14.equal_attention_r2_for_head14_third_item_write_heldout")
    attention = list(reversed(h14["attention_by_line_from_last_back"]["all"]))   # first line first
    assert len(attention) == lines
    for i, v in enumerate(attention, start=1):
        add(f"avg.attention_{i}", fixed(v, 2), f"head14.attention_by_line_from_last_back.all, line {i} counted from the first")
    add("avg.attention_first", fixed(attention[0], 2), "head14.attention_by_line_from_last_back.all, the first line")
    add("avg.answer_r2", fixed(bel["answer_from_plane_r2_heldout"]["ld"]["affine"], 2), "answer_from_plane_r2_heldout.ld.affine")
    for g, info in bel["frames"]["first_part_frames"].items():
        add(f"avg.rank_{g}", str(info["rank_on_fit_half"]), f"frames.first_part_frames['{g}'].rank_on_fit_half")
    stair = bel["selection_staircase"]["14020"]["selected_share_by_number_of_A_lines_others_C"]
    for i, v in enumerate(stair):
        add(f"avg.stair{i}", fixed(v, 2), f"selection_staircase['14020'].selected_share_by_number_of_A_lines_others_C[{i}]")
    slopes = load(root, "aba_abb", "b_trace.json")["fin|mid.15"]["one_map_per_type"]["scalar_slope_by_parent_length_fit_and_heldout"]
    for m in (2, 3, 4, 5):                                                     # a child of m + 1 lines against its parent of m lines
        value = statistics.mean(slopes[str(m)])
        facts.add(f"avg.shrink{m}", fixed(value, 2), source("aba_abb/b_trace.json"), f"['fin|mid.15'].one_map_per_type.scalar_slope_by_parent_length_fit_and_heldout['{m}'], mean of the two halves")
        facts.add(f"avg.ideal{m}", fixed(m / (m + 1), 2), "tools/geom_data.py", f"m / (m + 1) for m = {m}: the shrink of an exact running average")
    out["average"] = {"site": "resid_mid.15",
                      "histories": [{"types": x["types"], "x": fixed(x["plane_heldout"][0], 2), "y": fixed(x["plane_heldout"][1], 2), "d": str(x["counts"][0] - x["counts"][1])} for x in hist],
                      "corners": {k: [fixed(v["plane_heldout"][0], 2), fixed(v["plane_heldout"][1], 2)] for k, v in bel["vertices"].items()},
                      "attention": [fixed(v, 2) for v in attention]}

    # ---- a unit drawn at random: group 15417 at resid_post.27
    story = load(root, "random_units", "data", "story_lethality.json")
    add = lambda key, value, how, name="random_units/data/story_lethality.json": facts.add(key, value, source(name), how)
    assert story["unit"] == "resid_post.27 group 15417"
    words = [{"word": w["word"], "c4": fixed(w["code_it_was_a"][3], 1), "c2": fixed(w["code_it_was_a"][1], 1)} for w in story["word_map"]]
    wm = {w["word"]: w for w in story["word_map"]}
    add("leth.group", "15417", "unit")
    add("leth.layer", "27", "unit")
    add("leth.words", str(len(words)), "number of adjectives in word_map")
    for w in ("fatal", "deadly", "lethal", "crucial", "safe", "alive", "vital"):
        add(f"leth.{w}", signed(wm[w]["code_it_was_a"][3], 1), f"word_map['{w}'].code_it_was_a[3]")
    for w in ("vital", "fatal", "pivotal"):
        add(f"leth.c2_{w}", fixed(wm[w]["code_it_was_a"][1], 1), f"word_map['{w}'].code_it_was_a[1]")
    moves = {}
    for m in story["moves"]:
        if m["destination"] == "vital":
            moves.setdefault(m["mode"], []).append((m["margin_after"] - m["margin_clean"], m["margin_source_clean"] - m["margin_clean"]))
    a4 = moves["axis4"]
    add("leth.pairs", str(len(a4)), "number of pairs ('vital' moved to a death word, same sentence frame)")
    add("leth.move", signed(statistics.mean(x for x, _ in a4), 2), "moves, mode axis4, destination vital: mean change of the margin")
    add("leth.move_toward", str(sum(x * g > 0 for x, g in a4)), "number of those pairs in which the margin moves toward the source word")
    add("leth.move_share", fixed(statistics.mean(x for x, _ in a4) / statistics.mean(g for _, g in a4), 2), "that change over the mean gap between the two words")
    others = [statistics.mean(x for x, _ in moves[k]) for k in moves if k.startswith(("inframe_rand", "outside"))]
    add("leth.other_low", signed(min(others), 2), "moves of the same size along random directions inside and outside the frame: smallest mean change")
    add("leth.other_high", signed(max(others), 2), "largest")
    out["lethality"] = {"group": 15417, "site": "resid_post.27", "words": words}
    tables = load(root, "random_units", "data", "story_tables.json")
    add = lambda key, value, how, name="random_units/data/story_tables.json": facts.add(key, value, source(name), how)
    more = [r["frame_coords"][3] for r in tables["uniform"] if r["another_column_follows"]]
    last = [r["frame_coords"][3] for r in tables["uniform"] if not r["another_column_follows"] and r["K"] > 1]
    add("tab.group", "15613", "units")
    add("tab.layer", "15", "units")
    add("tab.more_low", fixed(min(more), 1), "uniform: fourth frame coordinate when another column follows, smallest")
    add("tab.more_high", fixed(max(more), 1), "largest")
    add("tab.last_low", fixed(min(last), 1), "uniform: fourth frame coordinate on the last column, smallest")
    add("tab.last_high", fixed(max(last), 1), "largest")
    route = [r["share_mean"] for r in tables["twin_frame_patch"] if r["mode"] == "frame"]
    add("tab.route", fixed(max(abs(v) for v in route), 2), "twin_frame_patch, mode frame: largest absolute share of the margin gap")
    re_aim = next(r for r in tables["reaim"] if r["mode"] == "full")
    add("tab.reaim", str(re_aim["moved"]), "reaim, mode full: moved")
    add("tab.reaim_n", str(re_aim["n"]), "reaim, mode full: n")
    h4 = next(r for r in tables["twin_head_patch"] if r["set"] == "L15:h4")
    add("tab.head4", fixed(h4["p4_share"], 2), "twin_head_patch['L15:h4'].p4_share")
    ex = load(root, "random_units", "data", "story_exemplification.json")
    add = lambda key, value, how, name="random_units/data/story_exemplification.json": facts.add(key, value, source(name), how)
    assert ex["unit"].endswith("group 87"), ex["unit"]
    add("ex.group", "87", "unit")
    add("ex.layer", "13", "unit")
    patch = next(r for r in ex["frame_patch"] if r["direction"] != "cat<-agent" and r["positions"] == "all" and r["mode"] == "frame")
    add("ex.move", signed(patch["mean"], 2), "frame_patch: the agent prompt moved to the category twin's coordinates inside the frame, mean change of the margin")
    add("ex.pairs", str(len(patch["margin_change_per_pair"])), "number of twin pairs")

    # ---- the comparison at layer 7: the plane of group 9719 and the read directions of transforms 357 and 472
    plane = load(root, "compare_357", "figure_g9719_plane.json")
    add = lambda key, value, how, name="compare_357/figure_g9719_plane.json": facts.add(key, value, source(name), how)
    lc = plane["list_cells"]
    cells = [{"cur": lc["cur"][i], "prev": lc["prev"][i], "outcome": lc["outcome"][i], "x": fixed(lc["xy"][i][0], 2), "y": fixed(lc["xy"][i][1], 2)} for i in range(len(lc["cur"]))]
    d357, d472 = plane["read"]["357"], plane["read"]["472"]
    dot = sum(a * b for a, b in zip(d357["direction_in_frame"], d472["direction_in_frame"])) / (d357["size"] * d472["size"])
    add("cmp.group", str(plane["group"]), "group")
    add("cmp.cells", str(len(cells)), "number of list cells")
    add("cmp.cosine", fixed(dot, 2), "cosine of the two read directions inside the frame (read.357.direction_in_frame, read.472.direction_in_frame)")
    add("cmp.inside_357", fixed(d357["share_of_direction_inside_plane"], 2), "read.357.share_of_direction_inside_plane")
    add("cmp.inside_472", fixed(d472["share_of_direction_inside_plane"], 2), "read.472.share_of_direction_inside_plane")
    add("cmp.plane_share", fixed(sum(plane["plane"]["variance_share"][:2]), 2), "plane.variance_share, first two summed")
    own = load(root, "compare_357", "rank_own_outcome.json")["sets"]
    for t in ("357", "472"):
        for fam in ("list", "js"):
            facts.add(f"cmp.fixed_{t}_{fam}", fixed(own[f"{t}/{fam}/own_outcome"]["share_of_squared_norm"]["in_the_mean_write_direction"], 2),
                      source("compare_357/rank_own_outcome.json"), f"sets['{t}/{fam}/own_outcome'].share_of_squared_norm.in_the_mean_write_direction")
    spectrum = load(root, "compare_357", "rank_spectrum.json")["transforms"]
    facts.add("cmp.rank_357", str(spectrum["357"]["rank"]), source("compare_357/rank_spectrum.json"), "transforms.357.rank")
    out["compare"] = {"group": plane["group"], "site": plane["site"], "cells": cells,
                      "reads": {t: [fixed(v, 4) for v in plane["read"][t]["direction_in_plane"]] for t in ("357", "472")},
                      "centroids": {k: [fixed(v[0], 2), fixed(v[1], 2)] for k, v in plane["outcome_centroids"].items()}}

    # ---- the steering unit: three rates of one run
    ctl = load(root, "steer_9167", "s2_hash_control.json")
    add = lambda key, value, how, name="steer_9167/s2_hash_control.json": facts.add(key, value, source(name), how)
    add("st.prompts", str(ctl["n_prompts"]), "n_prompts")
    bars = []
    for key, cond in (("base", "base"), ("move", "move"), ("forced", "hash")):
        r = ctl["conditions"][cond]["correct_rule"]
        add(f"st.{key}", fixed(r[0], 3), f"conditions.{cond}.correct_rule[0]")
        add(f"st.{key}_low", fixed(r[1], 2), f"conditions.{cond}.correct_rule[1]")
        add(f"st.{key}_high", fixed(r[2], 2), f"conditions.{cond}.correct_rule[2]")
        bars.append({"key": key, "value": fixed(r[0], 3), "lo": fixed(r[1], 2), "hi": fixed(r[2], 2)})
    path = {fixed(p["dose"], 1): p["first_choice_hash"] for p in load(root, "steer_9167", "figure_9167.json")["move_path_code_only_prompts"]}
    for dose in ("1.0", "2.0", "4.0"):
        facts.add(f"st.hash_dose{dose[0]}", fixed(path[dose], 2), source("steer_9167/figure_9167.json"), f"move_path_code_only_prompts, dose {dose}: first_choice_hash")
    out["steer"] = {"bars": bars}
    return out
