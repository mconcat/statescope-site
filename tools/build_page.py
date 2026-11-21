"""Write index.html from tools/page.template.html and the generated data files.

    python -B tools/build_page.py

Placeholders of the template (an unknown one stops the build):
  {{key}}                      display string of that key in data/facts.json
  {{share|<cell>|<swap>}}      share on even-numbered items from data/demo.json, for example {{share|count:60|l8/t189}}
  {{ci|<cell>|<swap>}}         the same share with its bootstrap interval, "0.328 (0.261 to 0.385)"
  {{rate|<unit>|<bin>}}        firing rate of data/demo.json, for example {{rate|L9 transform 410|30-39}}
  {{table|<name>}}             a table built from the data files
  {{lead}}                     the token-level text of the first figure, built from data/items-<cell>.json (item of demo.json "lead")
  {{strips}}                   the same lines as strips scaled to the figure's width, shown on narrow screens
  {{rates}}                    the firing-rate chart of the first figure, built from data/demo.json
  {{toc}}                      the list of sections (every <h2 id=...> of the page)
  {{fig|<name>}}               the number of <figure id="fig-<name>">, counted in page order
  {{python_tasks}}             evaluation function names and specifications, when provided by the prompt-state analysis
  {{python_answer|<condition>}}   the saved greedy acronym answer in the baseline or edited run
  {{steer|<cell>|<swap>|<dose>}}   share on all items of a cell at one dose, from data/steer.json
Blocks:
  <!--if 4b--> ... <!--endif 4b-->        kept only when data/layers-4b.json exists
  <!--if steer--> ... <!--endif steer-->  kept only when data/steer.json exists
  <!--if curve--> ... <!--endif curve-->  kept only when data/count-curve.json exists
  <!--if trace--> ... <!--endif trace-->  kept only when data/trace.json exists
  <!--if geom--> ... <!--endif geom-->    kept only when data/geom-4b.json exists
  <!--if frames--> ... <!--endif frames-->  kept only when the stops of data/trace.json carry the groups' frames
  {{trace|<step>|<entry>|<cell>}}  a share of the trace table of data/trace.json
  {{pathstrip|<stop>}}         one stop of the animated figure as a small static drawing
  {{references}}               the list of tools/references.json
Every <h2 id> and <h3 id> becomes its own link. Standard library only.
"""
from __future__ import annotations

import html
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
esc = html.escape


def exists(name: str) -> bool:
    return os.path.exists(os.path.join(HERE, "data", name))


def data(name: str) -> dict:
    with open(os.path.join(HERE, "data", name)) as f:
        return json.load(f)


