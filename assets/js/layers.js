// Numbers per layer: small multiples over one shared layer axis, for the 0.8B set, its spliced-in loss, and the 4B set.
// Solid lines and filled marks: re-measured with the published reader. Dashed lines, open marks and bars: recorded at training.
import { svg, h, clear, linear, niceTicks, tickText, onResize, diamond, segmented } from "./svg.js";

const HEIGHT = 190;
const M = { l: 40, r: 10, t: 10, b: 28 };

function mark(s, x, y, r) {
  const cls = `mark ${s.cls}${s.recorded ? " recorded" : ""}`;
  return s.shape === "diamond" ? svg("path", { d: diamond(x, y, r + 1), class: cls }) : svg("circle", { cx: x, cy: y, r, class: cls });
}

function legendKey(s) {
  const node = svg("svg", { width: 26, height: 12, "aria-hidden": "true" });
  node.append(svg("path", { d: "M1 6H25", class: `series ${s.cls}${s.recorded ? " recorded" : ""}` }), mark(s, 13, 6, 3));
  return node;
}

// A group of panels over the layers of one set.
//   rows: one object per layer; panels: [{ title, sub(), series: [{ label, cls, shape, recorded, value(row) }], bars: { value(row), total } }]
//   readout(row): [[label, text], ...] shown above the panels for the layer under the pointer or the slider
export function layerPanels({ grid, readoutBox, range, rows, panels, readout, start }) {
  const n = rows.length;
  let layer = start ?? Math.min(9, n - 1);
  const drawers = [];

  function showReadout() {
    clear(readoutBox);
    for (const [label, text] of readout(rows[layer])) readoutBox.append(h("span", {}, `${label} `, h("b", { text })));
    if (range) range.value = String(layer);
  }
  function setLayer(value) {
    const v = Math.max(0, Math.min(n - 1, value));
    if (v === layer) return;
    layer = v;
    showReadout();
    for (const draw of drawers) draw.cursor();
  }

  for (const spec of panels) {
    const sub = h("p", { class: "figure-sub" });
    const keys = h("ul", { class: "keys", "aria-hidden": "true" });
    const plot = h("div", { class: "plot" });
    grid.append(h("div", { class: "panel" }, h("h4", { text: spec.title }), sub, keys, plot));
    const series = spec.series ?? [];
    if (series.length > 1) for (const s of series) keys.append(h("li", {}, legendKey(s), s.label));

    let width = 0;
    let cursor = null;
    let x = () => 0;
    function draw() {
      if (!width) return;
      sub.textContent = spec.sub();
      clear(plot);
      const iw = width - M.l - M.r;
      const ih = HEIGHT - M.t - M.b;
      x = (i) => M.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
      const values = spec.bars ? rows.map(spec.bars.value).concat(spec.bars.total ?? []) : series.flatMap((s) => rows.map(s.value));
      const yt = niceTicks(0, Math.max(...values), 4);
      const y = linear(0, yt.hi, M.t + ih, M.t);
      const root = svg("svg", { width, height: HEIGHT, role: "img", "aria-label": `${spec.title}. ${spec.sub()} The table below the panels holds every value.` });
      const axis = svg("g", { "data-axis": "layer", "aria-hidden": "true" });
      for (const tick of yt.ticks) {
        axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
        axis.append(svg("text", { x: M.l - 6, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
      }
      const every = n > 26 ? 8 : 4;
      for (let i = 0; i < n; i += every) axis.append(svg("text", { x: x(i), y: HEIGHT - M.b + 14, "text-anchor": "middle" }, String(i)));
      axis.append(svg("text", { x: width - M.r, y: HEIGHT - 1, "text-anchor": "end", class: "axis-label" }, "layer"));
      root.append(axis);
      cursor = svg("path", { class: "cursor" });
      root.append(cursor);
      if (spec.bars) {
        const bw = Math.max(2, (iw / (n - 1)) * 0.62);
        if (spec.bars.total) root.append(svg("path", { d: `M${M.l} ${y(spec.bars.total)}H${width - M.r}`, class: "series s-r recorded" }));
        rows.forEach((row, i) => {
          const v = spec.bars.value(row);
          root.append(svg("rect", { x: x(i) - bw / 2, y: y(v), width: bw, height: Math.max(0, y(0) - y(v)), class: "bar-rect", "data-layer": i }));
        });
      }
      for (const s of series) {
        const pts = rows.map((row, i) => [x(i), y(s.value(row))]);
        root.append(svg("path", { d: "M" + pts.map((p) => p.join(" ")).join("L"), class: `series ${s.cls}${s.recorded ? " recorded" : ""}` }));
        const r = width < 330 ? 2 : 2.6;
        for (const [px, py] of pts) root.append(mark(s, px, py, r));
      }
      const at = (event) => {
        const box = root.getBoundingClientRect();
        setLayer(Math.round(((event.clientX - box.left - M.l) / iw) * (n - 1)));
      };
      root.addEventListener("pointermove", at);
      root.addEventListener("pointerdown", at);
      plot.append(root);
      moveCursor();
    }
    function moveCursor() {
      if (!cursor) return;
      cursor.setAttribute("d", `M${x(layer)} ${M.t}V${HEIGHT - M.b}`);
      for (const bar of plot.querySelectorAll(".bar-rect")) bar.classList.toggle("hot", Number(bar.dataset.layer) === layer);
    }
    const redraw = onResize(plot, (w) => {
      width = w;
      draw();
    });
    drawers.push({ redraw, cursor: moveCursor });
  }

  if (range) {
    range.max = String(n - 1);
    range.addEventListener("input", () => setLayer(Number(range.value)));
  }
  showReadout();
  return { redraw: () => drawers.forEach((d) => d.redraw()), showReadout };
}

export function initLayers(layers, splice) {
  const col = layers.columns;
  let p0 = "dropped";
  const p0Text = () => (p0 === "dropped" ? "position 0 dropped" : "position 0 included");
  const main = layerPanels({
    grid: document.getElementById("layer-panels"),
    readoutBox: document.getElementById("layer-readout"),
    range: document.getElementById("layer-range"),
    rows: layers.rows,
    readout: (r) => [
      ["Layer", String(r.layer)],
      [col.state_mid, r[p0].state_mid],
      [col.state_post, r[p0].state_post],
      [col.mlp, r[p0].mlp],
      [col.mlp_train, r.mlp_train],
      [col.on_per_token, r.on_per_token],
      [col.alive, r.alive_text],
      [col.penalty, r.penalty],
    ],
    panels: [
      {
        title: "State FVU",
        sub: () => `Re-measured with the published reader, ${p0Text()}.`,
        series: [
          { label: "resid_mid", cls: "s-n", shape: "circle", value: (r) => Number(r[p0].state_mid) },
          { label: "resid_post", cls: "s-r", shape: "diamond", value: (r) => Number(r[p0].state_post) },
        ],
      },
      {
        title: "MLP FVU",
        sub: () => `Two measurements on different tokens; the solid series has ${p0Text()}.`,
        series: [
          { label: "re-measured with the published reader", cls: "s-n", shape: "circle", value: (r) => Number(r[p0].mlp) },
          { label: "recorded at training", cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.mlp_train) },
        ],
      },
      {
        title: col.on_per_token,
        sub: () => "Recorded at training by us, position 0 included.",
        series: [{ label: col.on_per_token, cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.on_per_token) }],
      },
      {
        title: col.alive,
        sub: () => "Recorded at training by us. The dashed line is the number of transforms.",
        bars: { value: (r) => r.alive, total: layers.rows[0].transforms },
      },
    ],
  });
  const seg = segmented(document.getElementById("p0-seg"), (value) => {
    p0 = value;
    main.redraw();
    main.showReadout();
  });
  seg.set(p0);

  layerPanels({
    grid: document.getElementById("splice-panels"),
    readoutBox: document.getElementById("splice-readout"),
    range: null,
    rows: splice.rows,
    readout: (r) => [
      ["Layer", String(r.layer)],
      [splice.columns.state, r.state],
      [splice.columns.mlp, r.mlp],
    ],
    panels: [
      {
        title: splice.columns.state,
        sub: () => "Recorded at training, in nats.",
        series: [{ label: splice.columns.state, cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.state) }],
      },
      {
        title: splice.columns.mlp,
        sub: () => "Recorded at training, in nats.",
        series: [{ label: splice.columns.mlp, cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.mlp) }],
      },
    ],
  });
}

