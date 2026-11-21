// The worked example: the pair viewer, the chain with its shares, one swap item by item, and the link comparison.
// All values are strings written by tools/build_data.py; this file only places them and converts them to coordinates.
import { svg, h, clear, linear, niceTicks, tickText, onResize, diamond, showTip, hideTip, segmented } from "./svg.js";
import { renderText, tokenHints } from "./tokens.js";

const HALF_LABEL = { even: "even-numbered", odd: "odd-numbered", all: "all" };
const TAIL_LINES = 6;
const X_MIN = -0.06; // the share axis starts a little below 0: an interval can reach below it
const X = (v) => Math.max(0, Math.min(1, (v - X_MIN) / (1 - X_MIN)));

export function initDemo(demo, load) {
  const c = demo.constants;
  const cells = demo.cells.map((x) => x.key);
  const arms = new Map(demo.arms.map((a) => [a.key, a]));
  const units = [String(c.l8_transform), ...c.l9_transforms.map(String)];
  const unitNames = [`L8 transform ${units[0]}`, `L9 transform ${units[1]}`, `L9 transform ${units[2]}`];
  const state = {
    cell: cells[0],
    half: "even",
    arm: `l8/t${c.l8_transform}`,
    item: 0,
    base: Object.keys(demo.link_labels.bases)[0],
    sort: "clean",
    lines: "tail",
  };
  const itemFiles = new Map();
  const items = (cell) => {
    const info = demo.cells.find((x) => x.key === cell);
    if (!itemFiles.has(cell)) itemFiles.set(cell, load(info.file));
    return itemFiles.get(cell);
  };
  const colourOf = (key) =>
    key.endsWith(`t${units[0]}`) || key.endsWith(`g${c.l8_group}`) ? "c-a" : key.endsWith(`t${units[1]}`) ? "c-b" : key.endsWith(`t${units[2]}`) ? "c-c" : "c-ink";

  // ---------------------------------------------------------------- controls shared by several figures
  const scoped = { cell: [], half: [] };
  for (const box of document.querySelectorAll('[data-scope="cell"]')) {
    for (const cell of cells) box.append(h("button", { type: "button", "data-value": cell, "aria-pressed": "false", text: cell }));
    scoped.cell.push(segmented(box, (value) => set({ cell: value })));
  }
  for (const box of document.querySelectorAll('[data-scope="half"]')) {
    for (const half of ["even", "odd", "all"]) box.append(h("button", { type: "button", "data-value": half, "aria-pressed": "false", text: HALF_LABEL[half] }));
    scoped.half.push(segmented(box, (value) => set({ half: value })));
  }

  function set(change) {
    Object.assign(state, change);
    for (const s of scoped.cell) s.set(state.cell);
    for (const s of scoped.half) s.set(state.half);
    if ("cell" in change || "half" in change || "arm" in change) {
      drawChain();
      drawShare();
      redrawItems();
    }
    if ("sort" in change) redrawItems();
    if ("cell" in change || "half" in change || "base" in change) drawLink();
    if ("cell" in change || "item" in change || "arm" in change || "lines" in change) drawViewer();
  }

  // ---------------------------------------------------------------- the pair viewer
  const number = document.getElementById("item-number");
  number.max = String(demo.items - 1);
  const stepItem = (d) => set({ item: (state.item + d + demo.items) % demo.items });
  document.getElementById("item-prev").addEventListener("click", () => stepItem(-1));
  document.getElementById("item-next").addEventListener("click", () => stepItem(1));
  number.addEventListener("change", () => {
    const v = Math.round(Number(number.value));
    if (Number.isFinite(v)) set({ item: Math.max(0, Math.min(demo.items - 1, v)) });
  });
  const linesSeg = segmented(document.getElementById("lines-seg"), (value) => set({ lines: value }));
  const cleanBox = document.getElementById("clean-box");
  const corruptBox = document.getElementById("corrupt-box");
  tokenHints(cleanBox, unitNames);
  tokenHints(corruptBox, unitNames);
  for (const lead of document.querySelectorAll("#fig-lead .ttext")) {
    lead.classList.add("interactive");
    tokenHints(lead.parentElement, unitNames);
  }

  async function drawViewer() {
    const { cell, item, arm } = state;
    number.value = String(item);
    linesSeg.set(state.lines);
    let file;
    try {
      file = await items(cell);
    } catch (error) {
      const box = document.getElementById("load-error-demo");
      box.hidden = false;
      box.textContent = `The texts for this condition could not be loaded (${error.message}).`;
      return;
    }
    if (cell !== state.cell || item !== state.item || arm !== state.arm) return; // a newer selection is already being drawn
    const entry = file.items[item];
    const options = { width: file.width, units, tail: state.lines === "tail" ? TAIL_LINES : 0 };
    renderText(cleanBox, entry, { ...options, kind: "clean" });
    renderText(corruptBox, entry, { ...options, kind: "corrupt" });
    cleanBox.dataset.shown = corruptBox.dataset.shown = `${cell}/${item}`;
    const m = demo.margins[cell];
    document.getElementById("viewer-title").textContent = `Item ${item} of ${cell}, ${item % 2 ? "odd" : "even"}-numbered`;
    document.getElementById("clean-margins").textContent = `margin ${m.clean[item]}; with the selected swap ${m.arms[arm][item]}`;
    document.getElementById("corrupt-margins").textContent = `margin ${m.corrupt[item]}`;
  }

  // ---------------------------------------------------------------- the chain
  const t189 = `l8/t${c.l8_transform}`;
  const through = "Swapped in what the L9 mixer reads. The residual's direct path stays clean.";
  const steps = [
    {
      site: "L8 MLP dictionary",
      unit: `transform ${c.l8_transform}`,
      note: "fires on the first token of a line",
      route: through,
      rows: [
        { arm: t189, name: `transform ${c.l8_transform} only`, unit: true },
        { arm: "l8/molt8_all", name: "all transforms of the L8 dictionary" },
        { arm: "l8/mlp8_true", name: "the whole L8 MLP output" },
      ],
    },
    {
      site: "state dictionary, resid_post.8",
      unit: `group ${c.l8_group}`,
      note: "the first-token-of-a-line group; most of that write lies inside its frame",
      route: through,
      rows: [
        { arm: `l8/g${c.l8_group}`, name: `group ${c.l8_group} only`, unit: true },
        { arm: "l8/full_post8", name: "all of resid_post.8" },
      ],
    },
    {
      model: true,
      site: "the model's own L9 mixer",
      unit: `GatedDeltaNet head ${c.head}`,
      note: "carries the count; read directly as a model head",
      route: "The output of the L9 mixer is replaced.",
      rows: [
        { arm: "head_o", name: `head ${c.head}'s read only`, unit: true },
        { arm: "layer_y", name: "the whole mixer output" },
      ],
    },
    {
      site: "state dictionary, resid_mid.9",
      unit: `group ${c.l9_group}`,
      note: "selected on most tokens, its frame carries the count to the L9 transforms",
      route: "The whole mixer swap, read through the six selected L9 transforms.",
      rows: [
        { arm: `link/mix/g${c.l9_group}/F2`, name: `only the part inside group ${c.l9_group}'s frame`, unit: true },
        { arm: "link/mix/full/F2", name: "all of the change" },
        { arm: `link/mix/minus_g${c.l9_group}/F2`, name: "the rest" },
      ],
    },
    {
      site: "L9 MLP dictionary",
      unit: `transforms ${c.l9_transforms[0]} and ${c.l9_transforms[1]}`,
      note: `${c.l9_transforms[0]} is on while the line is short; ${c.l9_transforms[1]} is on once it is long`,
      route: "The output of the L9 MLP is replaced.",
      rows: [
        { arm: `l9/t${c.l9_transforms[0]}`, name: `transform ${c.l9_transforms[0]} only`, unit: true },
        { arm: `l9/t${c.l9_transforms[1]}`, name: `transform ${c.l9_transforms[1]} only`, unit: true },
        { arm: "l9/molt9_all", name: "all transforms of the L9 dictionary" },
        { arm: "l9/mlp9_y", name: "the whole L9 MLP output" },
      ],
    },
  ];
  const chain = document.getElementById("chain");
  const chainRows = [];
  {
    const scale = h("div", { class: "scale", "data-axis": "share" });
    for (const tick of [0, 0.25, 0.5, 0.75, 1]) scale.append(h("span", { style: `--x:${X(tick)}`, text: tickText(tick, 0.25) }));
    chain.append(h("div", { class: "chain-axis", "aria-hidden": "true" }, h("div", { class: "axis-name", text: "share" }), scale));
    for (const step of steps) {
      const rows = h("div", { class: "step-rows" }, h("p", { class: "step-route", text: step.route }));
      for (const row of step.rows) {
        const track = h("span", { class: "track" });
        for (const tick of [0, 0.25, 0.5, 0.75]) track.append(h("i", { class: "tk", style: `left:${X(tick) * 100}%` }));
        const value = h("span", { class: "value" });
        track.append(h("i", { class: "ci" }), h("i", { class: "pt" }));
        const button = h(
          "button",
          { type: "button", class: `chain-row ${row.unit ? "unit" : "ref"} ${row.unit ? colourOf(row.arm) : "c-ref"}`, "data-arm": row.arm, "aria-pressed": "false" },
          h("span", { class: "name", text: row.name }),
          value,
          track,
        );
        button.addEventListener("click", () => {
          select.value = row.arm;
          set({ arm: row.arm });
        });
        chainRows.push({ button, track, value, arm: row.arm });
        rows.append(button);
      }
      chain.append(
        h(
          "div",
          { class: `chain-step${step.model ? " model" : ""}` },
          h("div", { class: "step-what" }, h("span", { class: "step-site", text: step.site }), h("span", { class: "step-unit", text: step.unit }), h("span", { class: "step-note", text: step.note })),
          rows,
        ),
      );
    }
  }
  function drawChain() {
    for (const row of chainRows) {
      const e = demo.shares[state.cell][row.arm][state.half];
      row.track.style.setProperty("--v", X(e.v));
      row.track.style.setProperty("--lo", X(e.lo));
      row.track.style.setProperty("--hi", X(e.hi));
      clear(row.value).append(e.s, " ", h("span", { text: `(${e.slo} to ${e.shi})` }));
      row.button.setAttribute("aria-pressed", String(row.arm === state.arm));
    }
  }

  // ---------------------------------------------------------------- one swap, item by item
  const select = document.getElementById("arm-select");
  const groups = { main: "The eleven main swaps", link: "Link: parts of a change at the L9 mixer output", random: "Link: random frames" };
  for (const [group, label] of Object.entries(groups)) {
    const og = h("optgroup", { label });
    for (const a of demo.arms.filter((x) => x.group === group)) og.append(h("option", { value: a.key, text: a.label }));
    select.append(og);
  }
  select.addEventListener("change", () => set({ arm: select.value }));
  const sortSeg = segmented(document.getElementById("sort-seg"), (value) => set({ sort: value }));

  function drawShare() {
    const e = demo.shares[state.cell][state.arm][state.half];
    const mean = demo.means[state.cell][state.half];
    select.value = state.arm;
    document.getElementById("share-big").textContent = e.s;
    document.getElementById("share-interval").textContent = `bootstrap interval ${e.slo} to ${e.shi}`;
    document.getElementById("share-means").textContent = `mean(m_clean - m_patched) ${mean.num[state.arm]} / mean(m_clean - m_corrupt) ${mean.den}, ${mean.n} items`;
    document.getElementById("share-what").textContent = `${arms.get(state.arm).label}. ${arms.get(state.arm).what}`;
  }

  // Each item is one arrow from its clean margin to its margin after the swap; a faint tick is its corrupt margin, the place a
  // complete swap would take it. At the right, the same for the means of the selected items: the share is how far the bold arrow
  // gets toward the corrupt mean. The words on the plot come from the page (data attributes of #items-plot).
  const plot = document.getElementById("items-plot");
  const words = plot.dataset;
  const H = 340;
  const M = { l: 40, r: 4, t: 30, b: 34 };
  let plotWidth = 0;
  function drawItems() {
    if (!plotWidth) return;
    sortSeg.set(state.sort);
    const m = demo.margins[state.cell];
    const patched = m.arms[state.arm];
    const n = demo.items;
    const order = [...Array(n).keys()];
    if (state.sort === "clean") order.sort((a, b) => Number(m.clean[b]) - Number(m.clean[a]));
    // one vertical scale per cell, over every run of that cell, so that it does not move when the swap changes
    let lo = Infinity;
    let hi = -Infinity;
    for (const list of [m.clean, m.corrupt, ...Object.values(m.arms)]) {
      for (const v of list) {
        lo = Math.min(lo, Number(v));
        hi = Math.max(hi, Number(v));
      }
    }
    const yt = niceTicks(lo, hi, 5);
    const y = linear(yt.lo, yt.hi, H - M.b, M.t);
    const meanW = plotWidth < 560 ? 104 : 168; // the panel of the means
    const right = plotWidth - M.r - meanW - 14;
    const iw = right - M.l;
    const step = iw / n;
    const r = Math.max(1.4, Math.min(2.4, step * 0.26));
    const root = svg("svg", { width: plotWidth, height: H, role: "group", "aria-label": `${words.aria} The table below the figure holds every value.` });
    const axis = svg("g", { "data-axis": "margin", "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${right}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    if (state.sort === "index") {
      for (let i = 0; i < n; i += 8) axis.append(svg("text", { x: M.l + (i + 0.5) * step, y: H - M.b + 15, "text-anchor": "middle" }, String(i)));
    }
    root.append(axis);
    const labels = svg("g", { "aria-hidden": "true" });
    labels.append(svg("text", { x: 0, y: 11, class: "axis-label" }, words.y));
    labels.append(svg("text", { x: M.l + iw / 2, y: H - 4, "text-anchor": "middle", class: "axis-label" }, state.sort === "index" ? "item number" : words.x));
    if (yt.lo < 0 && yt.hi > 0) {
      // the half above zero is tinted and named; the items stand in the order of their clean margin, so its right corner is empty
      axis.prepend(svg("rect", { x: M.l, y: y(yt.hi), width: iw, height: y(0) - y(yt.hi), class: "zone above" }));
      const text = words.zero;
      const cut = text.length * 6 > iw - 12 ? text.lastIndexOf(" ", Math.ceil(text.length / 2) + 3) : -1;
      const parts = cut > 0 ? [text.slice(0, cut), text.slice(cut + 1)] : [text];
      parts.forEach((part, k) => labels.append(svg("text", { x: right - 5, y: y(yt.hi) + 14 + k * 14, "text-anchor": "end", class: "on-plot quiet" }, part)));
    }
    root.append(labels);
    const colour = colourOf(state.arm);
    order.forEach((i, k) => {
      const inSet = state.half === "all" || (state.half === "even") === (i % 2 === 0);
      const x = M.l + (k + 0.5) * step;
      const y0 = y(Number(m.clean[i]));
      const y1 = y(Number(patched[i]));
      const col = svg("g", {
        class: `item-col ${colour}${inSet ? "" : " dim"}${i === state.item ? " current" : ""}`,
        tabindex: "0",
        role: "button",
        "data-item": i,
        "aria-label": `Item ${i}: clean ${m.clean[i]}, corrupt ${m.corrupt[i]}, with the swap ${patched[i]}`,
      });
      col.append(svg("rect", { x: x - step / 2, y: M.t, width: step, height: H - M.b - M.t }));
      const half = Math.max(2.5, step * 0.36);
      col.append(svg("path", { d: `M${x - half} ${y(Number(m.corrupt[i]))}H${x + half}`, class: "pt-target" }));
      col.append(svg("circle", { cx: x, cy: y0, r, class: "pt-clean" }));
      const head = Math.max(2.6, Math.min(4.2, step * 0.42));
      if (Math.abs(y1 - y0) > head * 2.2) {
        const dir = y1 > y0 ? 1 : -1;
        col.append(svg("path", { d: `M${x} ${y0}V${y1 - dir * head * 1.5}`, class: "arrow-item" }));
        col.append(svg("path", { d: `M${x - head} ${y1 - dir * head * 1.7}L${x} ${y1}L${x + head} ${y1 - dir * head * 1.7}z`, class: "arrow-head pt-patched" }));
      } else {
        col.append(svg("path", { d: diamond(x, y1, head), class: "arrow-head pt-patched" }));
      }
      const tip = (event) =>
        showTip(event, (node) => {
          node.append(h("div", { text: `Item ${i}, ${i % 2 ? "odd" : "even"}-numbered` }));
          node.append(h("div", {}, "clean ", h("b", { text: m.clean[i] }), ", corrupt ", h("b", { text: m.corrupt[i] })));
          node.append(h("div", {}, "with the swap ", h("b", { text: patched[i] })));
        });
      col.addEventListener("pointermove", tip);
      col.addEventListener("pointerleave", hideTip);
      const pick = () => set({ item: i });
      col.addEventListener("click", pick);
      col.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          pick();
        }
      });
      root.append(col);
    });
    // the means of the selected items
    const mean = demo.means[state.cell][state.half];
    const share = demo.shares[state.cell][state.arm][state.half];
    const mc = Number(mean.clean);
    const mx = Number(mean.corrupt);
    const mp = mc - Number(mean.num[state.arm]);
    const x0 = plotWidth - M.r - meanW;
    const xc = x0 + (meanW < 120 ? 20 : 30);
    const panel = svg("g", { class: "mean-arrow", "aria-hidden": "true" });
    panel.append(svg("rect", { x: x0, y: M.t - 22, width: meanW, height: H - M.b - M.t + 30, rx: 8, class: "mean-panel" }));
    panel.append(svg("text", { x: x0 + 10, y: M.t - 7, class: "on-plot strong" }, words.mean));
    panel.append(svg("path", { d: `M${xc} ${y(mc)}V${y(mx)}`, class: "mean-track" }));
    panel.append(svg("path", { d: `M${x0 + 8} ${y(mc)}H${x0 + meanW - 8}`, class: "mean-line" }));
    panel.append(svg("path", { d: `M${x0 + 8} ${y(mx)}H${x0 + meanW - 8}`, class: "mean-line target" }));
    panel.append(svg("text", { x: xc + 16, y: y(mc) - 5, class: "on-plot quiet" }, words.start));
    panel.append(svg("text", { x: xc + 16, y: y(mx) + 14, class: "on-plot quiet" }, words.target));
    const dir = y(mp) > y(mc) ? 1 : -1;
    if (Math.abs(y(mp) - y(mc)) > 12) {
      panel.append(svg("path", { d: `M${xc} ${y(mc)}V${y(mp) - dir * 9}`, class: "arrow-mean" }));
      panel.append(svg("path", { d: `M${xc - 7} ${y(mp) - dir * 10}L${xc} ${y(mp)}L${xc + 7} ${y(mp) - dir * 10}z`, class: "arrow-mean-head" }));
    } else {
      panel.append(svg("path", { d: diamond(xc, y(mp), 6), class: "arrow-mean-head" }));
    }
    panel.append(svg("text", { x: xc + 16, y: Math.max(y(mc) + 22, Math.min(y(mx) - 10, (y(mc) + y(mp)) / 2 + 4)), class: "on-plot strong", "data-share": share.s }, `share ${share.s}`));
    root.append(panel);
    clear(plot).append(root);
  }
  const redrawPlot = onResize(plot, (w) => {
    plotWidth = w;
    drawItems();
  });

  const details = document.getElementById("items-details");
  const tableBox = document.getElementById("items-table");
  function drawTable() {
    if (!details.open) return;
    const m = demo.margins[state.cell];
    const table = h("table", {}, h("caption", { text: `Margins per item: ${state.cell}, ${arms.get(state.arm).label}.` }));
    table.append(h("thead", {}, h("tr", {}, ...["Item", "Set", "Clean run", "Corrupt run", "Clean run with the swap"].map((t) => h("th", { scope: "col", text: t })))));
    const body = h("tbody");
    for (let i = 0; i < demo.items; i++) {
      body.append(h("tr", {}, h("td", { text: String(i) }), h("td", { text: i % 2 ? "odd" : "even" }), h("td", { text: m.clean[i] }), h("td", { text: m.corrupt[i] }), h("td", { text: m.arms[state.arm][i] })));
    }
    table.append(body);
    clear(tableBox).append(h("div", { class: "table-wrap" }, table));
  }
  details.addEventListener("toggle", drawTable);
  function redrawItems() {
    redrawPlot();
    drawTable();
  }

  // ---------------------------------------------------------------- the link comparison
  const baseBox = document.getElementById("base-seg");
  for (const [key, label] of Object.entries(demo.link_labels.bases)) baseBox.append(h("button", { type: "button", "data-value": key, "aria-pressed": "false", text: label }));
  const baseSeg = segmented(baseBox, (value) => set({ base: value }));
  const linkPanels = document.getElementById("link-panels");
  const upper = (s) => s[0].toUpperCase() + s.slice(1);
  function drawLink() {
    baseSeg.set(state.base);
    clear(linkPanels);
    const labels = demo.link_labels;
    for (const [route, routeLabel] of Object.entries(labels.routes)) {
      const panel = h("div", { class: "link-panel" }, h("h4", { text: upper(routeLabel) }));
      for (const row of demo.link_table[state.half]) {
        if (row.part !== "random" && row.base !== state.base) continue;
        const text = row.cells[state.cell][route];
        if (text === undefined) continue; // random frames were measured through the transforms only
        const kind = row.part === "full" ? "all" : row.part === "random" ? "random" : row.part.startsWith("minus") ? "rest" : "inside";
        const label = row.part === "random" ? `Random frame, ${labels.bases[row.base]}` : upper(labels.parts[row.part]);
        const bar = h("div", { class: `hbar ${kind}` }, h("span", { class: "hbar-label", text: label }), h("b", { text }));
        bar.append(h("div", { class: "hbar-track" }, h("i", { style: `--v:${Math.max(0, Math.min(1, Number(text)))}` })));
        panel.append(bar);
      }
      linkPanels.append(panel);
    }
  }

  set({});
  drawChain();
  drawShare();
  drawLink();
  drawViewer();
}
