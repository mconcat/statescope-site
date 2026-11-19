// Numbers per layer and spliced-in loss: small multiples over one shared layer axis.
// Solid lines and filled marks: measured by this repository. Dashed lines and open marks: recorded by the original project.
import { svg, h, clear, linear, niceTicks, tickText, onResize, diamond } from "./svg.js";

const HEIGHT = 196;
const M = { l: 42, r: 12, t: 12, b: 30 };

function legendKey(s) {
  const node = svg("svg", { width: 26, height: 12, "aria-hidden": "true" });
  node.append(svg("path", { d: "M1 6H25", class: `series ${s.cls}` }));
  node.append(mark(s, 13, 6, 3.4));
  return node;
}

function mark(s, x, y, r) {
  if (s.shape === "diamond") return svg("path", { d: diamond(x, y, r + 1), class: `mark ${s.cls}` });
  return svg("circle", { cx: x, cy: y, r, class: `mark ${s.cls}` });
}

// One panel: a card with a title, a provenance line, a legend when there are two series, and a plot.
// spec: { title, sub(), series: [{ label, cls, shape, values() }], yMax, bars, reference }
function panel(grid, spec, n, store) {
  const card = h("div", { class: "card" });
  const title = h("h4", { text: spec.title });
  const sub = h("div", { class: "figure-sub" });
  const legend = h("div", { class: "legend", "aria-hidden": "true" });
  const plot = h("div", { class: "plot" });
  card.append(title, sub, legend, plot);
  grid.append(card);

  if (spec.series.length > 1) {
    for (const s of spec.series) legend.append(h("span", {}, legendKey(s), document.createTextNode(s.label)));
  }

  let width = 0;
  function draw() {
    if (!width) return;
    sub.textContent = spec.sub();
    clear(plot);
    const root = svg("svg", { width, height: HEIGHT, role: "img", "aria-label": `${spec.title}. ${spec.sub()}. The table below the charts holds every value.` });
    const iw = width - M.l - M.r;
    const ih = HEIGHT - M.t - M.b;
    const x = (i) => M.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
    const yt = niceTicks(0, spec.yMax, 4);
    const y = linear(0, yt.hi, M.t + ih, M.t);

    const axis = svg("g", { class: "axis", "data-axis": "" });
    for (const v of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(v)}H${width - M.r}`, class: v === 0 ? "baseline" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(v) + 3.5, "text-anchor": "end" }, document.createTextNode(tickText(v, yt.step))));
    }
    const every = iw / n < 15 ? 4 : 2;
    for (let i = 0; i < n; i++) {
      if (i % every !== 0 && i !== n - 1) continue;
      if (i !== n - 1 && n - 1 - i < every) continue;
      axis.append(svg("text", { x: x(i), y: HEIGHT - 12, "text-anchor": "middle" }, document.createTextNode(String(i))));
    }
    axis.append(svg("text", { x: width - M.r, y: HEIGHT - 1, "text-anchor": "end", class: "axis-title" }, document.createTextNode("layer")));
    root.append(axis);

    const sel = store.layer;
    root.append(svg("path", { d: `M${x(sel)} ${M.t}V${M.t + ih}`, class: "crosshair" }));

    if (spec.bars) {
      const s = spec.series[0];
      const values = s.values();
      const bw = Math.max(3, Math.min(14, (iw / n) * 0.62));
      if (spec.reference) {
        const ref = spec.reference();
        const ry = y(ref.value);
        root.append(svg("path", { d: `M${M.l} ${ry}H${width - M.r}`, class: "series rest" }));
        root.append(svg("text", { x: width - M.r, y: ry - 5, "text-anchor": "end", class: "axis-title" }, document.createTextNode(ref.label)));
      }
      values.forEach((v, i) => {
        const top = y(v);
        root.append(svg("rect", { x: x(i) - bw / 2, y: top, width: bw, height: Math.max(0, M.t + ih - top), rx: 2, class: `bar ${s.cls}${i === sel ? " on" : ""}` }));
      });
    } else {
      for (const s of spec.series) {
        const values = s.values();
        root.append(svg("path", { d: values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(""), class: `series ${s.cls}` }));
        values.forEach((v, i) => root.append(mark(s, x(i), y(v), i === sel ? 4.4 : 2.4)));
      }
    }

    const hit = svg("rect", { x: M.l - 8, y: M.t, width: iw + 16, height: ih + 16, fill: "transparent" });
    const pick = (event) => {
      const box = root.getBoundingClientRect();
      const i = Math.round(((event.clientX - box.left - M.l) / iw) * (n - 1));
      store.set(Math.max(0, Math.min(n - 1, i)));
    };
    hit.addEventListener("pointermove", pick);
    hit.addEventListener("pointerdown", pick);
    root.append(hit);
    plot.append(root);
  }
  onResize(plot, (w) => {
    width = w;
    draw();
  });
  return draw;
}

function readout(node, pairs) {
  clear(node);
  for (const [label, value] of pairs) node.append(h("div", {}, h("span", { text: label }), h("b", { text: value })));
}

export function initLayers(layers, splice) {
  const rows = layers.rows;
  const n = rows.length;
  const col = layers.columns;
  const draws = [];
  const store = {
    layer: 0,
    p0: "dropped",
    set(i) {
      if (i === store.layer) return;
      store.layer = i;
      update();
    },
  };
  const num = (key) => rows.map((r) => Number(key in r ? r[key] : r[store.p0][key]));
  const fvuMax = Math.max(...rows.flatMap((r) => [r.dropped, r.with_p0].flatMap((v) => [v.state_mid, v.state_post, v.mlp].map(Number))), ...rows.map((r) => Number(r.mlp_train)));
  const p0Text = () => (store.p0 === "dropped" ? "position 0 dropped" : "position 0 included");
  const repo = () => `Measured by this repository, ${p0Text()}`;
  const training = "Recorded at training by the original project, position 0 included";

  const grid = document.getElementById("layer-panels");
  draws.push(panel(grid, {
    title: "State dictionary FVU", sub: repo, yMax: fvuMax,
    series: [{ label: "resid_mid", cls: "a", shape: "circle", values: () => num("state_mid") },
             { label: "resid_post", cls: "b", shape: "diamond", values: () => num("state_post") }],
  }, n, store));
  draws.push(panel(grid, {
    title: "MLP dictionary FVU", sub: () => `Two measurements on different tokens; the solid series has ${p0Text()}`, yMax: fvuMax,
    series: [{ label: "measured by this repository", cls: "n", shape: "circle", values: () => num("mlp") },
             { label: "recorded at training", cls: "rest", shape: "circle", values: () => num("mlp_train") }],
  }, n, store));
  draws.push(panel(grid, {
    title: col.on_per_token, sub: () => training, yMax: Math.max(...num("on_per_token")),
    series: [{ label: col.on_per_token, cls: "rest", shape: "circle", values: () => num("on_per_token") }],
  }, n, store));
  draws.push(panel(grid, {
    title: col.alive, sub: () => training, yMax: rows[0].transforms, bars: true,
    reference: () => ({ value: rows[0].transforms, label: `all ${rows[0].transforms.toLocaleString("en-US")} transforms` }),
    series: [{ label: col.alive, cls: "rest", values: () => num("alive") }],
  }, n, store));

  const spliceGrid = document.getElementById("splice-panels");
  const recorded = "Recorded by the original project, not repeated by this repository; increase in nats";
  for (const key of ["state", "mlp"]) {
    const values = splice.rows.map((r) => Number(r[key]));
    draws.push(panel(spliceGrid, {
      title: splice.columns[key], sub: () => recorded, yMax: Math.max(...values),
      series: [{ label: splice.columns[key], cls: "rest", shape: "circle", values: () => values }],
    }, n, store));
  }

  const range = document.getElementById("layer-range");
  const out = document.getElementById("layer-out");
  range.max = String(n - 1);
  range.addEventListener("input", () => store.set(Number(range.value)));

  const seg = document.getElementById("p0-seg");
  seg.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    store.p0 = button.dataset.value;
    for (const b of seg.querySelectorAll("button")) b.setAttribute("aria-pressed", String(b === button));
    update();
  });

  function update() {
    const r = rows[store.layer];
    const v = r[store.p0];
    range.value = String(store.layer);
    out.textContent = String(r.layer);
    readout(document.getElementById("layer-readout"), [
      ["Layer", String(r.layer)],
      [col.state_mid, v.state_mid],
      [col.state_post, v.state_post],
      [col.mlp, v.mlp],
      [col.mlp_train, r.mlp_train],
      [col.on_per_token, r.on_per_token],
      [col.alive, r.alive_text],
      [col.penalty, r.penalty],
    ]);
    const s = splice.rows[store.layer];
    readout(document.getElementById("splice-readout"), [
      ["Layer", String(s.layer)],
      [splice.columns.state, s.state],
      [splice.columns.mlp, s.mlp],
    ]);
    for (const draw of draws) draw();
  }
  update();
}