def table(caption: str, head: list[str], rows: list[list[str]], row_header: bool = False) -> str:
    out = ['<div class="table-wrap"><table>', f"<caption>{esc(caption)}</caption>", "<thead><tr>"]
    out += [f'<th scope="col">{esc(c)}</th>' for c in head]
    out.append("</tr></thead><tbody>")
    for row in rows:
        cells = [f'<th scope="row">{esc(row[0])}</th>' if row_header else f"<td>{esc(row[0])}</td>"]
        cells += [f"<td>{esc(c)}</td>" for c in row[1:]]
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def details_table(f: dict, caption: str, four: bool) -> str:
    """sizes and training settings of one set, from data/facts.json (every value a fact read by tools/build_data.py)"""
    v = lambda key: f[key]["display"]
    p = "b4" if four else "mlp"
    tiers = ", ".join(f"{v(f'{p}.tier{i}_n')} of rank {v(f'{p}.tier{i}_rank')}" for i in range(1, 6))
    if four:
        rows = [["Base model", v("b4.model")], ["Layers, width", f"{v('b4.layers')}, {v('b4.width')}"],
                ["State dictionary: groups", f"{v('b4.groups')} groups of {v('b4.group_size')} directions"],
                ["State dictionary: active groups per token", v("b4.active")],
                ["State dictionary: training", f"{v('b4.state_train_tokens')} tokens over {v('b4.state_train_steps')} steps"],
                ["MLP dictionary: transforms", v("b4.transforms")], ["MLP dictionary: rank tiers", tiers],
                ["MLP dictionary: gate", "JumpReLU"], ["MLP dictionary: read and write matrices", "free, no skip connection"],
                ["MLP dictionary: sparsity penalty", f"tanh, coefficient {v('b4.penalty')} at all {v('b4.layers')} layers"],
                ["MLP dictionary: training", f"{v('b4.mlp_train_steps')} steps of {v('b4.mlp_step_tokens')} tokens, or {v('b4.mlp_train_million_tokens')} million tokens, per layer"],
                ["MLP dictionary: learning rate", v("b4.learning_rate")],
                ["Files", f"{v('b4.files')} weight and config files"],
                ["Size", f"about {v('b4.total_gib')} GiB: state about {v('b4.state_gib')} GiB, MLP about {v('b4.mlp_gib')} GiB"]]
    else:
        rows = [["Base model", v("set.model")], ["Layers, width", f"{v('model.layers')}, {v('model.width')}"],
                ["State dictionary: groups", f"{v('state.groups')} groups of {v('state.group_size')} directions"],
                ["State dictionary: active groups per token", v("state.active")],
                ["State dictionary: training", f"{v('state.train_tokens')} tokens over {v('state.train_steps')} steps"],
                ["MLP dictionary: transforms", v("mlp.transforms")], ["MLP dictionary: rank tiers", tiers],
                ["MLP dictionary: gate", "JumpReLU"], ["MLP dictionary: read and write matrices", "free, no skip connection"],
                ["MLP dictionary: sparsity penalty", f"tanh, coefficient {v('mlp.penalty_main')} at layers {v('model.first_layer')} to {v('mlp.penalty_main_last_layer')}, "
                                                    f"{v('mlp.penalty_last')} at layer {v('model.last_layer')}"],
                ["MLP dictionary: training", f"{v('mlp.train_steps')} steps of {v('mlp.step_tokens')} tokens, or {v('mlp.train_million_tokens')} million tokens, per layer"],
                ["MLP dictionary: learning rate", v("mlp.learning_rate")],
                ["Files", f"{v('set.files')} weight and config files"],
                ["Size", f"about {v('set.total_gib')} GiB: state about {v('set.state_gib')} GiB, MLP about {v('set.mlp_gib')} GiB"]]
    return table(caption, ["Setting", v("b4.model") if four else v("set.model")], rows, row_header=True)


# captions of the two tables of training details, written for this page
DETAILS_CAPTION_4B = ("This table lists the dictionary sizes, training settings, file counts, and file sizes for our Qwen3.5-4B set, using values from the "
                      "README, model card, and manifest.")
DETAILS_CAPTION_08B = ("This table lists the dictionary sizes, training settings, file counts, and file sizes for our Qwen3.5-0.8B set, using values from the "
                       "README, model card, and manifest.")

GENERATED_EDIT_LABELS = {
    "perm:40": "Permuted control",
    "frame:40": "In-frame part",
    "state_rand:40": "Random direction in the frame",
    "state_other:40": "State edit in another group",
}


