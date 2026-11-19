"""Load the site in a headless browser and exercise it.

    python -B tools/verify_browser.py --repo <statescope checkout> [--shots <folder for screenshots>] [--port 8765]

Needs playwright with Chromium. Serves the site folder itself with python's http.server on 127.0.0.1.
Checks: no console error, no failed request, no request to another host, no horizontal page scroll at desktop and phone width,
light and dark; every cell x swap x set of items shows the share of data/demo.json; items, chain steps, tables, the layer slider
(by keyboard) and the link comparison show the values of the data files; no "NaN" or "undefined" anywhere; every number that the
page shows after these interactions is traceable (the rule of tools/lint_page.py, with the data files added).
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
counts = {"shares": 0, "items": 0, "layers": 0, "link": 0, "toggles": 0, "nodes": 0}


def data(name: str) -> dict:
    with open(os.path.join(HERE, "data", name)) as f:
        return json.load(f)


def expect(ok: bool, message: str) -> None:
    if not ok:
        problems.append(message)


VISIBLE_TEXT = """() => {
  const skip = (n) => n.closest('[data-axis], .textbox, script, style, noscript');
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (!skip(n.parentElement)) out.push(n.textContent);
  for (const e of document.querySelectorAll('[aria-label]')) out.push(e.getAttribute('aria-label'));
  return out.join('\\n');
}"""


async def open_page(browser, url: str, width: int, height: int, scheme: str, log: list):
    ctx = await browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    page = await ctx.new_page()
    page.on("console", lambda m: log.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: log.append(f"page error: {e}"))
    page.on("requestfailed", lambda r: log.append(f"request failed: {r.url}"))
    page.on("request", lambda r: log.append(f"request to another host: {r.url}") if not r.url.startswith(url) else None)
    page.on("response", lambda r: log.append(f"status {r.status}: {r.url}") if r.status >= 400 else None)
    await page.goto(url + "index.html", wait_until="networkidle")
    await page.wait_for_selector("#forest .forest-row")
    await page.wait_for_selector("#clean-box pre")
    await page.wait_for_selector("#layer-panels svg")
    return ctx, page


async def basic(page, name: str, width: int) -> None:
    scroll = await page.evaluate("document.documentElement.scrollWidth")
    expect(scroll <= width, f"{name}: the page scrolls sideways ({scroll} > {width})")
    html_text = await page.content()
    for needle in ("NaN", "undefined", "[object"):
        expect(needle not in html_text, f"{name}: {needle!r} in the page")
    fonts = await page.evaluate("Promise.all([document.fonts.load('15px \"Site Sans\"'), document.fonts.load('12px \"Geist Mono\"')]).then(r => r.map(x => x.length))")
    expect(all(n > 0 for n in fonts), f"{name}: a typeface did not load {fonts}")


async def full_pass(page, demo: dict, layers: dict, splice: dict, corpus: str) -> None:
    cells = [c["key"] for c in demo["cells"]]
    arms = demo["arms"]
    seen_text = [await page.evaluate(VISIBLE_TEXT)]

    # every cell x swap x set of items
    await page.click('[data-toggle="items-table"]')
    for cell in cells:
        await page.click(f'#cell-seg button[data-value="{cell}"]')
        for half in ("even", "odd", "all"):
            await page.click(f'#half-seg button[data-value="{half}"]')
            for arm in arms:
                await page.select_option("#arm-select", arm["key"])
                e = demo["shares"][cell][arm["key"]][half]
                big = await page.inner_text("#share-big")
                interval = await page.inner_text("#share-interval")
                expect(big == e["s"], f"share {cell} {arm['key']} {half}: page {big!r}, data {e['s']!r}")
                expect(interval == f"bootstrap interval {e['slo']} to {e['shi']}", f"interval {cell} {arm['key']} {half}: {interval!r}")
                counts["shares"] += 1
                if half == "even":
                    rows = await page.eval_on_selector_all("#items-table tbody tr", "rows => rows.map(r => [...r.cells].map(c => c.textContent))")
                    m = demo["margins"][cell]
                    expect(len(rows) == demo["items"], f"items table {cell} {arm['key']}: {len(rows)} rows")
                    for i in (0, 17, 63):
                        expect(rows[i][2:] == [m["clean"][i], m["corrupt"][i], m["arms"][arm["key"]][i]], f"items table {cell} {arm['key']} item {i}: {rows[i]}")
                    marks = await page.eval_on_selector_all("#items-plot .pt-patched", "n => n.length")
                    expect(marks == demo["items"], f"items plot {cell} {arm['key']}: {marks} marks")
            if half == "even":
                forest = await page.eval_on_selector_all("#forest button.forest-row .value", "n => n.map(x => x.textContent)")
                main = [a for a in arms if a["group"] == "main"]
                want = [f"{e['s']} ({e['slo']} to {e['shi']})" for e in (demo["shares"][cell][a["key"]]["even"] for a in main)]
                expect(forest == want, f"forest {cell}: {forest}")
        seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # the link comparison, both bases, every cell and set of items
    for cell in cells:
        await page.click(f'#cell-seg button[data-value="{cell}"]')
        for half in ("even", "odd", "all"):
            await page.click(f'#half-seg button[data-value="{half}"]')
            for base in demo["link_labels"]["bases"]:
                await page.click(f'#base-seg button[data-value="{base}"]')
                shown = await page.eval_on_selector_all("#link-panels .hbar-label b", "n => n.map(x => x.textContent)")
                want = []
                for route in demo["link_labels"]["routes"]:
                    for row in demo["link_table"][half]:
                        if row["part"] != "random" and row["base"] != base:
                            continue
                        want.append(row["cells"][cell].get(route, "not measured"))
                expect(shown == want, f"link {cell} {half} {base}: {shown} != {want}")
                counts["link"] += 1
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # items: by the number field, by the buttons, by a click in the plot; texts against the data files
    await page.click('#half-seg button[data-value="even"]')
    for cell_info in demo["cells"]:
        cell = cell_info["key"]
        items = data(cell_info["file"])["items"]
        await page.click(f'#cell-seg button[data-value="{cell}"]')
        await page.select_option("#arm-select", "head_o")
        for i in (0, 5, 31, 63):
            await page.fill("#item-number", str(i))
            await page.press("#item-number", "Enter")
            await page.wait_for_function(f"document.getElementById('clean-box').dataset.shown === '{cell}/{i}'")
            title = await page.inner_text("#viewer-title")
            expect(title.startswith(f"Item {i} of {cell}"), f"viewer title {title!r}")
            clean = await page.eval_on_selector("#clean-box pre", "n => n.textContent")
            corrupt = await page.eval_on_selector("#corrupt-box pre", "n => n.textContent")
            expect(clean.replace("↵", "") == "".join(items[i]["clean"]), f"clean text {cell} {i}")
            expect(corrupt.replace("↵", "") == "".join(items[i]["corrupt"]), f"corrupt text {cell} {i}")
            last = await page.eval_on_selector("#clean-box .tok.last", "n => n.textContent")
            expect(last == items[i]["clean"][-1], f"last token {cell} {i}: {last!r}")
            inside = await page.evaluate("""() => ['clean-box', 'corrupt-box'].every((id) => {
              const box = document.getElementById(id).getBoundingClientRect();
              const tok = document.querySelector('#' + id + ' .tok.last').getBoundingClientRect();
              return tok.left >= box.left && tok.right <= box.right && tok.top >= box.top && tok.bottom <= box.bottom;
            })""")
            expect(inside, f"the last token of {cell} item {i} is outside the visible part of its box")
            marked = await page.eval_on_selector_all("#clean-box .tok.gb", "n => n.length")
            expect(marked == items[i]["gate"][str(demo["constants"]["l9_transforms"][0])].count("1"), f"gate marks {cell} {i}: {marked}")
            m = demo["margins"][cell]
            cm = await page.inner_text("#clean-margins")
            xm = await page.inner_text("#corrupt-margins")
            expect(cm == f"margin {m['clean'][i]} · with the swap {m['arms']['head_o'][i]}", f"clean margins {cell} {i}: {cm!r}")
            expect(xm == f"margin {m['corrupt'][i]}", f"corrupt margins {cell} {i}: {xm!r}")
            wide = await page.evaluate("[...document.querySelectorAll('.textbox pre')].every(p => getComputedStyle(p).whiteSpace === 'pre')")
            expect(wide, "a text box wraps its text")
            counts["items"] += 1
        await page.click("#item-prev")
        expect(await page.input_value("#item-number") == "62", "previous-item button")
        cols = page.locator("#items-plot .item-col")
        await cols.nth(10).click()
        expect(await page.input_value("#item-number") == "10", "click on an item in the plot")
        await page.click('#sort-seg button[data-value="clean"]')
        await page.click('#sort-seg button[data-value="index"]')
    await page.locator("#items-plot .item-col").nth(20).hover()
    tip = await page.inner_text("#tip")
    expect("Item 20" in tip and demo["margins"][cells[-1]]["clean"][20] in tip, f"tooltip {tip!r}")
    await page.uncheck("#show-b")
    expect(not await page.evaluate("document.getElementById('clean-box').classList.contains('show-b')"), "gate checkbox")
    await page.check("#show-b")
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    # chain steps, by pointer and by keyboard
    c = demo["constants"]
    expected = {"t8": f"l8/t{c['l8_transform']}", "g8": f"l8/g{c['l8_group']}", "mixer": "head_o", "g9": f"link/mix/g{c['l9_group']}/F2",
                "t9a": f"l9/t{c['l9_transforms'][0]}", "t9b": f"l9/t{c['l9_transforms'][1]}"}
    for node, arm in expected.items():
        await page.click(f'#chain button[data-node="{node}"]')
        expect(await page.input_value("#arm-select") == arm, f"chain step {node} did not load {arm}")
        visible = await page.eval_on_selector_all(".node-panel", "n => n.filter(x => getComputedStyle(x).display !== 'none').map(x => x.id)")
        expect(len(visible) == 1, f"chain step {node}: panels {visible}")
        counts["nodes"] += 1
        seen_text.append(await page.evaluate(VISIBLE_TEXT))
    await page.focus('#chain button[data-node="g8"]')
    await page.keyboard.press("Enter")
    expect(await page.input_value("#arm-select") == expected["g8"], "chain step by keyboard")
    await page.locator('#panel-g8 .related button').nth(2).click()
    expect(await page.input_value("#arm-select") == "l8/full_post8", "related-swap button")
    await page.locator("#forest button.forest-row").nth(1).focus()
    await page.keyboard.press("Space")
    expect(await page.input_value("#arm-select") == "head_o", "forest row by keyboard")

    # layers: the slider by keyboard, the position-0 switch, the tables
    await page.focus("#layer-range")
    for layer in range(1, len(layers["rows"])):
        await page.keyboard.press("ArrowRight")
        r = layers["rows"][layer]
        got = await page.eval_on_selector_all("#layer-readout b", "n => n.map(x => x.textContent)")
        want = [str(layer), r["dropped"]["state_mid"], r["dropped"]["state_post"], r["dropped"]["mlp"], r["mlp_train"], r["on_per_token"], r["alive_text"], r["penalty"]]
        expect(got == want, f"layer readout {layer}: {got}")
        s = splice["rows"][layer]
        got = await page.eval_on_selector_all("#splice-readout b", "n => n.map(x => x.textContent)")
        expect(got == [str(layer), s["state"], s["mlp"]], f"splice readout {layer}: {got}")
        counts["layers"] += 1
    await page.click('#p0-seg button[data-value="with_p0"]')
    got = await page.eval_on_selector_all("#layer-readout b", "n => n.map(x => x.textContent)")
    r = layers["rows"][-1]
    expect(got[1:4] == [r["with_p0"]["state_mid"], r["with_p0"]["state_post"], r["with_p0"]["mlp"]], f"position 0 included: {got}")
    box = await page.locator("#layer-panels .plot svg").first.bounding_box()
    await page.locator("#layer-panels .plot svg").first.hover(position={"x": box["width"] * 0.5, "y": box["height"] * 0.5})
    expect(await page.input_value("#layer-range") not in ("", str(len(layers["rows"]) - 1)), "pointer on a layer panel")
    panels = await page.eval_on_selector_all("#layer-panels .plot svg, #splice-panels .plot svg", "n => n.length")
    expect(panels == 6, f"{panels} layer panels")
    for button in await page.query_selector_all("[data-toggle]"):
        target = await button.get_attribute("data-toggle")
        if await button.get_attribute("aria-expanded") == "false":
            await button.click()
        shown = await page.evaluate(f"getComputedStyle(document.getElementById('{target}')).display !== 'none' && document.querySelector('#{target} table') !== null")
        expect(shown, f"table {target} does not open")
        counts["toggles"] += 1
    seen_text.append(await page.evaluate(VISIBLE_TEXT))

    bad = lint_page.untraceable("\n".join(seen_text), corpus)
    expect(not bad, f"numbers shown that are not traceable: {bad}")
    html_text = await page.content()
    for needle in ("NaN", "undefined", "[object"):
        expect(needle not in html_text, f"after the interactions: {needle!r} in the page")


async def run(args) -> None:
    url = f"http://127.0.0.1:{args.port}/"
    demo, layers, splice = data("demo.json"), data("layers.json"), data("splice.json")
    corpus = lint_page.source_text(args.repo) + "\n" + lint_page.data_values(lint_page.PAGE_DATA)
    corpus += "\n" + " ".join(str(i) for i in range(demo["items"]))          # item numbers are positions in the item file, not measurements
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, width, height, scheme in (("desktop-light", 1280, 900, "light"), ("desktop-dark", 1280, 900, "dark"),
                                            ("phone-light", 375, 800, "light"), ("phone-dark", 375, 800, "dark"), ("tablet-light", 820, 1000, "light")):
            log: list[str] = []
            ctx, page = await open_page(browser, url, width, height, scheme, log)
            await basic(page, name, width)
            if name in ("desktop-light", "phone-light"):
                await full_pass(page, demo, layers, splice, corpus)
                await basic(page, name + " after the interactions", width)
            if args.shots:
                os.makedirs(args.shots, exist_ok=True)
                await page.screenshot(path=os.path.join(args.shots, f"{name}.png"), full_page=True)
            for line in log:
                problems.append(f"{name}: {line}")
            print(f"{name}: loaded, {len(log)} console or network problems")
            await ctx.close()
        # without JavaScript the text and the tables must still be there
        ctx = await browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        await page.goto(url + "index.html")
        tables = await page.locator("table:visible").count()
        expect(tables == 4, f"without JavaScript: {tables} tables visible")
        expect(await page.locator(".node-panel:visible").count() == 5, "without JavaScript: the chain's texts are not all visible")
        expect(await page.locator(".needs-js:visible").count() == 0, "without JavaScript: an empty interactive block is visible")
        print(f"no JavaScript: {tables} tables visible")
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