export function initFourB(four) {
  const col = four.columns;
  layerPanels({
    grid: document.getElementById("b4-panels"),
    readoutBox: document.getElementById("b4-readout"),
    range: document.getElementById("b4-range"),
    rows: four.rows,
    start: 16,
    readout: (r) => [
      ["Layer", String(r.layer)],
      [col.state_mid, r.dropped.state_mid],
      [col.state_post, r.dropped.state_post],
      [col.mlp, r.dropped.mlp],
      [col.mlp_train, r.mlp_train],
      [col.alive, r.alive_text],
      ["On at 90% of tokens or more, web text / training mix", r.always_text],
      ["Their share of the write energy, web text", r.always_energy],
    ],
    panels: [
      {
        title: "State FVU",
        sub: () => "Re-measured with the published reader, position 0 dropped.",
        series: [
          { label: "resid_mid", cls: "s-n", shape: "circle", value: (r) => Number(r.dropped.state_mid) },
          { label: "resid_post", cls: "s-r", shape: "diamond", value: (r) => Number(r.dropped.state_post) },
        ],
      },
      {
        title: "MLP FVU",
        sub: () => "Two measurements on different tokens.",
        series: [
          { label: "re-measured with the published reader", cls: "s-n", shape: "circle", value: (r) => Number(r.dropped.mlp) },
          { label: "recorded at training", cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.mlp_train) },
        ],
      },
      {
        title: col.alive,
        sub: () => "Recorded at training by us. The dashed line is the number of transforms.",
        bars: { value: (r) => r.alive, total: four.rows[0].transforms },
      },
      {
        title: "Write energy of the always-on transforms",
        sub: () => "Share of the summed write energy carried by transforms on at 90% of tokens or more, web text. Recorded at training.",
        series: [{ label: "share", cls: "s-n", shape: "circle", recorded: true, value: (r) => Number(r.always_energy) }],
      },
    ],
  });
}
