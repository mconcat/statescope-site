"""Load the site in a headless browser and exercise it.

    python -B tools/verify_browser.py --repo <statescope checkout> [--shots <folder for screenshots>] [--port 8765]

Needs playwright with Chromium. Serves the site folder itself with python's http.server on 127.0.0.1.
Checks: no console error, no failed request, no request to another host, no horizontal page scroll at desktop, tablet and phone
width, light and dark; the first figure (built without a browser) holds the tokens, gates and character counts of the item file and
its text sits on the scale of one character; every cell x swap x set of items shows the share of data/demo.json; the chain, the
items, the pair viewer, the link comparison, the tables, the layer panels (by keyboard and by pointer) and the 4B panels show the
values of the data files; the dose figure shows the share, interval, mean margin and item margins of data/steer.json at every unit,
cell and dose; the two count figures show the values of data/count-curve.json and data/count-readout.json; the bars of the 4B
examples show the values of data/used-4b.json; no "NaN" or "undefined" anywhere; every number that the page shows after these interactions is traceable
(the rule of tools/lint_page.py, with the data files added); without JavaScript the text, the first figure and the tables are there.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_page  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

HERE = lint_page.HERE
problems: list[str] = []
counts = {"shares": 0, "chain rows": 0, "items": 0, "layers": 0, "link": 0, "tables": 0, "lead tokens": 0, "doses": 0, "count readouts": 0, "bars": 0}
VIEWS = (("desktop-light", 1280, 900, "light"), ("desktop-dark", 1280, 900, "dark"), ("tablet-light", 820, 1100, "light"),
         ("tablet-dark", 820, 1100, "dark"), ("phone-light", 375, 800, "light"), ("phone-dark", 375, 800, "dark"))
TAIL_LINES = 6          # lines of a text that the pair viewer shows before "whole text" is chosen (assets/js/demo.js)


def data(name: str) -> dict:
    with open(os.path.join(HERE, "data", name)) as f:
        return json.load(f)


def expect(ok: bool, message: str) -> None:
    if not ok:
        problems.append(message)


def lines_of(pieces: list[str]) -> list[list[int]]:
    out: list[list[int]] = [[]]
    for i, piece in enumerate(pieces):
        out[-1].append(i)
        if piece == "\n":
            out.append([])
    return [line for line in out if line]


# the text a reader sees, without the item texts, the axis ticks and the code blocks (those are data or code, not claims)
VISIBLE_TEXT = """() => {
  const skip = (n) => n.closest('[data-axis], [data-items], .ttext, .tip .t, script, style, noscript');
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (!skip(n.parentElement)) out.push(n.textContent);
  for (const e of document.querySelectorAll('[aria-label]')) out.push(e.getAttribute('aria-label'));
  return out.join('\\n');
}"""

TOKENS = """(sel) => [...document.querySelectorAll(sel + ' .tline')].map(line => ({
  count: line.querySelector('.count')?.textContent ?? null,
  toks: [...line.querySelectorAll('.tok')].map(t => ({ text: t.textContent, cls: t.className, i: +t.dataset.i, c: +t.dataset.c,
                                                       left: t.offsetLeft, width: t.getBoundingClientRect().width })) }))"""


async def open_page(browser, url: str, width: int, height: int, scheme: str, log: list):
    ctx = await browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    page = await ctx.new_page()
    page.on("console", lambda m: log.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: log.append(f"page error: {e}"))
    page.on("requestfailed", lambda r: log.append(f"request failed: {r.url}"))
    page.on("request", lambda r: log.append(f"request to another host: {r.url}") if not r.url.startswith(url) else None)
    page.on("response", lambda r: log.append(f"status {r.status}: {r.url}") if r.status >= 400 else None)
    await page.goto(url + "index.html", wait_until="networkidle")
    await page.wait_for_selector("#chain .chain-row .value")
    await page.wait_for_selector("#clean-box .tok")
    await page.wait_for_selector("#items-plot svg")
    for sel, name in (("#steer-items-plot svg", "steer.json"), ("#curve-plot svg", "count-curve.json"), ("#read-lines svg", "count-readout.json")):
        if os.path.exists(os.path.join(HERE, "data", name)):
            await page.wait_for_selector(sel)
    return ctx, page


async def open_folds(page) -> None:
    """the blocks that stay closed until asked for (training details, numbers per layer, what was checked) are opened by their summaries"""
    for i in range(await page.locator("details.fold").count()):
        d = page.locator("details.fold").nth(i)
        if await d.get_attribute("open") is None:
            await d.locator("> summary").click()
    await page.wait_for_selector("#layer-panels svg")


async def basic(page, name: str, width: int) -> None:
    scroll = await page.evaluate("document.documentElement.scrollWidth")
    expect(scroll <= width, f"{name}: the page scrolls sideways ({scroll} > {width})")
    html_text = await page.content()
    for needle in ("NaN", "undefined", "[object"):
        expect(needle not in html_text, f"{name}: {needle!r} in the page")
    fonts = await page.evaluate("Promise.all([document.fonts.load('15px \"Site Sans\"'), document.fonts.load('12px \"Geist Mono\"')]).then(r => r.map(x => x.length))")
    expect(all(n > 0 for n in fonts), f"{name}: a typeface did not load {fonts}")
    ids = await page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id)")
    expect(len(ids) == len(set(ids)), f"{name}: an id is used twice: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    numbers = await page.eval_on_selector_all("figure[id] > figcaption > b:first-child", "n => n.map(x => x.textContent)")
    expect(numbers == [f"Figure {i}." for i in range(1, len(numbers) + 1)] and len(numbers) >= 8, f"{name}: figure numbers {numbers}")


async def lead_figure(page, demo: dict, name: str, width: int) -> None:
    """the first figure against the item file: tokens, gates, character counts, and the scale of one character"""
    lead, c = demo["lead"], demo["constants"]
    info = next(x for x in demo["cells"] if x["key"] == lead["cell"])
    item = data(info["file"])["items"][lead["item"]]
    units = [str(c["l8_transform"])] + [str(t) for t in c["l9_transforms"]]
    want = lines_of(item["clean"])[-lead["lines"]:]
    got = await page.evaluate(TOKENS, "#fig-lead")
    expect(len(got) == len(want), f"{name}: first figure has {len(got)} lines")
    cw = await page.evaluate("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--cw'))")
    for line, idx in zip(got, want):
        expect([t["i"] for t in line["toks"]] == idx, f"{name}: first figure, token indices of a line")
        end = idx[-2] if item["clean"][idx[-1]] == "\n" else idx[-1]
        expect(line["count"] == str(item["chars"][end]), f"{name}: first figure, count at the end of a line {line['count']!r}")
        for t in line["toks"]:
            i = t["i"]
            piece = item["clean"][i]
            expect(t["text"] == ("⏎" if piece == "\n" else piece), f"{name}: first figure, token {i} text {t['text']!r}")
            cls = set(t["cls"].split())
            for letter, unit in zip("abc", units):
                expect((letter in cls) == (item["gate"][unit][i] == "1"), f"{name}: first figure, token {i} gate of {unit}")
            expect(t["c"] == item["chars"][i], f"{name}: first figure, token {i} characters {t['c']}")
            expect(("last" in cls) == (i == len(item["clean"]) - 1), f"{name}: first figure, last-token mark at {i}")
            if piece != "\n":                                                 # one character is one unit of the horizontal axis
                expect(abs(t["left"] - (item["chars"][i] - len(piece)) * cw) < 1.0 and abs(t["width"] - len(piece) * cw) < 1.0,
                       f"{name}: first figure, token {i} is not on the character scale (left {t['left']}, width {t['width']}, character {cw})")
            counts["lead tokens"] += 1
    strips = await page.eval_on_selector_all("#fig-lead .tmap-line", "n => n.map(l => l.children.length)")
    expect(strips == [len(idx) for idx in want], f"{name}: strips of the first figure {strips}")
    bars = await page.eval_on_selector_all("#fig-lead .rates .bin", """n => n.map(b => ({ bin: b.dataset.bin, r: [...b.querySelectorAll('.bar')].map(x =>
        [x.style.getPropertyValue('--r'), x.getBoundingClientRect().height, x.textContent]), h: b.getBoundingClientRect().height, w: b.getBoundingClientRect().width }))""")
    names = [f"L9 transform {t}" for t in c["l9_transforms"]]
    for j, b in enumerate(bars):
        for k, n_ in enumerate(names):
            rate = demo["firing_rate"][n_]["by_chars_in_line"][j]
            expect(b["bin"] == rate["bin"] and b["r"][k][0] == rate["rate"], f"{name}: rate bar {b['bin']} of {n_}: {b['r'][k]}")
            expect(abs(b["r"][k][1] - max(1.0, float(rate["rate"]) * b["h"])) < 1.2, f"{name}: height of rate bar {b['bin']} of {n_}")
            expect(b["r"][k][2] in ("", rate["rate"]), f"{name}: label of rate bar {b['bin']} of {n_}: {b['r'][k][2]!r}")
        if width >= 1000:
            expect(abs(b["w"] - c["char_bin"] * cw) < 1.0, f"{name}: rate bin {b['bin']} is not {c['char_bin']} characters wide")
    visible = await page.evaluate("getComputedStyle(document.querySelector('#fig-lead .tmap')).display !== 'none'")
    fits = await page.evaluate("(() => { const b = document.querySelector('#fig-lead .tscroll'); return b.scrollWidth <= b.clientWidth + 1; })()")
    expect(fits or visible, f"{name}: the first figure's text does not fit and the strips are hidden")


async def full_pass(page, demo: dict, layers: dict, splice: dict, corpus: str, name: str) -> None:
    cells = [c["key"] for c in demo["cells"]]
    arms = demo["arms"]
    c = demo["constants"]
    units = [str(c["l8_transform"])] + [str(t) for t in c["l9_transforms"]]
    seen_text = [await page.evaluate(VISIBLE_TEXT)]
    chain_arms = await page.eval_on_selector_all("#chain .chain-row", "n => n.map(x => x.dataset.arm)")
    expect(len(chain_arms) == 14 and set(chain_arms) <= {a["key"] for a in arms}, f"chain rows {chain_arms}")

    # every cell x swap x set of items: the share, its interval, the means behind it, the chain, the items
    await page.evaluate("document.getElementById('items-details').open = true")
    for cell in cells:
        await page.click(f'#fig-items [data-scope="cell"] button[data-value="{cell}"]')
        for half in ("even", "odd", "all"):
            await page.click(f'#fig-items [data-scope="half"] button[data-value="{half}"]')
            pressed = await page.eval_on_selector_all('[data-scope] button[aria-pressed="true"]', "n => n.map(x => x.dataset.value)")
            expect(set(pressed) == {cell, half}, f"the controls of the figures disagree: {pressed}")
            mean = demo["means"][cell][half]
            for arm in arms:
                await page.select_option("#arm-select", arm["key"])
                e = demo["shares"][cell][arm["key"]][half]
                big = await page.inner_text("#share-big")
                interval = await page.inner_text("#share-interval")
                means = await page.inner_text("#share-means")
                expect(big == e["s"], f"share {cell} {arm['key']} {half}: page {big!r}, data {e['s']!r}")
                expect(interval == f"bootstrap interval {e['slo']} to {e['shi']}", f"interval {cell} {arm['key']} {half}: {interval!r}")
                expect(means == f"mean(m_clean - m_patched) {mean['num'][arm['key']]} / mean(m_clean - m_corrupt) {mean['den']}, {mean['n']} items",
                       f"means {cell} {arm['key']} {half}: {means!r}")
                counts["shares"] += 1
                if half == "even":
                    rows = await page.eval_on_selector_all("#items-table tbody tr", "rows => rows.map(r => [...r.cells].map(c => c.textContent))")
                    m = demo["margins"][cell]
                    expect(len(rows) == demo["items"], f"items table {cell} {arm['key']}: {len(rows)} rows")
                    for i in (0, 17, 63):
                        expect(rows[i][2:] == [m["clean"][i], m["corrupt"][i], m["arms"][arm["key"]][i]], f"items table {cell} {arm['key']} item {i}: {rows[i]}")
                    marks = await page.eval_on_selector_all("#items-plot .pt-patched", "n => n.length")
                    expect(marks == demo["items"], f"items plot {cell} {arm['key']}: {marks} marks")
            dim = await page.eval_on_selector_all("#items-plot .item-col.dim", "n => n.length")
            expect(dim == (0 if half == "all" else demo["items"] // 2), f"items plot {cell} {half}: {dim} faded items")
            shown = await page.eval_on_selector_all("#chain .chain-row", """n => n.map(x => [x.dataset.arm, x.querySelector('.value').textContent,
                x.querySelector('.track').style.getPropertyValue('--v'), x.querySelector('.pt').getBoundingClientRect().left + 5.5 - x.querySelector('.track').getBoundingClientRect().left,
                x.querySelector('.track').getBoundingClientRect().width])""")
            for arm_key, text, v, dot, track in shown:
                e = demo["shares"][cell][arm_key][half]
                expect(text == f"{e['s']} ({e['slo']} to {e['shi']})", f"chain {cell} {half} {arm_key}: {text!r}")
                x = (e["v"] + 0.06) / 1.06                                   # the share axis of assets/js/demo.js
                expect(abs(float(v) - x) < 1e-6 and abs(dot - x * track) < 1.5, f"chain {cell} {half} {arm_key}: the dot is not at its share")
                counts["chain rows"] += 1
        seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # the link comparison, both changes, every cell and set of items
    for cell in cells:
        await page.click(f'#fig-link [data-scope="cell"] button[data-value="{cell}"]')
        for half in ("even", "odd", "all"):
            await page.click(f'#fig-link [data-scope="half"] button[data-value="{half}"]')
            for base in demo["link_labels"]["bases"]:
                await page.click(f'#base-seg button[data-value="{base}"]')
                shown = await page.eval_on_selector_all("#link-panels .hbar", "n => n.map(x => [x.querySelector('b').textContent, x.querySelector('i').style.getPropertyValue('--v')])")
                want = []
                for route in demo["link_labels"]["routes"]:
                    for row in demo["link_table"][half]:
                        if (row["part"] != "random" and row["base"] != base) or route not in row["cells"][cell]:
                            continue
                        want.append(row["cells"][cell][route])
                expect([s[0] for s in shown] == want, f"link {cell} {half} {base}: {shown} != {want}")
                expect(all(abs(float(v) - max(0.0, min(1.0, float(t)))) < 1e-9 for t, v in shown), f"link {cell} {half} {base}: a bar is not as long as its value")
                expect(len(want) == 11, f"link {cell} {half} {base}: {len(want)} bars")
                counts["link"] += 1
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # the pair viewer: by the number field, by the buttons, by a click in the plot; texts, gates and counts against the item files
    await page.click('#fig-items [data-scope="half"] button[data-value="even"]')
    for cell_info in demo["cells"]:
        cell = cell_info["key"]
        items = data(cell_info["file"])["items"]
        await page.click(f'#fig-pair [data-scope="cell"] button[data-value="{cell}"]')
        await page.select_option("#arm-select", "head_o")
        for i in (0, 5, 31, 63):
            await page.fill("#item-number", str(i))
            await page.press("#item-number", "Enter")
            await page.wait_for_function(f"document.getElementById('clean-box').dataset.shown === '{cell}/{i}'")
            title = await page.inner_text("#viewer-title")
            expect(title == f"Item {i} of {cell}, {'odd' if i % 2 else 'even'}-numbered", f"viewer title {title!r}")
            m = demo["margins"][cell]
            cm, xm = await page.inner_text("#clean-margins"), await page.inner_text("#corrupt-margins")
            expect(cm == f"margin {m['clean'][i]}; with the selected swap {m['arms']['head_o'][i]}", f"clean margins {cell} {i}: {cm!r}")
            expect(xm == f"margin {m['corrupt'][i]}", f"corrupt margins {cell} {i}: {xm!r}")
            for mode in ("tail", "all"):
                await page.click(f'#lines-seg button[data-value="{mode}"]')
                for kind, box in (("clean", "#clean-box"), ("corrupt", "#corrupt-box")):
                    pieces = items[i][kind]
                    want = lines_of(pieces)
                    want = want[-TAIL_LINES:] if mode == "tail" else want
                    got = await page.evaluate(TOKENS, box)
                    expect([[t["i"] for t in line["toks"]] for line in got] == want, f"{kind} text {cell} {i} {mode}: token indices")
                    expect("".join(t["text"] for line in got for t in line["toks"]).replace("⏎", "\n") == "".join(pieces[j] for line in want for j in line),
                           f"{kind} text {cell} {i} {mode}: text")
                    last = [t for line in got for t in line["toks"] if "last" in t["cls"].split()]
                    expect(len(last) == 1 and last[0]["i"] == len(pieces) - 1 and last[0]["text"] == pieces[-1], f"{kind} text {cell} {i} {mode}: last token")
                    if kind == "clean":
                        for letter, unit in zip("abc", units):
                            marked = [t["i"] for line in got for t in line["toks"] if letter in t["cls"].split()]
                            expect(marked == [j for line in want for j in line if items[i]["gate"][unit][j] == "1"], f"gate marks of {unit}, {cell} {i} {mode}")
                        expect(all(t["c"] == items[i]["chars"][t["i"]] for line in got for t in line["toks"]), f"character counts {cell} {i} {mode}")
                        unknown = [t["i"] for line in got for t in line["toks"] if "u" in t["cls"].split()]
                        expect(unknown == [j for line in want for j in line if items[i]["known"][j] == "0"], f"tokens without a known count {cell} {i} {mode}")
                    for line, idx in zip(got, want):                          # the count after a line is the number of its characters
                        text = "".join(pieces[j] for j in idx).rstrip("\n")
                        expect(line["count"] in (None, str(len(text))), f"{kind} text {cell} {i} {mode}: count {line['count']!r} for a line of {len(text)}")
                    inside = await page.evaluate("""(sel) => { const box = document.querySelector(sel).getBoundingClientRect();
                      const tok = document.querySelector(sel + ' .tok.last').getBoundingClientRect();
                      return tok.left >= box.left - 1 && tok.right <= box.right + 1; }""", box)
                    expect(inside, f"the last token of the {kind} text of {cell} item {i} ({mode}) is outside the visible part of its box")
            await page.click('#lines-seg button[data-value="tail"]')
            pre = await page.evaluate("[...document.querySelectorAll('#viewer .tline')].every(p => getComputedStyle(p).whiteSpace === 'pre')")
            expect(pre, "a text box wraps its text")
            counts["items"] += 1
        await page.click("#item-prev")
        expect(await page.input_value("#item-number") == "62", "previous-item button")
        await page.click("#item-next")
        await page.click("#item-next")
        expect(await page.input_value("#item-number") == "0", "next-item button wraps around")
        cols = page.locator("#items-plot .item-col")
        tenth = await cols.nth(10).get_attribute("data-item")                  # the items stand in the order of their clean margin
        await cols.nth(10).click()
        expect(await page.input_value("#item-number") == tenth, "click on an item in the plot")
        await page.click('#sort-seg button[data-value="clean"]')
        order = await page.eval_on_selector_all("#items-plot .item-col", "n => n.map(x => +x.dataset.item)")
        clean = [float(v) for v in demo["margins"][cell]["clean"]]
        expect(sorted(order) == list(range(demo["items"])) and all(clean[a] >= clean[b] for a, b in zip(order, order[1:])), f"order by clean margin, {cell}")
        await page.click('#sort-seg button[data-value="index"]')
    await page.locator("#items-plot .item-col").nth(20).hover()
    tip = await page.inner_text("#tip")
    expect("Item 20" in tip and demo["margins"][cells[-1]]["clean"][20] in tip, f"tooltip {tip!r}")
    await page.locator("#items-plot .item-col").nth(33).focus()
    await page.keyboard.press("Enter")
    expect(await page.input_value("#item-number") == "33", "an item of the plot by keyboard")
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # the chain: every row by pointer, one by keyboard
    for arm_key in chain_arms:
        await page.click(f'#chain .chain-row[data-arm="{arm_key}"]')
        expect(await page.input_value("#arm-select") == arm_key, f"chain row {arm_key} did not load its swap")
        pressed = await page.eval_on_selector_all('#chain .chain-row[aria-pressed="true"]', "n => n.map(x => x.dataset.arm)")
        expect(pressed == [arm_key], f"chain row {arm_key}: pressed {pressed}")
        what = await page.inner_text("#share-what")
        arm = next(a for a in arms if a["key"] == arm_key)
        expect(what == f"{arm['label']}. {arm['what']}", f"chain row {arm_key}: description {what!r}")
    await page.focus(f'#chain .chain-row[data-arm="{chain_arms[3]}"]')
    await page.keyboard.press("Enter")
    expect(await page.input_value("#arm-select") == chain_arms[3], "chain row by keyboard")
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # layers: the slider by keyboard, the position-0 switch, the pointer; spliced-in loss by pointer
    async def hover_layer(selector: str, layer: int, n: int) -> None:
        box = await page.locator(selector).first.bounding_box()
        await page.locator(selector).first.hover(position={"x": 40 + layer / (n - 1) * (box["width"] - 50), "y": box["height"] * 0.5})

    await page.locator("#layer-range").scroll_into_view_if_needed()
    await page.focus("#layer-range")
    await page.keyboard.press("Home")
    n = len(layers["rows"])
    for layer in range(n):
        if layer:
            await page.keyboard.press("ArrowRight")
        r = layers["rows"][layer]
        got = await page.eval_on_selector_all("#layer-readout b", "n => n.map(x => x.textContent)")
        want = [str(layer), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"], r["alive_text"], r["penalty"]]
        expect(got == want, f"layer readout {layer}: {got}")
        await hover_layer("#splice-panels .plot svg", layer, n)
        s = splice["rows"][layer]
        got = await page.eval_on_selector_all("#splice-readout b", "n => n.map(x => x.textContent)")
        expect(got == [str(layer), s["state"], s["mlp"]], f"splice readout {layer}: {got}")
        counts["layers"] += 1
    await page.click('#p0-seg button[data-value="with_p0"]')
    got = await page.eval_on_selector_all("#layer-readout b", "n => n.map(x => x.textContent)")
    r = layers["rows"][-1]
    expect(got[1:4] == [r["with_p0"]["state_mid"], r["with_p0"]["state_post"], r["with_p0"]["mlp"]], f"position 0 included: {got}")
    await hover_layer("#layer-panels .plot svg", 6, n)
    expect(await page.input_value("#layer-range") == "6", "pointer on a layer panel")
    marks = await page.eval_on_selector_all("#layer-panels .panel", "n => n.map(p => [p.querySelectorAll('.plot .mark').length, p.querySelectorAll('.bar-rect').length])")
    expect(marks == [[2 * n, 0], [2 * n, 0], [n, 0], [0, n]], f"marks of the layer panels {marks}")
    marks = await page.eval_on_selector_all("#splice-panels .panel", "n => n.map(p => p.querySelectorAll('.mark.recorded').length)")
    expect(marks == [n, n], f"marks of the spliced-in loss panels {marks}")
    await page.click('#p0-seg button[data-value="dropped"]')
    if os.path.exists(os.path.join(HERE, "data", "layers-4b.json")):
        four = data("layers-4b.json")["rows"]
        await page.focus("#b4-range")
        await page.keyboard.press("Home")
        for layer, r in enumerate(four):
            if layer:
                await page.keyboard.press("ArrowRight")
            got = await page.eval_on_selector_all("#b4-readout b", "n => n.map(x => x.textContent)")
            want = [str(layer), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["alive_text"], r["always_text"], r["always_energy"]]
            expect(got == want, f"4B readout {layer}: {got}")
            counts["layers"] += 1
        marks = await page.eval_on_selector_all("#b4-panels .panel", "n => n.map(p => [p.querySelectorAll('.plot .mark').length, p.querySelectorAll('.bar-rect').length])")
        expect(marks == [[2 * len(four), 0], [2 * len(four), 0], [0, len(four)], [len(four), 0]], f"marks of the 4B panels {marks}")
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    seen_text += await new_figures(page, demo)

    # every table behind a "Table" line opens
    for i in range(await page.locator("details.more").count()):
        d = page.locator("details.more").nth(i)
        if await d.get_attribute("open") is None:
            await d.locator("summary").click()
        expect(await d.locator("table").count() == 1 and await d.locator("table").is_visible(), f"table {i} does not open")
        counts["tables"] += 1
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # a hint on a token of the first figure
    tok = page.locator("#fig-lead .ttext .tok.last")
    await tok.scroll_into_view_if_needed()
    await tok.hover()
    tip = await page.inner_text("#tip")
    expect("Last token" in tip and "characters" in tip, f"token hint {tip!r}")

    bad = lint_page.untraceable("\n".join(seen_text), corpus)
    expect(not bad, f"{name}: numbers shown that are not traceable: {bad}")
    html_text = await page.content()
    for needle in ("NaN", "undefined", "[object"):
        expect(needle not in html_text, f"after the interactions: {needle!r} in the page")


async def new_figures(page, demo: dict) -> list[str]:
    """the dose figure, the two count figures and the bars of the 4B examples against their data files; returns the text seen"""
    seen = []
    if os.path.exists(os.path.join(HERE, "data", "steer.json")):
        steer = data("steer.json")
        expect(await page.locator("#steer-unit option").count() == len(steer["units"]), "dose figure: units offered")
        for unit in steer["units"]:
            await page.select_option("#steer-unit", unit["key"])
            for cell, c in steer["cells"].items():
                await page.click(f'#steer-cell button[data-value="{cell}"]')
                a = c["arms"][unit["key"]]
                for i, alpha in enumerate(steer["alphas"]):
                    await page.fill("#steer-dose", str(i))
                    got = [await page.inner_text(sel) for sel in ("#steer-dose-value", "#steer-share", "#steer-interval", "#steer-mean", "#steer-items-title")]
                    expect(got[:2] == [alpha, a["share"][i]] and got[2].endswith(f" {a['lo'][i]} to {a['hi'][i]}") and got[3] == a["mean"][i] and got[4].endswith(f"= {alpha}"),
                           f"dose figure {unit['key']} {cell} {alpha}: {got}")
                    marks = await page.eval_on_selector_all("#steer-items-plot .item-col", "n => n.map(x => [+x.dataset.item, x.querySelector('.pt-patched').dataset.margin])")
                    expect(len(marks) == len(c["clean"]) and all(m == a["items"][i][j] for j, m in marks), f"dose figure {unit['key']} {cell} {alpha}: item margins")
                    chosen = await page.eval_on_selector_all("#steer-share-plot .mark.chosen, #steer-mean-plot .mark.chosen", "n => n.map(x => x.dataset.dose)")
                    expect(chosen == [alpha, alpha], f"dose figure {unit['key']} {cell} {alpha}: chosen marks {chosen}")
                    counts["doses"] += 1
                expect(await page.locator("#steer-key-ref-item").is_visible() == bool(unit["reference"]), f"dose figure {unit['key']}: reference line key")
            seen.append(await page.evaluate(VISIBLE_TEXT))
        i1 = steer["alphas"].index(steer["swap_dose"])                        # dose 1 is the demonstration's swap, on all items
        for cell in steer["cells"]:
            for unit in steer["units"]:
                expect(steer["cells"][cell]["arms"][unit["key"]]["share"][i1] == demo["shares"][cell][unit["key"]]["all"]["s"], f"dose 1 of {unit['key']} in {cell}")
    if os.path.exists(os.path.join(HERE, "data", "count-curve.json")):
        curve, read = data("count-curve.json"), data("count-readout.json")
        total = sum(len(w["counts"]) for w in curve["widths"].values())
        expect(await page.locator("#curve-plot .curve-pt").count() == total, "count curve: number of points")
        for count in (0, 7, 30, 60, 61, 100):
            await page.fill("#curve-count", str(count))
            got = await page.eval_on_selector_all("#curve-readout b", "n => n.map(x => x.textContent)")
            want = [str(count)] + [w["tokens"][count] for w in curve["widths"].values() if count < len(w["counts"])]
            expect(got == want, f"count curve readout at {count}: {got} != {want}")
            hot = await page.eval_on_selector_all("#curve-plot .curve-pt.hot", "n => n.map(x => x.dataset.count)")
            expect(hot == [str(count)] * (len(want) - 1), f"count curve: marked points at {count}: {hot}")
            counts["count readouts"] += 1
        for t in read["transforms"]:
            await page.click(f'#read-transform button[data-value="{t}"]')
            for w, d in read["widths"].items():
                await page.click(f'#read-width button[data-value="{w}"]')
                for count in (0, 25, len(d["counts"]) - 1):
                    await page.fill("#read-count", str(count))
                    got = await page.eval_on_selector_all("#read-readout b", "n => n.map(x => x.textContent)")
                    want = [str(count), d[t]["gate"][count], d[t]["frame"][count], read["threshold"][t], d[t]["rate"][count]]
                    expect(got == want, f"count readout {t} width {w} at {count}: {got} != {want}")
                    shade = await page.eval_on_selector_all(f'#read-plane .curve-pt[data-width="{w}"][data-count="{count}"]', "n => n.map(x => x.style.getPropertyValue('--t'))")
                    expect(len(shade) == 1 and abs(float(shade[0]) - float(d[t]["rate"][count])) < 1e-6, f"count readout {t} width {w} at {count}: shade {shade}")
                    counts["count readouts"] += 1
            seen.append(await page.evaluate(VISIBLE_TEXT))
        expect(await page.locator("#read-plane .read-arrow").count() == 2, "count readout: the read direction is not drawn")
    if os.path.exists(os.path.join(HERE, "data", "used-4b.json")):
        used = data("used-4b.json")
        bars = {fig: await page.eval_on_selector_all(f"#{fig} .hbar", """n => n.map(x => [x.querySelector('b').textContent,
            [...x.querySelectorAll('.hbar-track i')].map(i => ['--v', '--lo', '--hi'].map(k => i.style.getPropertyValue(k)))])""") for fig in ("fig-u1", "fig-u2", "fig-u3")}
        want1 = [b["value"] for b in used["rule"]["bars"]]
        expect([b[0] for b in bars["fig-u1"]] == want1 and [b[1][0][0] for b in bars["fig-u1"]] == want1, f"bars of the first 4B example: {bars['fig-u1']}")
        want2 = [f"{r['lo']} to {r['hi']}" for r in used["aba"]["ranges"]] + [v for f in used["aba"]["flips"] for v in (f["value"], f["twice"])]
        expect([b[0] for b in bars["fig-u2"]] == want2, f"bars of the second 4B example: {[b[0] for b in bars['fig-u2']]}")
        expect([b[1][0][1:] for b in bars["fig-u2"][:5]] == [[r["lo"], r["hi"]] for r in used["aba"]["ranges"]], "range bars of the second 4B example")
        js = used["js"]["bars"]
        expect([b[0] for b in bars["fig-u3"]] == [f"{js[0]['value']} ({js[0]['lo']} to {js[0]['hi']})"], f"bar of the third 4B example: {bars['fig-u3']}")
        counts["bars"] += sum(len(v) for v in bars.values())
        for fig in bars:                                                      # a bar is as long as its value on the track from 0 to 1
            sizes = await page.eval_on_selector_all(f"#{fig} .hbar-track", "n => n.map(t => [t.getBoundingClientRect().width, ...[...t.children].map(i => i.getBoundingClientRect().width)])")
            for (text, styles), size in zip(bars[fig], sizes):
                v, lo, hi = styles[0]
                length = float(v) if v else float(hi) - float(lo)
                expect(abs(size[1] - length * size[0]) < 1.5, f"{fig}: bar {text!r} is not as long as its value")
    if os.path.exists(os.path.join(HERE, "data", "examples-4b.json")):
        ex = data("examples-4b.json")
        shown = await page.eval_on_selector_all(".contexts li", "n => n.map(x => [x.textContent, x.querySelector('mark').textContent])")
        want = [[c.replace("[[", "").replace("]]", ""), c[c.index("[[") + 2:c.index("]]")]] for c in ex["contexts"]["aba"] + ex["contexts"]["less"]]
        expect(shown == want, f"natural-text contexts: {shown}")
        code = await page.eval_on_selector_all(".exp .codeblock code", "n => n.map(x => x.textContent)")
        expect(code == [ex["rule_sample"]], "the generated function of the first 4B example")
    return seen


async def run(args) -> None:
    url = f"http://127.0.0.1:{args.port}/"
    demo, layers, splice = data("demo.json"), data("layers.json"), data("splice.json")
    corpus = lint_page.source_text(args.repo) + "\n" + lint_page.data_values(lint_page.page_data())
    corpus += "\n" + " ".join(str(i) for i in range(demo["items"]))          # item numbers are positions in the item file, not measurements
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, width, height, scheme in VIEWS:
            log: list[str] = []
            ctx, page = await open_page(browser, url, width, height, scheme, log)
            await basic(page, name, width)
            await lead_figure(page, demo, name, width)
            if args.shots:                                                    # before the interactions: the page as a reader first sees it
                os.makedirs(args.shots, exist_ok=True)
                await page.screenshot(path=os.path.join(args.shots, f"{name}.png"), full_page=True)
                later = []                                                    # figures inside a closed block are taken once it is open
                for fig in await page.eval_on_selector_all("figure[id]", "n => n.map(f => f.id)"):
                    if await page.locator(f"#{fig}").is_visible():
                        await page.locator(f"#{fig}").screenshot(path=os.path.join(args.shots, f"{name}-{fig}.png"))
                    else:
                        later.append(fig)
            await open_folds(page)
            if args.shots:
                for fig in later:
                    await page.locator(f"#{fig}").screenshot(path=os.path.join(args.shots, f"{name}-{fig}.png"))
            await basic(page, name + " with the closed blocks opened", width)
            if name in ("desktop-light", "phone-light"):
                await full_pass(page, demo, layers, splice, corpus, name)
                await basic(page, name + " after the interactions", width)
            for line in log:
                problems.append(f"{name}: {line}")
            print(f"{name}: loaded, {len(log)} console or network problems")
            await ctx.close()
        # without JavaScript: the text, the first figure and the tables are there, and no empty interactive block shows
        ctx = await browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        await page.goto(url + "index.html")
        for i in range(await page.locator("details.fold").count()):
            await page.locator("details.fold").nth(i).locator("> summary").click()
        for i in range(await page.locator("details.more:visible").count()):
            await page.locator("details.more:visible").nth(i).locator("summary").click()
        tables = await page.locator("table:visible").count()
        want = 6 + 2 * os.path.exists(os.path.join(HERE, "data", "layers-4b.json"))   # shares, rates, link, layers, spliced-in loss, details; 4B: layers, details
        expect(tables == want, f"without JavaScript: {tables} tables visible, {want} expected")
        expect(await page.locator(".needs-js:visible").count() == 0, "without JavaScript: an empty interactive block is visible")
        expect(await page.locator("#fig-lead .tok:visible").count() > 100, "without JavaScript: the first figure is not there")
        expect(await page.locator("#fig-layer svg:visible").count() == 1, "without JavaScript: the schematic is not there")
        if args.shots:
            await page.screenshot(path=os.path.join(args.shots, "no-javascript.png"), full_page=True)
        print(f"no JavaScript: {tables} tables visible")
        await ctx.close()
        # print: the page lays out without its controls
        ctx = await browser.new_context(viewport={"width": 794, "height": 1123})
        page = await ctx.new_page()
        await page.goto(url + "index.html", wait_until="networkidle")
        await page.emulate_media(media="print")
        expect(await page.locator(".controls:visible").count() == 0, "print: controls are visible")
        expect(await page.evaluate("document.documentElement.scrollWidth") <= 794, "print: the page is wider than the sheet")
        if args.shots:
            await page.pdf(path=os.path.join(args.shots, "print.pdf"), format="A4", print_background=False)
        await ctx.close()
        await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--shots", default=None)
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = subprocess.Popen([sys.executable, "-m", "http.server", str(args.port), "--bind", "127.0.0.1", "--directory", HERE],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.0)
        asyncio.run(run(args))
    finally:
        server.terminate()
    print("interactions checked:", ", ".join(f"{v} {k}" for k, v in counts.items()))
    print(f"{len(problems)} problems")
    for line in problems[:60]:
        print("  PROBLEM:", line)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
