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
Blocks:
  <!--if 4b--> ... <!--endif 4b-->        kept only when data/layers-4b.json exists
  <!--if steer--> ... <!--endif steer-->  kept only when data/steer.json exists
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


def tables() -> dict[str, str]:
    layers, splice, demo = data("layers.json"), data("splice.json"), data("demo.json")
    col = layers["columns"]
    cells = [c["key"] for c in demo["cells"]]
    labels = demo["link_labels"]
    out = {}
    out["layers"] = table(
        "Numbers per layer. The first three value columns were measured by this repository with position 0 dropped. "
        "The next three were recorded at training by the original project.",
        ["Layer", col["state_mid"], col["state_post"], col["mlp"], col["mlp_train"], col["on_per_token"], col["alive"], col["penalty"]],
        [[str(r["layer"]), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"],
          r["alive_text"], r["penalty"]] for r in layers["rows"]])
    out["splice"] = table(
        "Spliced-in loss: increase in cross-entropy in nats, recorded by the original project and not repeated by this repository.",
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
        "Fraction of tokens at which each transform's gate is open, on the clean texts of the two count cells. "
        "Measured by this repository's demonstration script.", ["Tokens"] + units, rate_rows, row_header=True)
    if exists("layers-4b.json"):
        four = data("layers-4b.json")
        col = four["columns"]
        out["layers4b"] = table(
            "Qwen3.5-4B set, numbers per layer. The first three value columns were measured by this repository with position 0 dropped. "
            "The others were recorded by the original project.",
            ["Layer", col["state_mid"], col["state_post"], col["mlp"], col["mlp_train"], col["on_per_token"], col["alive"], col["always"], col["always_energy"]],
            [[str(r["layer"]), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"],
              r["alive_text"], r["always_text"], r["always_energy"]] for r in four["rows"]])
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


# ------------------------------------------------------------------------------------------------ the page
def conditional(page: str, name: str, keep: bool) -> str:
    pattern = re.compile(rf"<!--if {name}-->(.*?)<!--endif {name}-->", flags=re.S)
    assert pattern.search(page), f"no block for {name!r} in the template"
    return pattern.sub((lambda m: m.group(1)) if keep else "", page)


def main() -> None:
    facts = data("facts.json")["facts"]
    demo = data("demo.json")
    with open(os.path.join(HERE, "tools", "page.template.html")) as f:
        page = f.read()
    page = page[:page.index("<!--")] + page[page.index("-->") + 4:]          # the template's own header comment
    page = conditional(page, "4b", exists("layers-4b.json"))
    page = conditional(page, "steer", exists("steer.json"))
    page = re.sub(r"<!--.*?-->", "", page, flags=re.S)                        # the template's remaining notes are not part of the page

    figures = {name: n for n, name in enumerate(re.findall(r'<figure[^>]*\bid="fig-([a-z0-9-]+)"', page), start=1)}
    sections = re.findall(r'<h2 id="([a-z0-9-]+)">(.*?)</h2>', page, flags=re.S)
    built, used = tables(), set()

    def fill(match: re.Match) -> str:
        key = match.group(1)
        parts = key.split("|")
        if parts[0] == "table":
            return built[parts[1]]
        if parts[0] == "fig":
            return str(figures[parts[1]])
        if parts[0] in ("share", "ci"):
            e = demo["shares"][parts[1]][parts[2]]["even"]
            return e["s"] if parts[0] == "share" else f"{e['s']} ({e['slo']} to {e['shi']})"
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