def tables(facts: dict) -> dict[str, str]:
    layers, splice, demo = data("layers.json"), data("splice.json"), data("demo.json")
    col = layers["columns"]
    cells = [c["key"] for c in demo["cells"]]
    labels = demo["link_labels"]
    out = {}
    out["layers"] = table(
        "Numbers per layer. The first three value columns were re-measured with the published reader with position 0 dropped. "
        "The next three were recorded at training by us.",
        ["Layer", col["state_mid"], col["state_post"], col["mlp"], col["mlp_train"], col["on_per_token"], col["alive"], col["penalty"]],
        [[str(r["layer"]), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"],
          r["alive_text"], r["penalty"]] for r in layers["rows"]])
    out["splice"] = table(
        "Spliced-in loss: increase in cross-entropy in nats, from the training evaluation. The final-layer MLP value comes from a separate measurement on the same kind of text.",
        ["Layer", splice["columns"]["state"], splice["columns"]["mlp"]],
        [[str(r["layer"]), r["state"], r["mlp"]] for r in splice["rows"]])
    main = [a for a in demo["arms"] if a["group"] == "main"]
    out["shares"] = table(
        "Shares on even-numbered items, with the bootstrap interval in parentheses.",
        ["Swap"] + cells,
        [[a["label"]] + [f"{e['s']} ({e['slo']} to {e['shi']})" for e in (demo["shares"][c][a["key"]]["even"] for c in cells)] for a in main],
        row_header=True)
    link_rows = []
    for row in demo["link_table"]["even"]:
        label = f"{labels['bases'][row['base']]}, {labels['parts'][row['part']]}"
        values = []
        for c in cells:
            v = row["cells"][c]
            values.append(f"{v['F2']} / {v['T2']} ({v['down']})" if "down" in v else f"{v['F2']} / {v['T2']}")
        link_rows.append([label] + values)
    routes = labels["routes"]
    out["link"] = table(
        f"Shares on even-numbered items, written A / B (C). A: {routes['F2']}. B: {routes['T2']}. C: {routes['down']}. The last row has no C.",
        ["Change at the L9 mixer output"] + cells, link_rows, row_header=True)
    units = list(demo["firing_rate"])
    bins = [b["bin"] for b in demo["firing_rate"][units[0]]["by_chars_in_line"]]
    rate_rows = [["first token of a line"] + [demo["firing_rate"][u]["line_first"] for u in units],
                 ["line-break token"] + [demo["firing_rate"][u]["newline"] for u in units],
                 ["any other token"] + [demo["firing_rate"][u]["other"] for u in units]]
    for i, b in enumerate(bins):
        rate_rows.append([f"other token, {b} characters in the line"] + [demo["firing_rate"][u]["by_chars_in_line"][i]["rate"] for u in units])
    out["rates"] = table(
        "Fraction of tokens at which each transform's gate is open, on the clean texts of the two count conditions.", ["Tokens"] + units, rate_rows,
        row_header=True)
    out["details08b"] = details_table(facts, DETAILS_CAPTION_08B, False)
    if exists("layers-4b.json"):
        out["details4b"] = details_table(facts, DETAILS_CAPTION_4B, True)
        four = data("layers-4b.json")
        col = four["columns"]
        out["layers4b"] = table(
            "Qwen3.5-4B set, numbers per layer. The first three value columns were re-measured with the published reader with position 0 dropped. "
            "Training records supply MLP FVU, transforms on per token and transforms alive. The last two columns were measured after training. The counts use FineWeb-Edu and held-out training-mix tokens respectively. The write energy uses FineWeb-Edu.",
            ["Layer", col["state_mid"], col["state_post"], col["mlp"], col["mlp_train"], col["on_per_token"], col["alive"], col["always"], "Fraction of summed write energy carried by those transforms on web text"],
            [[str(r["layer"]), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"],
              r["alive_text"], r["always_text"], r["always_energy"]] for r in four["rows"]])
    comparison = data("state-subspaces.json")
    conditions = comparison["conditions"]
    subspace_labels = {"One learned BSF group": "One learned group of the state dictionary"}
    out["subspaces"] = table("Percentage of the full mixer effect retained through the six transforms, with paired 95% bootstrap intervals over new document pairs.",
                            ["Subspace", *conditions], [[subspace_labels.get(label, label), *(values[c] for c in conditions)] for label, values in comparison["rows"].items()], True)
    if exists("width-edit.json"):
        widths = data("width-edit.json")
        group = facts["lc.g12"]["display"]
        labels = {
            "clean": "No edit",
            "shift:40": "Head edit (head 13, toward width 40)",
            "perm:40": "Permuted control",
            "in_frame:40": f"In-frame part (group {group})",
            "rest:40": "The rest",
            "state_gated:40": f"State edit (group {group}, toward width 40)",
            "state_randdir0:40": "Random direction in the frame",
        }
        out["width"] = table("Fixed-text edits. Size is the root mean square (RMS) of the edit divided by the RMS of the mixer output. Brackets give 95% bootstrap intervals over documents where measured.",
                             ["Edit", "Relative size", "First crossing (characters)", "Mean margin at counts 48–50", "Margin before a line break"],
                             [[labels[row["arm"]], row["size"], row["crossing"], row["margin"], row["end"]] for row in widths["rows"]], True)
    if exists("generated-lines.json"):
        gen = data("generated-lines.json")
        out["lengths"] = table("Completed non-empty lines in the sampled continuations. The interval on the median resamples documents.",
                               ["Condition", "Lines", "Median [95% interval]", "Mean", "At most 60 characters", "At least 80 characters"],
                               [[GENERATED_EDIT_LABELS.get(arm, r["label"]), r["lines"], r["median"], r["mean"], r["short"], r["long"]]
                                for arm, r in gen["rows"].items()], True)
    if exists("code-behaviour.json"):
        scores = data("code-behaviour.json")
        out["behaviour"] = table("Generated Python on the main wording. Percentages with 95% bootstrap intervals over tasks. Rejection means a raise statement in the generated code fired.",
                                 ["Condition", "Contains raise or isinstance", "Wrong types rejected", "Wrong values rejected", "Passes every valid case"],
                                 [[r[k] for k in ("label", "guard", "type_rej", "value_rej", "valid_all")] for r in scores["rows"].values()], True)
        out["behaviour-changes"] = table("Change in percentage points with 95% paired bootstrap intervals over tasks. Each prompt is compared with its own unedited run. The last two rows compare the main edit with pooled control directions at its dose.",
                                         ["Condition", "Wrong types rejected", "Wrong values rejected", "Passes every valid case"],
                                         [[r[k] for k in ("label", "type_rej", "value_rej", "valid_all")] for r in scores["changes"].values()], True)
    return out


