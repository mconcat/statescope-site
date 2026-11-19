// The line-count demonstration: the chain, shares by swap, one swap item by item, the item viewer, firing rates, the link comparison.
// All values are strings written by tools/build_data.py; this file only places them and converts them to coordinates.
import { svg, h, clear, linear, niceTicks, tickText, onResize, diamond, showTip, hideTip, segmented } from "./svg.js";

const HALF_LABEL = { even: "even-numbered items", odd: "odd-numbered items", all: "all items" };
const HALF_SHORT = { even: "even-numbered", odd: "odd-numbered", all: "all items" };
const HALF_NOTE = {
  even: "The original project reads results on the even-numbered items.",
  odd: "The original project ranked transforms on the odd-numbered items.",
  all: "All items of the cell, both halves together.",
};

export function initDemo(demo, load) {
  const c = demo.constants;
  const cells = demo.cells;
  const arms = demo.arms;
  const armByKey = new Map(arms.map((a) => [a.key, a]));
  const mainArms = arms.filter((a) => a.group === "main");
  const state = { cell: cells[0].key, half: "even", arm: `l8/t${c.l8_transform}`, item: 0, sort: "index", base: "mix", node: "t8" };
  const cellInfo = () => cells.find((x) => x.key === state.cell);
  const inHalf = (i) => state.half === "all" || (state.half === "even") === (i % 2 === 0);
  const itemFiles = new Map();

  // one share axis for every track on the page
  let lo = 0;
  let hi = 1;
  for (const cell of cells) for (const a of arms) for (const half of Object.keys(HALF_LABEL)) {
    const e = demo.shares[cell.key][a.key][half];
    lo = Math.min(lo, e.lo);
    hi = Math.max(hi, e.hi);
  }
  lo = Math.floor(lo * 10 - 1e-9) / 10;
  hi = Math.ceil(hi * 10 - 1e-9) / 10;
  const pct = (v) => `${(((v - lo) / (hi - lo)) * 100).toFixed(2)}%`;

  function track(entry) {
    const t = h("span", { class: "track", "aria-hidden": "true" });
    t.append(h("span", { class: "zero", style: `left:${pct(0)}` }), h("span", { class: "one", style: `left:${pct(1)}` }));
    t.append(h("span", { class: "iv", style: `left:${pct(entry.lo)};width:calc(${pct(entry.hi)} - ${pct(entry.lo)})` }));
    t.append(h("span", { class: "pt", style: `left:${pct(entry.v)}` }));
    return t;
  }
  function axisRow() {
    const ticks = h("span", { class: "track-ticks", "data-axis": "" });
    for (const v of [0, 0.5, 1]) ticks.append(h("span", { style: `left:${pct(v)}`, text: tickText(v, 0.5) }));
    return h("div", { class: "forest-axis", "aria-hidden": "true" }, h("span", { class: "label" }), ticks, h("span", { class: "value" }));
  }
  function valueCell(entry) {
    return h("span", { class: "value" }, document.createTextNode(`${entry.s} `), h("small", { text: `(${entry.slo} to ${entry.shi})` }));
  }

  // ------------------------------------------------------------------ controls
  const cellSeg = document.getElementById("cell-seg");
  for (const cell of cells) cellSeg.append(h("button", { type: "button", "data-value": cell.key, "aria-pressed": String(cell.key === state.cell), text: cell.key }));
  segmented(cellSeg, (value) => {
    state.cell = value;
    update();
  });
  segmented(document.getElementById("half-seg"), (value) => {
    state.half = value;
    update();
  });
  const sortSeg = segmented(document.getElementById("sort-seg"), (value) => {
    state.sort = value;
    drawItems();
  });
  sortSeg.set(state.sort);

  const select = document.getElementById("arm-select");
  const groups = [["main", "Swaps of the table"], ["link", "From the L9 mixer to the L9 transforms"], ["random", "Random frames"]];
  for (const [group, label] of groups) {
    const og = h("optgroup", { label });
    for (const a of arms.filter((x) => x.group === group)) og.append(h("option", { value: a.key, text: a.label }));
    select.append(og);
  }
  select.addEventListener("change", () => setArm(select.value));

  const baseSeg = document.getElementById("base-seg");
  for (const [key, label] of Object.entries(demo.link_labels.bases)) {
    baseSeg.append(h("button", { type: "button", "data-value": key, "aria-pressed": String(key === state.base), text: label }));
  }
  segmented(baseSeg, (value) => {
    state.base = value;
    drawLink();
  });

  // ------------------------------------------------------------------ the chain
  const g9 = `g${c.l9_group}`;
  const nodes = {
    t8: { panel: "panel-t8", arm: `l8/t${c.l8_transform}`, related: [`l8/t${c.l8_transform}`, "l8/molt8_all", "l8/mlp8_true"] },
    g8: { panel: "panel-g8", arm: `l8/g${c.l8_group}`, related: [`l8/g${c.l8_group}`, `l8/t${c.l8_transform}`, "l8/full_post8"] },
    mixer: { panel: "panel-mixer", arm: "head_o", related: ["head_o", "layer_y"] },
    g9: { panel: "panel-g9", arm: `link/mix/${g9}/F2`, related: [`link/mix/${g9}/F2`, `link/mix/${g9}/T2`, `link/mix/${g9}/down`, `link/mix/minus_${g9}/F2`] },
    t9a: { panel: "panel-t9", arm: `l9/t${c.l9_transforms[0]}`, related: [`l9/t${c.l9_transforms[0]}`, `l9/t${c.l9_transforms[1]}`, "l9/molt9_all", "l9/mlp9_y"] },
    t9b: { panel: "panel-t9", arm: `l9/t${c.l9_transforms[1]}`, related: [`l9/t${c.l9_transforms[0]}`, `l9/t${c.l9_transforms[1]}`, "l9/molt9_all", "l9/mlp9_y"] },
  };
  const chain = document.getElementById("chain");
  chain.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-node]");
    if (!button) return;
    state.node = button.dataset.node;
    setArm(nodes[state.node].arm);
  });
  const relatedButtons = [];
  for (const box of document.querySelectorAll("[data-related]")) {
    const id = box.dataset.related === "t9" ? "t9a" : box.dataset.related;
    box.append(h("span", { text: "Swaps for this step:" }));
    for (const key of nodes[id].related) {
      const b = h("button", { type: "button", class: "quiet", "data-arm": key, "aria-pressed": "false", text: armByKey.get(key).label });
      b.addEventListener("click", () => setArm(key));
      relatedButtons.push(b);
      box.append(b);
    }
  }
  function drawChain() {
    const active = nodes[state.node].panel;
    for (const b of chain.querySelectorAll("button[data-node]")) b.setAttribute("aria-pressed", String(b.dataset.node === state.node));
    for (const p of document.querySelectorAll(".node-panel")) p.classList.toggle("active", p.id === active);
    for (const b of relatedButtons) b.setAttribute("aria-pressed", String(b.dataset.arm === state.arm));
  }

  function setArm(key) {
    state.arm = key;
    update();
  }

  // ------------------------------------------------------------------ shares by swap
  const forest = document.getElementById("forest");
  function drawForest() {
    clear(forest);
    forest.append(axisRow());
    for (const a of mainArms) {
      const entry = demo.shares[state.cell][a.key][state.half];
      const row = h("button", { type: "button", class: "forest-row", "aria-pressed": String(a.key === state.arm),
        "aria-label": `${a.label}: share ${entry.s}, interval ${entry.slo} to ${entry.shi}. Select this swap.` });
      row.append(h("span", { class: "label", text: a.label }), track(entry), valueCell(entry));
      row.addEventListener("click", () => setArm(a.key));
      forest.append(row);
    }
    document.getElementById("forest-title").textContent =
      `Share of the clean/corrupt margin difference carried by each swap: ${state.cell}, ${HALF_LABEL[state.half]}`;
    document.getElementById("half-note").textContent = HALF_NOTE[state.half];
  }

  // ------------------------------------------------------------------ one swap: readout and halves
  function drawShare() {
    const a = armByKey.get(state.arm);
    const entry = demo.shares[state.cell][a.key][state.half];
    const means = demo.means[state.cell][state.half];
    document.getElementById("share-context").textContent = `Share, ${state.cell}, ${HALF_LABEL[state.half]}`;
    document.getElementById("share-big").textContent = entry.s;
    document.getElementById("share-interval").textContent = `bootstrap interval ${entry.slo} to ${entry.shi}`;
    document.getElementById("share-what").textContent = `${a.label}. ${a.what}`;
    const meansBox = clear(document.getElementById("share-means"));
    meansBox.append(document.createTextNode(`mean(m_clean - m_patched) = ${means.num[a.key]}`), h("br"),
      document.createTextNode(`mean(m_clean - m_corrupt) = ${means.den}`), h("br"),
      document.createTextNode(`items: ${means.n}`));
    const halves = clear(document.getElementById("halves"));
    halves.append(axisRow());
    for (const half of Object.keys(HALF_LABEL)) {
      const e = demo.shares[state.cell][a.key][half];
      const row = h("div", { class: `forest-row${half === state.half ? " current" : ""}` });
      row.append(h("span", { class: "label", text: HALF_SHORT[half] }), track(e), valueCell(e));
      halves.append(row);
    }
    select.value = state.arm;
  }

  // ------------------------------------------------------------------ margin per item
  const itemsPlot = document.getElementById("items-plot");
  const itemsTable = document.getElementById("items-table");
  let itemsWidth = 0;
  const marginsOf = () => {
    const m = demo.margins[state.cell];
    return { clean: m.clean, corrupt: m.corrupt, patched: m.arms[state.arm] };
  };
  function cellRange() {
    const m = demo.margins[state.cell];
    let a = 0;
    let b = 0;
    for (const list of [m.clean, m.corrupt, ...Object.values(m.arms)]) for (const s of list) {
      const v = Number(s);
      a = Math.min(a, v);
      b = Math.max(b, v);
    }
    return [a, b];
  }
  function drawItems() {
    if (!itemsWidth) return;
    const m = marginsOf();
    const n = demo.items;
    const width = Math.max(itemsWidth, 620);
    const height = 280;
    const M = { l: 44, r: 10, t: 24, b: 34 };
    const iw = width - M.l - M.r;
    const ih = height - M.t - M.b;
    const order = [...Array(n).keys()];
    if (state.sort === "clean") order.sort((p, q) => Number(m.clean[p]) - Number(m.clean[q]) || p - q);
    const [a, b] = cellRange();
    const yt = niceTicks(a, b, 6);
    const y = linear(yt.lo, yt.hi, M.t + ih, M.t);
    const step = iw / n;
    clear(itemsPlot);
    const root = svg("svg", { width, height, role: "img",
      "aria-label": `Margin of the clean run, the corrupt run and the clean run with the swap, for each of the ${n} items of ${state.cell}. The table holds every value.` });
    const axis = svg("g", { class: "axis", "data-axis": "" });
    for (const v of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(v)}H${width - M.r}`, class: v === 0 ? "baseline" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(v) + 3.5, "text-anchor": "end" }, document.createTextNode(tickText(v, yt.step))));
    }
    axis.append(svg("text", { x: 4, y: 11, class: "axis-title" }, document.createTextNode("margin")));
    if (state.sort === "index") {
      for (let i = 0; i < n; i += 8) axis.append(svg("text", { x: M.l + (i + 0.5) * step, y: height - 16, "text-anchor": "middle" }, document.createTextNode(String(i))));
    }
    axis.append(svg("text", { x: width - M.r, y: height - 2, "text-anchor": "end", class: "axis-title" },
      document.createTextNode(state.sort === "index" ? "item number" : "items ordered by clean margin")));
    root.append(axis);

    order.forEach((item, pos) => {
      const cx = M.l + (pos + 0.5) * step;
      const yc = y(Number(m.clean[item]));
      const yx = y(Number(m.corrupt[item]));
      const yp = y(Number(m.patched[item]));
      const col = svg("rect", { x: cx - step / 2, y: M.t, width: step, height: ih, class: `item-col${item === state.item ? " on" : ""}` });
      const g = svg("g", { class: `item-g${inHalf(item) ? "" : " off"}`, "pointer-events": "none" });
      g.append(svg("path", { d: `M${cx} ${yc}V${yx}`, class: "stem" }));
      g.append(svg("circle", { cx, cy: yx, r: 3, class: "pt-corrupt" }));
      g.append(svg("circle", { cx, cy: yc, r: 3.4, class: "pt-clean" }));
      g.append(svg("path", { d: diamond(cx, yp, 4.6), class: "pt-patched" }));
      col.addEventListener("pointermove", (event) => showTip(event, (tip) => {
        tip.append(h("div", { class: "tip-title", text: `Item ${item}, ${item % 2 === 0 ? "even-numbered" : "odd-numbered"}` }));
        for (const [label, value] of [["clean run", m.clean[item]], ["corrupt run", m.corrupt[item]], ["clean run with the swap", m.patched[item]]]) {
          tip.append(h("div", {}, document.createTextNode(`${label} `), h("b", { text: value })));
        }
      }));
      col.addEventListener("pointerleave", hideTip);
      col.addEventListener("click", () => setItem(item));
      root.append(col, g);
    });
    itemsPlot.append(root);
    if (itemsTable.classList.contains("open")) drawItemsTable();
  }
  function drawItemsTable() {
    const m = marginsOf();
    clear(itemsTable);
    const table = h("table");
    table.append(h("caption", { text: `Margins per item: ${state.cell}; swap: ${armByKey.get(state.arm).label}. Rows outside the selected set of items are grey.` }));
    const head = h("tr");
    for (const t of ["Item", "Set", "Clean run", "Corrupt run", "Clean run with the swap"]) head.append(h("th", { scope: "col", text: t }));
    table.append(h("thead", {}, head));
    const body = h("tbody");
    for (let i = 0; i < demo.items; i++) {
      const tr = h("tr", { class: inHalf(i) ? null : "dim" });
      tr.append(h("td", { text: String(i) }), h("td", { text: i % 2 === 0 ? "even" : "odd" }), h("td", { text: m.clean[i] }), h("td", { text: m.corrupt[i] }), h("td", { text: m.patched[i] }));
      body.append(tr);
    }
    table.append(body);
    itemsTable.append(h("div", { class: "table-wrap tall" }, table));
  }
  itemsTable.addEventListener("toggle-open", (event) => {
    if (event.detail) drawItemsTable();
  });
  onResize(itemsPlot, (w) => {
    itemsWidth = w;
    drawItems();
  });

  // ------------------------------------------------------------------ item viewer
  const number = document.getElementById("item-number");
  number.max = String(demo.items - 1);
  const clamp = (i) => Math.max(0, Math.min(demo.items - 1, i));
  number.addEventListener("change", () => setItem(clamp(Number(number.value) || 0)));
  document.getElementById("item-prev").addEventListener("click", () => setItem(clamp(state.item - 1)));
  document.getElementById("item-next").addEventListener("click", () => setItem(clamp(state.item + 1)));
  const cleanBox = document.getElementById("clean-box");
  const corruptBox = document.getElementById("corrupt-box");
  for (const letter of ["a", "b", "c"]) {
    const box = document.getElementById(`show-${letter}`);
    const apply = () => cleanBox.classList.toggle(`show-${letter}`, box.checked);
    box.addEventListener("change", apply);
    apply();
  }
  const gateKeys = [["ga", String(c.l8_transform)], ["gb", String(c.l9_transforms[0])], ["gc", String(c.l9_transforms[1])]];

  function renderText(box, pieces, gate, width) {
    clear(box);
    const pre = h("pre", { class: "mono" });
    pieces.forEach((piece, i) => {
      const span = h("span", { class: "tok" });
      if (piece.includes("\n")) {
        span.classList.add("nl");
        span.textContent = piece.replace(/\n/g, "↵\n");
      } else {
        span.textContent = piece;
      }
      if (gate) for (const [cls, key] of gateKeys) if (gate[key][i] === "1") span.classList.add(cls);
      if (i === pieces.length - 1) span.classList.add("last");
      pre.append(span);
    });
    const guide = h("div", { class: "guide mono", style: `left: calc(var(--space-7) + ${width}ch)`, "aria-hidden": "true" }, h("span", { text: `${width} characters` }));
    box.append(h("div", { class: "textbox-inner" }, pre, guide));
    // show the end of the text, and bring the last token into view when its line is wider than the box
    box.scrollTop = box.scrollHeight;
    const last = pre.lastElementChild;
    box.scrollLeft = Math.max(0, last.offsetLeft + last.offsetWidth - box.clientWidth + 32);
  }
  function file(cell) {
    if (!itemFiles.has(cell.key)) itemFiles.set(cell.key, load(cell.file));
    return itemFiles.get(cell.key);
  }
  let viewerToken = 0;
  function drawViewer() {
    const cell = cellInfo();
    const m = marginsOf();
    const i = state.item;
    const token = ++viewerToken;
    number.value = String(i);
    document.getElementById("viewer-title").textContent = `Item ${i} of ${cell.key}, ${i % 2 === 0 ? "even-numbered" : "odd-numbered"}`;
    const cleanM = clear(document.getElementById("clean-margins"));
    cleanM.append(document.createTextNode("margin "), h("b", { text: m.clean[i] }), document.createTextNode(" · with the swap "), h("b", { text: m.patched[i] }));
    const corruptM = clear(document.getElementById("corrupt-margins"));
    corruptM.append(document.createTextNode("margin "), h("b", { text: m.corrupt[i] }));
    file(cell)
      .then((data) => {
        if (token !== viewerToken) return;
        const item = data.items[i];
        const key = `${cell.key}/${i}`;
        if (cleanBox.dataset.shown === key) return;      // the texts do not change with the swap
        cleanBox.dataset.shown = key;
        renderText(cleanBox, item.clean, item.gate, data.width);
        renderText(corruptBox, item.corrupt, null, data.width);
      })
      .catch((error) => {
        cleanBox.textContent = `The texts of this cell could not be loaded (${error.message}).`;
        console.error(error);
      });
  }
  function setItem(i) {
    state.item = i;
    drawItems();
    drawViewer();
  }

  // ------------------------------------------------------------------ firing rates
  const firingNames = Object.keys(demo.firing_rate);
  const firingStyle = [{ cls: "n", shape: "circle" }, { cls: "b", shape: "circle" }, { cls: "a", shape: "diamond" }];
  const firingMark = (i, x, y, r) => (firingStyle[i].shape === "diamond"
    ? svg("path", { d: diamond(x, y, r + 1), class: `mark ${firingStyle[i].cls}` })
    : svg("circle", { cx: x, cy: y, r, class: `mark ${firingStyle[i].cls}` }));
  const legend = document.getElementById("firing-legend");
  firingNames.forEach((name, i) => {
    const key = svg("svg", { width: 26, height: 12 });
    key.append(svg("path", { d: "M1 6H25", class: `series ${firingStyle[i].cls}` }), firingMark(i, 13, 6, 3.4));
    legend.append(h("span", {}, key, document.createTextNode(name)));
  });
  const firingPlot = document.getElementById("firing-plot");
  onResize(firingPlot, (width) => {
    const bins = demo.firing_rate[firingNames[0]].by_chars_in_line.map((b) => b.bin);
    const height = 220;
    const M = { l: 38, r: 12, t: 12, b: 40 };
    const iw = width - M.l - M.r;
    const ih = height - M.t - M.b;
    const x = (i) => M.l + ((i + 0.5) / bins.length) * iw;
    const y = linear(0, 1, M.t + ih, M.t);
    clear(firingPlot);
    const root = svg("svg", { width, height, role: "img", "aria-label": "Firing rate of the three transforms by characters in the line so far. The table beside the plot holds every value." });
    const axis = svg("g", { class: "axis", "data-axis": "" });
    for (const v of [0, 0.25, 0.5, 0.75, 1]) {
      axis.append(svg("path", { d: `M${M.l} ${y(v)}H${width - M.r}`, class: v === 0 ? "baseline" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(v) + 3.5, "text-anchor": "end" }, document.createTextNode(tickText(v, 0.25))));
    }
    const every = iw / bins.length < 38 ? 2 : 1;
    bins.forEach((bin, i) => {
      if (i % every === 0) axis.append(svg("text", { x: x(i), y: height - 22, "text-anchor": "middle" }, document.createTextNode(bin)));
    });
    axis.append(svg("text", { x: width - M.r, y: height - 4, "text-anchor": "end", class: "axis-title" }, document.createTextNode("characters in the line so far")));
    root.append(axis);
    firingNames.forEach((name, s) => {
      const values = demo.firing_rate[name].by_chars_in_line.map((b) => Number(b.rate));
      root.append(svg("path", { d: values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(""), class: `series ${firingStyle[s].cls}` }));
      values.forEach((v, i) => root.append(firingMark(s, x(i), y(v), 3)));
    });
    bins.forEach((bin, i) => {
      const hit = svg("rect", { x: x(i) - iw / bins.length / 2, y: M.t, width: iw / bins.length, height: ih, fill: "transparent" });
      hit.addEventListener("pointermove", (event) => showTip(event, (tip) => {
        tip.append(h("div", { class: "tip-title", text: `${bin} characters in the line so far` }));
        for (const name of firingNames) tip.append(h("div", {}, document.createTextNode(`${name} `), h("b", { text: demo.firing_rate[name].by_chars_in_line[i].rate })));
      }));
      hit.addEventListener("pointerleave", hideTip);
      root.append(hit);
    });
    firingPlot.append(root);
  });
  {
    const table = h("table");
    table.append(h("caption", { text: "Fraction of tokens at which the gate is open, clean texts of the count cells." }));
    const head = h("tr", {}, h("th", { scope: "col", text: "Tokens" }));
    for (const name of firingNames) head.append(h("th", { scope: "col", text: name }));
    table.append(h("thead", {}, head));
    const body = h("tbody");
    for (const [key, label] of [["line_first", "first token of a line"], ["newline", "line breaks"], ["other", "other tokens"]]) {
      const tr = h("tr", {}, h("th", { scope: "row", text: label }));
      for (const name of firingNames) tr.append(h("td", { text: demo.firing_rate[name][key] }));
      body.append(tr);
    }
    demo.firing_rate[firingNames[0]].by_chars_in_line.forEach((b, i) => {
      const tr = h("tr", {}, h("th", { scope: "row", text: `other tokens, ${b.bin} characters` }));
      for (const name of firingNames) tr.append(h("td", { text: demo.firing_rate[name].by_chars_in_line[i].rate }));
      body.append(tr);
    });
    table.append(body);
    document.getElementById("firing-table").append(h("div", { class: "table-wrap", style: "margin-top: 0" }, table));
  }

  // ------------------------------------------------------------------ the link comparison
  const linkPanels = document.getElementById("link-panels");
  function drawLink() {
    clear(linkPanels);
    const labels = demo.link_labels;
    const rows = demo.link_table[state.half];
    for (const [route, routeLabel] of Object.entries(labels.routes)) {
      const panel = h("div", { class: "link-panel" }, h("h4", { text: routeLabel }));
      for (const row of rows) {
        if (row.part !== "random" && row.base !== state.base) continue;
        const value = row.cells[state.cell][route];
        const kind = row.part === "full" ? "all" : row.part === "random" ? "random" : row.part.startsWith("minus") ? "rest" : "inside";
        const label = row.part === "random" ? `${labels.bases[row.base]}, ${labels.parts.random}` : labels.parts[row.part];
        const bar = h("div", { class: `hbar ${kind}${value === undefined ? " none" : ""}` });
        bar.append(h("div", { class: "hbar-label" }, h("span", { text: label }), h("b", { text: value === undefined ? "not measured" : value })));
        const t = h("div", { class: "hbar-track", "aria-hidden": "true" });
        if (value !== undefined) t.append(h("div", { class: "hbar-fill", style: `width:${Math.max(0, Math.min(1, Number(value))) * 100}%` }));
        bar.append(t);
        panel.append(bar);
      }
      linkPanels.append(panel);
    }
    document.getElementById("link-sub").textContent = `${state.cell}, ${HALF_LABEL[state.half]}; each track runs from a share of 0 to a share of 1`;
  }

  function update() {
    drawChain();
    drawForest();
    drawShare();
    drawItems();
    drawViewer();
    drawLink();
  }
  update();
}
