"""Build the comparison tables and generated-line figure from the measured runs."""

import csv
import json
from decimal import Decimal, ROUND_HALF_UP


def read(path):
    return json.loads(path.read_text())


def interval(value, bounds, fmt):
    return f"{fmt(value)} [{fmt(bounds[0])}, {fmt(bounds[1])}]"


def state_subspaces(repo):
    source = "docs/l9-state-subspaces.csv"
    with (repo / source).open() as file:
        measurements = list(csv.DictReader(file))
    rows = {}
    conditions = list(dict.fromkeys(m["condition"] for m in measurements))
    for m in measurements:
        values = [float(m[key]) for key in ("fraction_retained", "paired_bootstrap_95_low", "paired_bootstrap_95_high")]
        rows.setdefault(m["subspace"], {})[m["condition"]] = interval(values[0], values[1:], lambda x: f"{100 * x:.1f}")
    counts = {int(m["new_document_pairs"]) for m in measurements}
    assert len(counts) == 1 and all(list(row) == conditions for row in rows.values())
    per_condition = counts.pop()
    return {
        "sources": [source],
        "conditions": conditions,
        "pairs": per_condition * len(conditions),
        "per_condition": per_condition,
        "rows": rows,
    }


def width_edit(root, public_rows, facts):
    folder = root / "line_count"
    m6 = read(folder / "m6_frame_edit.json")
    extra = read(folder / "m7_extra.json")
    # The public demonstration supplies the point estimates. The research run supplies intervals and curves.
    rows = []
    keys = ["clean", "shift:40", "perm:40", "in_frame:40", "rest:40", "state_gated:40", "state_randdir0:40"]
    for arm, (name, size, crossing, margin, end) in zip(keys, public_rows, strict=True):
        row = dict(arm=arm, label=name, size=size, crossing=crossing, margin=margin, end=end)
        if arm in extra["arms"]:
            boot = extra["arms"][arm]
            for field, ci, digits in (
                ("crossing", "c_star_ci95_over_resamples_with_a_crossing", 1),
                ("margin", "mean_margin_48_50_ci95", 2),
            ):
                row[field] = interval(
                    float(row[field]),
                    boot[ci],
                    lambda x: str(Decimal(str(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)),
                )
        rows.append(row)
    arms = m6["arms"]
    verdict = m6["verdicts"]["40"]["frame_carries_the_head_edit"]
    share = m6["share_of_m3_delta_squared_norm_inside_frame"]["40"]
    controls = [arms[k] for k in m6["arm_names"]["40"]["arm3_rule_controls"]]
    measures = {
        "documents": extra["documents"],
        "control_margin": f"{min(c['mean_margin_count_48_50'] for c in controls):.2f} to {max(c['mean_margin_count_48_50'] for c in controls):.2f}",
        "control_end": f"{min(c['mean_margin_at_true_breaks'] for c in controls):+.2f} to {max(c['mean_margin_at_true_breaks'] for c in controls):+.2f}",
        "rest_rise": f"{verdict['rise_rest']:+.2f}",
        "perm_rise": f"{verdict['descriptive_rise_other_arms']['perm:40']:+.2f}",
        "sixty_control": " and ".join(
            f"{arms[k + ':60']['c_star']:.1f}" for k in ("state_gated_other1", "state_randdir0")
        ),
        "level": f"{m6['level']:g}",
        "in_share": f"{share['group']:.2f}",
        "next_share": f"{share['other_groups_with_largest_share'][0][1]:.3f}",
        "rise_inside": interval(
            extra["in_frame_rise_over_head_edit_rise"]["point"],
            extra["in_frame_rise_over_head_edit_rise"]["ci95"],
            lambda x: f"{x:.3f}",
        ),
        "rise_rest": f"{verdict['rise_rest'] / verdict['rise_m3_edit']:.2f}",
        "rise_state": f"{(arms['state_gated:40']['mean_margin_count_48_50'] - arms['clean']['mean_margin_count_48_50']) / verdict['rise_m3_edit']:.2f}",
        "state_peak": arms["state_gated:40"]["bump_count"],
        "close_cross": f"{arms['state_randdir4:40']['c_star']:.1f}",
        "small_size": f"{min(c['size_injected_rms_over_mixer_rms'] for c in controls):.3f} to {max(c['size_injected_rms_over_mixer_rms'] for c in controls):.3f}",
        "small_cross": f"{min(c['c_star'] for c in controls):.1f} to {max(c['c_star'] for c in controls):.1f}",
        "other_margin": f"{arms['state_gated_other1:40']['mean_margin_count_48_50']:.2f}",
        "other_end": f"{arms['state_gated_other1:40']['mean_margin_at_true_breaks']:+.2f}",
        "other_group": m6["state_edit"]["40"]["control_group_rank1"],
        "other_cross": f"{arms['state_gated_other1:40']['c_star']:.1f}",
        "sixty": ", ".join(f"{arms[k + ':60']['c_star']:.1f}" for k in ("shift", "in_frame", "state_gated")),
        "end_clean": f"{arms['clean']['mean_margin_remaining_0_2']:+.2f}",
        "end_head": f"{arms['shift:40']['mean_margin_remaining_0_2']:+.2f}",
    }
    facts.find(
        "README.md",
        r"script took (\d+) seconds the first time and (\d+) seconds after that. Peak GPU memory was ([\d.]+) GiB",
        ["width.first", "width.cached", "width.memory"],
    )
    return {
        "sources": [
            "README.md (width intervention demonstration)",
            "line_count/m6_frame_edit.json",
            "line_count/m7_extra.json",
        ],
        "rows": rows,
        **measures,
    }


def generated_lines(root):
    folder = root / "line_count"
    results, texts, post = [read(folder / name) for name in ("m7_results.json", "m7_texts.json", "m7_posthoc.json")]
    fmt = lambda x: f"{round(x, 1):g}"
    labels = {
        "none": "No edit",
        "head:40": "Head edit",
        "perm:40": "Permuted head edit",
        "frame:40": "Inside the frame",
        "state:40": "State edit",
        "state_rand:40": "Random in-frame direction",
        "state_other:40": "Another group",
        "ref:40": "Width-40 prompt, no edit",
    }
    rows = {}
    for key, label in labels.items():
        sampled = results["arms"][key]["sampled"]
        docs = sampled["line_lengths_by_document"]
        lengths = [length for doc in docs for length in doc]
        assert len(docs) == results["documents"] and len(lengths) == sampled["lines"]
        bins = [0] * 13
        for length in lengths:
            bins[min(length // 10, 12)] += 1
        assert bins == post["arms"][key]["sampled"]["histogram_10_character_bins_0_to_120_up"]
        rows[key] = {
            "label": label,
            "bins": bins,
            "lines": f"{len(lengths):,}",
            "median": interval(sampled["median"], sampled["median_ci95"], fmt),
            "mean": f"{sampled['mean']:.1f}",
            "short": f"{100 * sampled['share_le_60']:.1f}%",
            "long": f"{100 * sum(x >= 80 for x in lengths) / len(lengths):.1f}%",
        }
    verdict = results["verdicts"]["the_edit_changes_generated_wrapping"]
    retained = results["verdicts"]["the_frame_carries_it"]
    perm = results["arms"]["perm:40"]["sampled"]
    first = 0
    assert results["corpus_lines"] == texts["corpus_lines"]
    doc = {key: texts["arms"][key]["sampled"]["text"][first] for key in ("none", "head:40")}
    head_docs = results["arms"]["head:40"]["sampled"]["line_lengths_by_document"]
    first_lines = [doc[0] for doc in head_docs if doc]
    later_lines = [v for doc in head_docs for v in doc[3:]]
    return {
        "sources": ["line_count/m7_results.json", "line_count/m7_texts.json", "line_count/m7_posthoc.json"],
        "overflow_bin": "120+",
        "rows": rows,
        "documents": results["documents"],
        "tokens": results["new_tokens"],
        "example": {
            **doc,
            "corpus_line": texts["corpus_lines"][first],
            "prompt_end": "\n".join(texts["prompts"]["100"][first].rstrip("\n").splitlines()[-2:]),
        },
        "reduction": interval(verdict["reduction"], verdict["reduction_ci95"], fmt),
        "allowed": verdict["allowed_at_most_abs"],
        "retained": interval(
            retained["frame_over_head"], retained["frame_over_head_ci95_descriptive"], lambda x: f"{x:.2f}"
        ),
        "perm_delta": interval(perm["median_minus_no_edit"], perm["median_minus_no_edit_ci95"], lambda x: f"{x:+.0f}"),
        "long_first": f"{100 * sum(v >= 80 for v in first_lines) / len(first_lines):.0f}%",
        "long_later": f"{100 * sum(v >= 80 for v in later_lines) / len(later_lines):.0f}%",
        "sixty": ", ".join(
            fmt(results["arms"][k + ":60"]["sampled"]["median"]) for k in ("head", "frame", "state", "ref")
        ),
        "greedy": ", ".join(
            fmt(results["arms"][k]["greedy"]["median"]) for k in ("none", "head:40", "frame:40", "state:40", "perm:40")
        ),
        "letters": [
            f"{100 * results['arms'][key]['sampled']['letter_or_space_share']:.1f}%" for key in ("none", "head:40")
        ],
    }


def code_behaviour(root):
    tables = read(root / "steer_state/x1_out/tables.json")
    main = {
        "nbase": "No edit",
        "n_g2879_d1": "Mean dose",
        "n_g2879_d2": "Twice the dose",
        "n_g2879_d4": "Four times the dose",
        "ginstr": "Written instruction",
        "n_full_d1": "Whole prompt difference",
    }
    measures = ("guard", "type_rej", "value_rej", "valid_all")
    pct = lambda n: f"{100 * n:.1f}"
    rows = {}
    for key, label in main.items():
        cell = tables["cells"][key]
        rows[key] = {"label": label, **{m: interval(cell[m][0], cell[m][1:], pct) for m in measures}}
        rows[key]["guard_pct"] = rows[key]["guard"].replace(" [", "% [")
        rows[key]["wrong_type_pct"] = f"{100 * cell['type_rej'][0]:.1f}%"
        rows[key]["valid_pct"] = f"{100 * cell['valid_all'][0]:.1f}%"
    changes = {}
    for condition, label in (
        ("n_g2879_d1", "Mean dose"),
        ("n_g2879_d2", "Twice the dose"),
        ("n2_g2879_d2", "Second neutral sentence, twice"),
        ("n3_g2879_d2", "Third neutral sentence, twice"),
    ):
        cell = tables["cells"][condition]
        metrics = {}
        for m in measures[1:]:
            delta = cell["d_" + m]
            metrics[m] = interval(delta[0], delta[1:], lambda x: f"{x * 100:+.1f}")
        changes[condition] = {"label": label, **metrics}
    for key in ("n_g2879_d1", "n_g2879_d2"):
        row = tables["unit_minus_controls"][key]
        changes[key + "_controls"] = {
            "label": main[key] + " versus pooled controls",
            **{m: interval(row[m][0], row[m][1:], lambda x: f"{100 * x:+.1f}") for m in measures[1:]},
        }
    special = {key: int(tables["cells"][key]["spec_edge_n_outputs_raise"]) for key in main}
    other = {}
    for k in ("n2", "n3"):
        for dose in (1, 2):
            delta = tables["cells"][f"{k}_g2879_d{dose}"]["d_guard"]
            other[k + str(dose)] = "+" + (interval(delta[0], delta[1:], pct) if dose == 2 else pct(delta[0]))
    pooled = tables["syntax_vs_behaviour"]["POOLED"]
    return {
        "sources": ["steer_state/x1_out/tables.json"],
        "rows": rows,
        "other": other,
        "changes": changes,
        "fires": f"{100 * pooled['g1r'] / pooled['g1n']:.1f}%",
        "fired": f"{int(pooled['g1r']):,}",
        "scored": f"{pooled['g1n']:,}",
        "edge_cases": special,
        "edge_n": tables["cells"]["nbase"]["spec_edge_n_outputs"],
        "empty_n": tables["cells"]["nbase"]["spec_empty_n_outputs"],
        "value_tasks": tables["cells"]["nbase"]["n_value_tasks"],
    }


def audit_facts(facts, root):
    source = "site_audit_2026-11-21/site_corrections.md"
    notes = " ".join((root / source).read_text().split())
    for pattern, names in (
        (
            r"with ([\d.]+) to ([\d.]+) of the squared\s+change; the runner-up has ([\d.]+) to ([\d.]+)\)",
            ["pick.min", "pick.max", "pick.next_min", "pick.next_max"],
        ),
        (
            r"three common directions: ([\d.]+) -> ([\d.]+); in the full residual, over (\d+) to (\d+) characters remaining .*?figure.s all-cells range\): ([\d.]+) \(resid_post.11\) -> ([\d.]+) \(resid_mid.12\) -> ([\d.]+) \(resid_post.13\)",
            [
                "spread.three_before",
                "spread.three_after",
                "spread.start",
                "spread.stop",
                "spread.full_before",
                "spread.full_mid",
                "spread.full_post",
            ],
        ),
        (r"one with cosine\s+([\d.]+) to the edit", ["width.close_cos"]),
        (r"with cosines ([-\d.]+, [-\d.]+, [-\d.]+ and [-\d.]+) do not", ["width.other_cos"]),
        (r"selects group 15458 on ([\d.]+ to [\d.]+) of clean", ["width.active"]),
        (r"it has cosine ([\d.]+) with the edit\)", ["width.random_cos"]),
        (
            r"(\d+ to \d+)% of the head's response.*?it reproduced (\d+ to \d+)%",
            ["transcoder.mlp", "transcoder.residual"],
        ),
        (
            r"72 tasks, (\d+) valid cases, (\d+) wrong-type inputs, (\d+) wrong-value inputs",
            ["exec.valid", "exec.types", "exec.values"],
        ),
        (r"group 2879's part of that mean shift \(([\d.]+) of its norm", ["su.norm_share"]),
    ):
        facts.find(source, pattern, names, notes)