# ------------------------------------------------------------------------------------------------ the first figure, built without a browser
def token_lines(item: dict, key: str = "clean") -> list[list[int]]:
    """token indices of each line of a text; a line-break token closes its line"""
    lines: list[list[int]] = [[]]
    for i, piece in enumerate(item[key]):
        lines[-1].append(i)
        if piece == "\n":
            lines.append([])
    return [line for line in lines if line]


def token_class(item: dict, i: int, units: list[str], last: int) -> str:
    cls = ["tok"]
    for letter, unit in zip("abc", units):
        if item["gate"][unit][i] == "1":
            cls.append(letter)
    if item["clean"][i] == "\n":
        cls.append("nl")
    if item["known"][i] == "0":
        cls.append("u")
    if i == last:
        cls.append("last")
    return " ".join(cls)


def lead_figure(demo: dict) -> str:
    """the last lines of one clean text: one span per token, with the gate of each of the three transforms as a class.
    assets/js/tokens.js writes the same markup for the item viewer."""
    lead, c = demo["lead"], demo["constants"]
    info = next(x for x in demo["cells"] if x["key"] == lead["cell"])
    item = data(info["file"])["items"][lead["item"]]
    units = [str(c["l8_transform"])] + [str(t) for t in c["l9_transforms"]]
    lines = token_lines(item)[-lead["lines"]:]
    last = len(item["clean"]) - 1
    assert all(item["known"][i] == "1" for line in lines for i in line)
    width = info["width"]
    out = [f'<div class="ttext" data-items data-cell="{esc(lead["cell"])}" data-item="{lead["item"]}" data-first="{lines[0][0]}" style="--w:{width}">']
    out.append('<div class="ruler" aria-hidden="true">' + "".join(f'<span style="--at:{x}">{x}</span>' for x in range(0, width + 1, 20)) + "</div>")
    for line in lines:
        spans = []
        for i in line:
            piece = item["clean"][i]
            spans.append(f'<span class="{token_class(item, i, units, last)}" data-i="{i}" data-c="{item["chars"][i]}">{"⏎" if piece == chr(10) else esc(piece)}</span>')
        end = item["chars"][line[-1]] if item["clean"][line[-1]] != "\n" else item["chars"][line[-2]]
        out.append(f'<div class="tline">{"".join(spans)}<span class="count" aria-hidden="true">{end}</span></div>')
    out.append("</div>")
    return "\n".join(out)


