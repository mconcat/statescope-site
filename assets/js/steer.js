// "Steering one unit by a dose": the swap of the worked example scaled by a factor alpha.
// data/steer.json (written by tools/build_data.py, every value a string):
//   alphas: the measured doses in order; units: [{ key, label, reference, reference_label }]
//   cells[cell]: { clean[item], corrupt[item], mean_clean, mean_corrupt,
//                  arms[arm]: { mean[dose], share[dose], lo[dose], hi[dose], items[dose][item] } }
// Only measured doses are shown: the slider steps through them and nothing is interpolated. The words on the plots come from the page.
import { svg, h, clear, linear, niceTicks, tickText, onResize, diamond, showTip, hideTip, segmented } from "./svg.js";

export function initSteer(steer) {
  const figure = document.getElementById("fig-steer");
  const words = figure.dataset;
  const meanWords = document.getElementById("items-plot").dataset; // the names of the two mean lines, as in the per-item figure
  const alphas = steer.alphas.map(Number);
  const cells = Object.keys(steer.cells);
  const state = { unit: steer.units[0].key, cell: cells[0], dose: steer.alphas.indexOf(steer.swap_dose) };
  const unit = () => steer.units.find((u) => u.key === state.unit);
  const arm = (key = state.unit) => steer.cells[state.cell].arms[key];
  const colour = (key) => (key.startsWith("l8/") ? "c-a" : key.endsWith("t410") ? "c-b" : key.endsWith("t1749") ? "c-c" : "c-ink");

  const select = document.getElementById("steer-unit");
  for (const u of steer.units) select.append(h("option", { value: u.key, text: u.label }));
  select.addEventListener("change", () => set({ unit: select.value }));
  const cellBox = document.getElementById("steer-cell");
  for (const cell of cells) cellBox.append(h("button", { type: "button", "data-value": cell, "aria-pressed": "false", text: cell }));
  const cellSeg = segmented(cellBox, (value) => set({ cell: value }));
  const range = document.getElementById("steer-dose");
  range.max = String(alphas.length - 1);
  range.addEventListener("input", () => set({ dose: Number(range.value) }));
  const doseLabel = document.querySelector('label[for="steer-dose"]').textContent;

  const plots = { share: document.getElementById("steer-share-plot"), mean: document.getElementById("steer-mean-plot"), items: document.getElementById("steer-items-plot") };
  const widths = { share: 0, mean: 0, items: 0 };
  const M = { l: 44, r: 10, t: 18, b: 34 };

  function set(change) {
    Object.assign(state, change);
    draw();
  }

  function readout() {
    const a = arm();
    const i = state.dose;
    select.value = state.unit;
    cellSeg.set(state.cell);
    range.value = String(i);
    range.setAttribute("aria-valuetext", steer.alphas[i]);
    document.getElementById("steer-dose-value").textContent = steer.alphas[i];
    document.getElementById("steer-share").textContent = a.share[i];
    document.getElementById("steer-interval").textContent = `${words.readoutInterval} ${a.lo[i]} to ${a.hi[i]}`;
    document.getElementById("steer-mean").textContent = a.mean[i];
    document.getElementById("steer-key-unit").textContent = unit().label;
    document.getElementById("steer-key-ref-item").hidden = !unit().reference;
    const title = document.getElementById("steer-items-title");
    title.textContent = title.dataset.text.replace("ALPHA", steer.alphas[i]);
    figure.classList.remove("c-a", "c-b", "c-c", "c-ink");
    figure.classList.add(colour(state.unit));
  }

  // the horizontal axis of both curves: the doses, with the part outside 0 to 1 shaded
  function doseAxis(root, width, height, x, withZoneLabel) {
    const g = svg("g", { "data-axis": "dose", "aria-hidden": "true" });
    const left = x(alphas[0]);
    const right = x(alphas[alphas.length - 1]);
    g.append(svg("rect", { x: left, y: M.t, width: x(0) - left, height: height - M.t - M.b, class: "zone" }));
    g.append(svg("rect", { x: x(1), y: M.t, width: right - x(1), height: height - M.t - M.b, class: "zone" }));
    const every = width < 380 ? 0.5 : 0.25;
    steer.alphas.forEach((a, i) => {
      if (Math.abs(alphas[i] / every - Math.round(alphas[i] / every)) < 1e-9) {
        g.append(svg("text", { x: x(alphas[i]), y: height - M.b + 14, "text-anchor": "middle" }, a));
      }
    });
    root.append(g);
    const labels = svg("g", { "aria-hidden": "true" });
    labels.append(svg("text", { x: (left + right) / 2, y: height - 3, "text-anchor": "middle", class: "axis-label" }, doseLabel));
    if (withZoneLabel) labels.append(svg("text", { x: right - 4, y: M.t + 12, "text-anchor": "end", class: "on-plot quiet" }, words.zone));
    root.append(labels);
  }

  function pickDose(root, x) {
    const at = (event) => {
      const px = event.clientX - root.getBoundingClientRect().left;
      let best = 0;
      alphas.forEach((a, i) => {
        if (Math.abs(x(a) - px) < Math.abs(x(alphas[best]) - px)) best = i;
      });
      if (best !== state.dose) set({ dose: best });
    };
    root.addEventListener("pointerdown", at);
    root.addEventListener("pointermove", (event) => {
      if (event.buttons) at(event);
    });
  }

  function curve(kind) {
    const width = widths[kind];
    if (!width) return;
    const height = kind === "share" ? 220 : 200;
    const cell = steer.cells[state.cell];
    const a = arm();
    const x = linear(alphas[0], alphas[alphas.length - 1], M.l, width - M.r);
    // one vertical scale per cell, over every unit, so that it does not move when the unit changes
    const all = [];
    for (const key of Object.keys(cell.arms)) {
      if (kind === "share") all.push(...cell.arms[key].lo.map(Number), ...cell.arms[key].hi.map(Number));
      else all.push(...cell.arms[key].mean.map(Number));
    }
    if (kind === "mean") all.push(Number(cell.mean_clean), Number(cell.mean_corrupt));
    const yt = niceTicks(Math.min(0, ...all), Math.max(...all), 4);
    const y = linear(yt.lo, yt.hi, height - M.b, M.t);
    const root = svg("svg", { width, height, role: "img", "aria-label": kind === "share" ? words.ariaShare : words.ariaMean });
    doseAxis(root, width, height, x, kind === "share");
    const axis = svg("g", { "data-axis": kind, "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    root.append(axis);
    const line = (values) => "M" + values.map((v, i) => `${x(alphas[i])} ${y(Number(v))}`).join("L");
    if (kind === "share") {
      const band = a.hi.map((v, i) => `${x(alphas[i])} ${y(Number(v))}`).concat(a.lo.map((v, i) => `${x(alphas[i])} ${y(Number(v))}`).reverse());
      root.append(svg("path", { d: `M${band.join("L")}z`, class: "band-fill" }));
      if (unit().reference) root.append(svg("path", { d: line(arm(unit().reference).share), class: "series s-r recorded" }));
    } else {
      const lines = svg("g", { "aria-hidden": "true" });
      lines.append(svg("path", { d: `M${M.l} ${y(Number(cell.mean_clean))}H${width - M.r}`, class: "mean-line" }));
      lines.append(svg("path", { d: `M${M.l} ${y(Number(cell.mean_corrupt))}H${width - M.r}`, class: "mean-line target" }));
      lines.append(svg("text", { x: width - M.r - 4, y: y(Number(cell.mean_clean)) - 5, "text-anchor": "end", class: "on-plot quiet" }, meanWords.start));
      lines.append(svg("text", { x: width - M.r - 4, y: y(Number(cell.mean_corrupt)) - 5, "text-anchor": "end", class: "on-plot quiet" }, meanWords.target));
      root.append(lines);
    }
    const values = kind === "share" ? a.share : a.mean;
    root.append(svg("path", { d: `M${x(alphas[state.dose])} ${M.t}V${height - M.b}`, class: "chosen-line" }));
    root.append(svg("path", { d: line(values), class: "series s-unit" }));
    values.forEach((v, i) =>
      root.append(svg("circle", { cx: x(alphas[i]), cy: y(Number(v)), r: i === state.dose ? 5 : 3, class: `mark s-unit${i === state.dose ? " chosen" : ""}`, "data-dose": steer.alphas[i] })),
    );
    pickDose(root, x);
    clear(plots[kind]).append(root);
  }

  function items() {
    const width = widths.items;
    if (!width) return;
    const height = 452;
    const cell = steer.cells[state.cell];
    const dosed = arm().items[state.dose];
    const n = cell.clean.length;
    const order = [...Array(n).keys()].sort((p, q) => Number(cell.clean[q]) - Number(cell.clean[p]));
    let lo = Infinity;
    let hi = -Infinity;
    for (const list of [cell.clean, cell.corrupt, ...Object.values(cell.arms).flatMap((v) => v.items)]) {
      for (const v of list) {
        lo = Math.min(lo, Number(v));
        hi = Math.max(hi, Number(v));
      }
    }
    const yt = niceTicks(lo, hi, 6);
    const y = linear(yt.lo, yt.hi, height - M.b, M.t);
    const step = (width - M.l - M.r) / n;
    const r = Math.max(1.8, Math.min(3.4, step * 0.36));
    const root = svg("svg", { width, height, role: "group", "aria-label": words.ariaItems });
    const axis = svg("g", { "data-axis": "margin", "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    root.append(axis);
    const labels = svg("g", { "aria-hidden": "true" });
    labels.append(svg("text", { x: M.l + (width - M.l - M.r) / 2, y: height - 4, "text-anchor": "middle", class: "axis-label" }, meanWords.x));
    root.append(labels);
    order.forEach((i, k) => {
      const cx = M.l + (k + 0.5) * step;
      const col = svg("g", { class: "item-col", "data-item": i, "aria-label": `Item ${i}: ${words.keyClean} ${cell.clean[i]}, ${words.keyCorrupt} ${cell.corrupt[i]}, ${words.keyDosed} ${dosed[i]}` });
      col.append(svg("rect", { x: cx - step / 2, y: M.t, width: step, height: height - M.b - M.t }));
      col.append(svg("path", { d: `M${cx} ${y(Number(cell.clean[i]))}V${y(Number(cell.corrupt[i]))}`, class: "stem" }));
      col.append(svg("circle", { cx, cy: y(Number(cell.corrupt[i])), r: r - 0.4, class: "pt-corrupt" }));
      col.append(svg("circle", { cx, cy: y(Number(cell.clean[i])), r, class: "pt-clean" }));
      col.append(svg("path", { d: diamond(cx, y(Number(dosed[i])), r + 1.2), class: "pt-patched", "data-margin": dosed[i] }));
      col.addEventListener("pointermove", (event) =>
        showTip(event, (node) => {
          node.append(h("div", { text: `Item ${i}` }));
          node.append(h("div", {}, `${words.keyClean} `, h("b", { text: cell.clean[i] })));
          node.append(h("div", {}, `${words.keyCorrupt} `, h("b", { text: cell.corrupt[i] })));
          node.append(h("div", {}, `${words.keyDosed} `, h("b", { text: dosed[i] })));
        }),
      );
      col.addEventListener("pointerleave", hideTip);
      root.append(col);
    });
    clear(plots.items).append(root);
  }

  function draw() {
    readout();
    curve("share");
    curve("mean");
    items();
  }
  for (const kind of Object.keys(plots)) {
    onResize(plots[kind], (w) => {
      widths[kind] = w;
      draw();
    });
  }
  draw();
}
