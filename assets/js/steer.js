// "Steering one unit by a dose": the margin as a function of a strength alpha, for a few units.
// This module is loaded only when data/steer.json exists (tools/build_page.py then writes the section's markup).
//
// data/steer.json, every number a string as in the other data files:
// {
//   "sources": ["..."],                      where the numbers come from
//   "intro": "...",                           plain sentences shown above the figure: what was changed, on which texts
//   "caption": "...",                         the figure's caption after its number: what it shows, who measured it
//   "alphas": ["-2", "-1", "0", "1", "2"],    the strengths, in order
//   "units": [{
//     "key": "l9/t1749", "label": "L9 transform 1749",
//     "mean": ["...", ...],                   mean margin at each alpha
//     "items": [["...", ...], ...]            per item: the margin at each alpha
//   }]
// }
import { svg, h, clear, linear, niceTicks, tickText, onResize, segmented } from "./svg.js";

export function initSteer(steer) {
  document.getElementById("steer-intro").textContent = steer.intro;
  document.getElementById("steer-caption").textContent = steer.caption;
  const box = document.getElementById("steer-seg");
  for (const unit of steer.units) box.append(h("button", { type: "button", "data-value": unit.key, "aria-pressed": "false", text: unit.label }));
  let current = steer.units[0];
  const seg = segmented(box, (key) => {
    current = steer.units.find((u) => u.key === key);
    redraw();
  });
  seg.set(current.key);

  const plot = document.getElementById("steer-plot");
  const H = 280;
  const M = { l: 44, r: 12, t: 12, b: 36 };
  let width = 0;
  function draw() {
    if (!width) return;
    const alphas = steer.alphas.map(Number);
    const all = steer.units.flatMap((u) => u.items.flat().map(Number));
    const yt = niceTicks(Math.min(...all), Math.max(...all), 5);
    const x = linear(alphas[0], alphas[alphas.length - 1], M.l, width - M.r);
    const y = linear(yt.lo, yt.hi, H - M.b, M.t);
    const root = svg("svg", { width, height: H, role: "img", "aria-label": `${current.label}: margin by strength. ${steer.caption}` });
    const axis = svg("g", { "data-axis": "steer", "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    steer.alphas.forEach((a, i) => axis.append(svg("text", { x: x(alphas[i]), y: H - M.b + 15, "text-anchor": "middle" }, a)));
    axis.append(svg("text", { x: 0, y: M.t - 2, class: "axis-label" }, "margin"));
    axis.append(svg("text", { x: (M.l + width - M.r) / 2, y: H - 4, "text-anchor": "middle", class: "axis-label" }, "strength"));
    root.append(axis);
    const path = (values) => "M" + values.map((v, i) => `${x(alphas[i])} ${y(Number(v))}`).join("L");
    for (const item of current.items) root.append(svg("path", { d: path(item), class: "series s-r", "stroke-width": 0.7, opacity: 0.45 }));
    root.append(svg("path", { d: path(current.mean), class: "series s-n", "stroke-width": 2.2 }));
    current.mean.forEach((v, i) => root.append(svg("circle", { cx: x(alphas[i]), cy: y(Number(v)), r: 3, class: "mark s-n" })));
    clear(plot).append(root);
  }
  const redraw = onResize(plot, (w) => {
    width = w;
    draw();
  });
}