def lead_strips(demo: dict) -> str:
    """the same lines, one strip per line scaled to the figure's width, for screens too narrow for the text"""
    lead, c = demo["lead"], demo["constants"]
    info = next(x for x in demo["cells"] if x["key"] == lead["cell"])
    item = data(info["file"])["items"][lead["item"]]
    units = [str(c["l8_transform"])] + [str(t) for t in c["l9_transforms"]]
    lines = token_lines(item)[-lead["lines"]:]
    last, width = len(item["clean"]) - 1, info["width"]
    out = [f'<div class="tmap" data-items aria-hidden="true" style="--w:{width}">']
    for line in lines:
        strip = []
        for i in line:
            n = 1 if item["clean"][i] == "\n" else len(item["clean"][i])
            strip.append(f'<i class="{token_class(item, i, units, last)}" style="--n:{n}"></i>')
        out.append(f'<div class="tmap-line">{"".join(strip)}</div>')
    out.append("</div>")
    return "\n".join(out)


def rates_chart(demo: dict) -> str:
    """firing rate of the two L9 transforms by characters in the line: one column per bin, as wide as the bin is in the text above"""
    c = demo["constants"]
    names = [f"L9 transform {t}" for t in c["l9_transforms"]]
    series = [demo["firing_rate"][n]["by_chars_in_line"] for n in names]
    bins = [b["bin"] for b in series[0]]
    step = c["char_bin"]
    assert bins == [f"{i * step}-{i * step + step - 1}" for i in range(len(bins))]
    out = [f'<div class="rates" style="--w:{len(bins) * step};--step:{step}">',
           '<div class="rates-y" aria-hidden="true"><span style="--v:1">1.0</span><span style="--v:0.5">0.5</span><span style="--v:0">0</span></div>',
           '<div class="rates-plot">']
    for i, b in enumerate(bins):
        bars = []
        for cls, s in zip(("b", "c"), series):
            rate = s[i]["rate"]
            label = f"<b>{rate}</b>" if float(rate) >= 0.1 else ""
            bars.append(f'<i class="bar {cls}" style="--r:{rate}">{label}</i>')
        out.append(f'<div class="bin" data-bin="{b}">{"".join(bars)}</div>')
    out.append("</div>")
    out.append('<div class="rates-x" aria-hidden="true">' + "".join(f"<span>{b}</span>" for b in bins) + "</div>")
    out.append("</div>")
    return "\n".join(out)


def path_strip(trace: dict, index: int) -> str:
    """one stop of the animated figure as a small static drawing (the mesh in the figure's fixed view), shown where scripts are off"""
    path, widths = trace["path"], trace["widths"]
    stops = path["stops"]
    pts = [(float(x), -float(y)) for s in stops for w in widths for x, y in zip(s["curves"][w]["x"], s["curves"][w]["y"])]
    x0, x1, y0, y1 = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)
    W, H, M = 190, 120, 6
    k = min((W - 2 * M) / (x1 - x0), (H - 2 * M) / (y1 - y0))
    place = lambda x, y: f"{M + (float(x) - x0) * k:.1f} {M + (-float(y) - y0) * k:.1f}"
    out = []
    curves = stops[index]["curves"]
    first = {w: int(trace["counts"][w][0]) for w in widths}
    for c in range(path["connect"], max(int(trace["counts"][w][1]) for w in widths) + 1, path["connect"]):
        has = [w for w in widths if 0 <= c - first[w] < len(curves[w]["x"])]
        if len(has) > 1:
            out.append('<path d="M' + "L".join(place(curves[w]["x"][c - first[w]], curves[w]["y"][c - first[w]]) for w in has) + '" class="mesh-connector"/>')
    for w in widths:
        xy = list(zip(curves[w]["x"], curves[w]["y"]))
        out.append('<path d="M' + "L".join(place(x, y) for x, y in xy[::2]) + '" class="path-line"/>')
        tail = xy[max(0, int(w) - path["highlight"] - first[w]):]
        out.append('<path d="M' + "L".join(place(x, y) for x, y in tail) + '" class="mesh-end"/>')
    return f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">{"".join(out)}</svg>'


def length_histograms(generated: dict) -> str:
    """Small multiples with common bin edges and a common frequency scale."""
    rows = generated["rows"]
    peak = max(max(r["bins"]) / sum(r["bins"]) for r in rows.values())
    overflow = generated["overflow_bin"]
    overflow_start = int(overflow.removesuffix("+"))
    extent = overflow_start + 10
    guides = "".join(f'<line x1="{x}" x2="{x}" y1="0" y2="35"/>' for x in (40, 100))
    ticks = []
    for x in (0, 40, 60, 100, overflow_start):
        label = overflow if x == overflow_start else str(x)
        ticks.append(f'<span style="left:{x / extent:.4%}">{esc(label)}</span>')
    out = []
    for arm, row in rows.items():
        n = sum(row["bins"])
        bars = []
        for i, count in enumerate(row["bins"]):
            height = 34 * count / n / peak
            bars.append(f'<rect x="{i * 10 + 0.5}" y="{35-height:.2f}" width="9" height="{height:.2f}" data-lines="{count}"/>')
        out.append(
            f'<div class="length-row" data-arm="{esc(arm)}"><div class="length-summary"><b>{esc(GENERATED_EDIT_LABELS.get(arm, row["label"]))}</b>'
            f'<span>Median {esc(row["median"])} · mean {esc(row["mean"])}</span></div>'
            f'<div class="length-chart" aria-hidden="true"><svg viewBox="0 0 {extent} 35" preserveAspectRatio="none">'
            f'{"".join(bars)}{guides}</svg><div class="length-scale">{"".join(ticks)}</div></div></div>'
        )
    return "\n".join(out)


def references() -> str:
    """the list of works the page refers to, from tools/references.json; an entry with "needs" is listed only when that data file exists"""
    with open(os.path.join(HERE, "tools", "references.json")) as f:
        entries = json.load(f)["references"]
    out = []
    for e in entries:
        if "needs" in e and not exists(e["needs"]):
            continue
        title = e["title"] if e["title"].endswith("?") else e["title"] + "."
        out.append(f'    <p class="citation">{esc(e["authors"])}. {esc(title)} {esc(e["id"])}, {esc(e["date"])}. <a href="{esc(e["url"])}">{esc(e["url"])}</a></p>')
    return "\n".join(out)


# ------------------------------------------------------------------------------------------------ the page
def conditional(page: str, name: str, keep: bool, inside: str | None = None) -> str:
    """keep or drop the blocks of one name; a name whose blocks all stand inside another block may be gone with it"""
    pattern = re.compile(rf"<!--if {name}-->(.*?)<!--endif {name}-->", flags=re.S)
    assert pattern.search(page) or (inside and not exists(inside)), f"no block for {name!r} in the template"
    return pattern.sub((lambda m: m.group(1)) if keep else (lambda m: ""), page)


def main() -> None:
    facts = data("facts.json")["facts"]
    demo = data("demo.json")
    with open(os.path.join(HERE, "tools", "page.template.html")) as f:
        page = f.read()
    page = page[:page.index("<!--")] + page[page.index("-->") + 4:]          # the template's own header comment
    page = conditional(page, "4b", exists("layers-4b.json"))
    page = conditional(page, "steer", exists("steer.json"))
    page = conditional(page, "curve", exists("count-curve.json"))
    page = conditional(page, "trace", exists("trace.json"))
    page = conditional(page, "geom", exists("geom-4b.json"))
    prompt_study = data("geom-4b.json")["state"] if exists("geom-4b.json") else {}
    page = conditional(page, "python-tasks", bool(prompt_study.get("tasks")), inside="geom-4b.json")
    page = conditional(page, "python-answers", bool(prompt_study.get("acronym_answers")), inside="geom-4b.json")
    trace = data("trace.json") if exists("trace.json") else None
    page = conditional(page, "frames", bool(trace) and "frame" in trace["path"]["stops"][0], inside="trace.json")
    steer = data("steer.json") if exists("steer.json") else None
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)                        # the template's remaining notes are not part of the page

    figures = {name: n for n, name in enumerate(re.findall(r'<figure[^>]*\bid="fig-([a-z0-9-]+)"', page), start=1)}          # figures with an id are numbered
    sections = re.findall(r'<h2 id="([a-z0-9-]+)">(.*?)</h2>', page, flags=re.S)
    built, used = tables(facts), set()

    records = {key: data(file) for key, file in (("width", "width-edit.json"), ("gen", "generated-lines.json"),
               ("comparison", "state-subspaces.json"), ("code", "code-behaviour.json")) if exists(file)}

    def fill(match: re.Match) -> str:
        key = match.group(1)
        parts = key.split("|")
        if parts[0] == "m":
            value = records[parts[1]]
            for field in parts[2:]:
                value = value[int(field)] if isinstance(value, list) else value[field]
            return esc(str(value))
        if key == "continuations":
            example = records["gen"]["example"]
            out = []
            for arm, label in (("none", "No edit"), ("head:40", "Head edit to width 40")):
                lines = "".join(f"<li>{esc(line)}</li>" for line in example[arm].split("\n"))
                out.append(f'<div><h4>{label}</h4><ol>{lines}</ol></div>')
            return "\n".join(out)
        if key == "lengths":
            return length_histograms(records["gen"])
        if parts[0] == "table":
            return built[parts[1]]
        if parts[0] == "fig":
            return str(figures[parts[1]])
        if parts[0] in ("share", "ci"):
            e = demo["shares"][parts[1]][parts[2]]["even"]
            return e["s"] if parts[0] == "share" else f"{e['s']} ({e['slo']} to {e['shi']})"
        if parts[0] == "steer":                                               # share on all items of a cell at one dose
            return steer["cells"][parts[1]]["arms"][parts[2]]["share"][steer["alphas"].index(parts[3])]
        if parts[0] == "trace":                                               # a share of the trace table: step, entry, cell
            return trace["table"][int(parts[1])]["entries"][int(parts[2])]["shares"][int(parts[3])]
        if parts[0] == "link_random":
            row = next(r for r in demo["link_table"]["even"] if r["base"] == "mix" and r["part"] == "random")
            return row["cells"][parts[1]]["F2"]
        if parts[0] == "causal":
            c = trace["causal"]
            return c["arms"][parts[1]][c["counts"].index(parts[2])]
        if parts[0] == "pathstrip":
            return path_strip(trace, int(parts[1]))
        if key == "last_state_loss":
            return data("splice.json")["rows"][-1]["state"]
        if key == "references":
            return references()
        if key == "python_tasks":
            return "\n".join(f"<div><dt><code>{esc(name)}</code></dt><dd>{esc(spec)}.</dd></div>" for name, spec in prompt_study["tasks"].items())
        if parts[0] == "python_answer":
            # Preserve whitespace inside the original docstrings without trailing spaces in the HTML source.
            return esc(prompt_study["acronym_answers"][parts[1]]).replace(" \n", "&#32;\n")
        if parts[0] == "rate":
            return next(b["rate"] for b in demo["firing_rate"][parts[1]]["by_chars_in_line"] if b["bin"] == parts[2])
        if key == "lead":
            return lead_figure(demo)
        if key == "strips":
            return lead_strips(demo)
        if key == "rates":
            return rates_chart(demo)
        if key == "toc":
            return "\n".join(f'<li><a href="#{i}">{re.sub("<[^>]+>", "", t)}</a></li>' for i, t in sections)
        used.add(key)
        return esc(facts[key]["display"])

    page = re.sub(r"\{\{([A-Za-z0-9_.:/|, -]+)\}\}", fill, page)
    assert "{{" not in page and "}}" not in page
    page = re.sub(r'<(h[23]) id="([a-z0-9-]+)">(.*?)</\1>', r'<\1 id="\2"><a href="#\2">\3</a></\1>', page, flags=re.S)
    page = page.replace("<html lang=\"en\">", "<!-- Generated by tools/build_page.py from tools/page.template.html and data/. Do not edit by hand. -->\n<html lang=\"en\">", 1)
    with open(os.path.join(HERE, "index.html"), "w") as f:
        f.write(page)
    print(f"wrote index.html  {len(page):,} characters; {len(figures)} figures; {len(sections)} sections; facts used: {len(used)} of {len(facts)}")
    unused = sorted(set(facts) - used)
    if unused:
        print("facts not used on the page:", ", ".join(unused))


if __name__ == "__main__":
    main()
