// Three planes inside state-group frames of the Qwen3.5-4B set. data/geom-4b.json (written by tools/build_data.py, values as strings):
//   aba:       conditions[] = { name, kind: task | line | natural, n, common, rule, points? }, reads[] = { common, rule, gain }
//   lethality: words[] = { word, c4, c2 }
//   compare:   cells[] = { cur, prev, outcome: -1 | 0 | 1, x, y }, reads = { "357": [x, y], "472": [x, y] }
// Each drawing has one scale for both directions. The words on the plots come from the page (data attributes of each figure).
import { svg, h, clear, onResize, diamond, showTip, hideTip, linear, niceTicks, tickText } from "./svg.js";

// a plane with equal scales: returns { root, X, Y, width, height } and draws the axis titles and the two zero lines
function plane(box, pts, words, { height: wanted = 0.74, pad = 30 } = {}, draw) {
  onResize(box, (width) => {
    const height = Math.round(Math.min(480, Math.max(280, width * wanted)));
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs, 0);
    const x1 = Math.max(...xs, 0);
    const y0 = Math.min(...ys, 0);
    const y1 = Math.max(...ys, 0);
    const k = Math.min((width - 2 * pad) / (x1 - x0), (height - 2 * pad) / (y1 - y0));
    const ox = (width - k * (x1 - x0)) / 2;
    const oy = (height - k * (y1 - y0)) / 2;
    const X = (v) => ox + (v - x0) * k;
    const Y = (v) => oy + (y1 - v) * k;
    const root = svg("svg", { width, height, role: "img", "aria-label": words.aria });
    const axis = svg("g", { "aria-hidden": "true" });
    axis.append(svg("path", { d: `M${X(x0)} ${Y(0)}H${X(x1)}`, class: "zero" }), svg("path", { d: `M${X(0)} ${Y(y0)}V${Y(y1)}`, class: "zero" }));
    axis.append(svg("text", { x: width - 4, y: height - 5, "text-anchor": "end", class: "axis-label" }, words.x));
    axis.append(svg("text", { x: 4, y: 12, class: "axis-label" }, words.y));
    root.append(axis);
    draw({ root, X, Y, width, height, k });
    clear(box).append(root);
  });
}

function arrow(group, x0, y0, x1, y1, cls, text, width) {
  // on a narrow plot the arrows are named in the legend only
  const len = Math.hypot(x1 - x0, y1 - y0) || 1;
  const ux = (x1 - x0) / len;
  const uy = (y1 - y0) / len;
  group.append(svg("path", { d: `M${x0} ${y0}L${x1 - ux * 9} ${y1 - uy * 9}`, class: `arrow-mean read-arrow ${cls}` }));
  group.append(svg("path", { d: `M${x1} ${y1}L${x1 - ux * 12 - uy * 6} ${y1 - uy * 12 + ux * 6}L${x1 - ux * 12 + uy * 6} ${y1 - uy * 12 - ux * 6}z`, class: `arrow-mean-head read-arrow ${cls}` }));
  if (width < 520) return;
  if (Math.abs(ux) < 0.35) {
    // a nearly upright arrow carries its label beyond its tip
    group.append(svg("text", { x: x1, y: y1 + (uy > 0 ? 16 : -8), "text-anchor": "middle", class: "on-plot strong" }, text));
    return;
  }
  const room = text.length * 6.6 + 12;
  const after = ux >= 0 ? x1 + room < width : x1 - room < 0;
  group.append(svg("text", { x: x1 + (after ? 8 : -8), y: y1 + (uy > 0.3 ? 15 : uy < -0.3 ? -8 : 4), "text-anchor": after ? "start" : "end", class: "on-plot strong" }, text));
}

function tipOn(node, lines) {
  node.addEventListener("pointermove", (event) => showTip(event, (box) => lines.forEach((line) => box.append(h("div", {}, ...line)))));
  node.addEventListener("pointerleave", hideTip);
}

function initAba(d) {
  const figure = document.getElementById("fig-aba");
  if (!figure) return;
  const w = figure.dataset;
  const all = d.conditions.flatMap((c) => (c.points || []).map((p) => [Number(p[0]), Number(p[1])]).concat([[Number(c.common), Number(c.rule)]]));
  plane(document.getElementById("aba-plot"), all, { aria: w.aria, x: w.x, y: w.y }, {}, ({ root, X, Y, width, k }) => {
    const cloud = svg("g", { "aria-hidden": "true" });
    for (const c of d.conditions) for (const p of c.points || []) cloud.append(svg("circle", { cx: X(Number(p[0])), cy: Y(Number(p[1])), r: 1.6, class: `cloud ${c.kind}` }));
    root.append(cloud);
    for (const c of d.conditions) {
      const x = X(Number(c.common));
      const y = Y(Number(c.rule));
      const mark = c.kind === "task" ? svg("circle", { cx: x, cy: y, r: 6.5, class: "cond task" }) : c.kind === "line" ? svg("path", { d: diamond(x, y, 5.5), class: "cond line" }) : svg("rect", { x: x - 5, y: y - 5, width: 10, height: 10, class: "cond natural" });
      mark.setAttribute("data-condition", c.name);
      tipOn(mark, [[c.name], [`${w.x} `, h("b", { text: c.common })], [`${w.y} `, h("b", { text: c.rule })], ["n ", h("b", { text: c.n })]]);
      root.append(mark);
    }
    const by = Object.fromEntries(d.conditions.map((c) => [c.name, c]));
    const notes = svg("g", { "aria-hidden": "true" });
    const put = (name, text, dx, dy, anchor = "start") => notes.append(svg("text", { x: X(Number(by[name].common)) + dx, y: Y(Number(by[name].rule)) + dy, "text-anchor": anchor, class: "on-plot strong" }, text));
    const narrow = width < 520;
    put("task ABA", w.labelAba, narrow ? -12 : 12, -12, narrow ? "end" : "start");
    put("task ABB", w.labelAbb, narrow ? -12 : 12, 18, narrow ? "end" : "start");
    put("task ABC", w.labelNew, 10, -12);
    if (!narrow) {
      put("sentence, repeated noun", w.labelNoun, -12, 4, "end");
      const earlier = d.conditions.filter((c) => c.kind === "line" && Number(c.rule) > 0.5 && Number(c.common) > 5);
      const top = earlier.reduce((a, b) => (Number(a.rule) > Number(b.rule) ? a : b));
      notes.append(svg("text", { x: X(Number(top.common)) - 12, y: Y(Number(top.rule)) - 10, "text-anchor": "end", class: "on-plot quiet" }, w.labelEarlier));
    }
    root.append(notes);
    const arrows = svg("g", { "aria-hidden": "true" });
    const L = Math.min(130, 4 * k);
    const from = [X(4.5), Y(-4.5)]; // the arrows are directions; they start where the plane is empty
    d.reads.forEach((r, i) => {
      const n = Math.hypot(Number(r.common), Number(r.rule));
      arrow(arrows, from[0], from[1], from[0] + (Number(r.common) / n) * L, from[1] - (Number(r.rule) / n) * L, i ? "c-b" : "c-a", i ? w.arrow2 : w.arrow1, width);
    });
    root.append(arrows);
  });
}

function initLethality(d) {
  const figure = document.getElementById("fig-leth");
  if (!figure) return;
  const w = figure.dataset;
  const pts = d.words.map((x) => [Number(x.c4), Number(x.c2)]);
  plane(document.getElementById("leth-plot"), pts, { aria: w.aria, x: w.x, y: w.y }, { height: 0.95, pad: 30 }, ({ root, X, Y, width, height }) => {
    const placed = [];
    const order = d.words.map((x, i) => i).sort((a, b) => Math.hypot(...pts[b]) - Math.hypot(...pts[a])); // the words far from the centre are placed first
    for (const p of pts) placed.push({ x0: X(p[0]) - 5, x1: X(p[0]) + 5, y0: Y(p[1]) - 5, y1: Y(p[1]) + 5 }); // no label covers a point
    const labels = svg("g", { "aria-hidden": "true" });
    for (const i of order) {
      const x = X(pts[i][0]);
      const y = Y(pts[i][1]);
      const dot = svg("circle", { cx: x, cy: y, r: 2.6, class: "word-pt small", "data-word": d.words[i].word });
      tipOn(dot, [[h("b", { text: d.words[i].word })], [`${w.x} `, h("b", { text: d.words[i].c4 })], [`${w.y} `, h("b", { text: d.words[i].c2 })]]);
      root.append(dot);
      // a label goes to the first free place beside, above or below its point
      const tw = d.words[i].word.length * 5.9 + 4;
      const tries = [
        { x: x + 7, y: y + 4, anchor: "start", x0: x + 6, x1: x + 7 + tw },
        { x: x - 7, y: y + 4, anchor: "end", x0: x - 7 - tw, x1: x - 6 },
        { x, y: y - 8, anchor: "middle", x0: x - tw / 2, x1: x + tw / 2 },
        { x, y: y + 15, anchor: "middle", x0: x - tw / 2, x1: x + tw / 2 },
        { x: x + 7, y: y - 6, anchor: "start", x0: x + 6, x1: x + 7 + tw },
        { x: x - 7, y: y + 13, anchor: "end", x0: x - 7 - tw, x1: x - 6 },
      ];
      for (const c of tries) {
        const boxed = { x0: c.x0, x1: c.x1, y0: c.y - 9, y1: c.y + 3 };
        if (boxed.x0 > 2 && boxed.x1 < width - 2 && boxed.y0 > 14 && boxed.y1 < height - 14 && placed.every((p) => boxed.x1 < p.x0 || boxed.x0 > p.x1 || boxed.y1 < p.y0 || boxed.y0 > p.y1)) {
          placed.push(boxed);
          labels.append(svg("text", { x: c.x, y: c.y, "text-anchor": c.anchor, class: "on-plot word" }, d.words[i].word));
          dot.setAttribute("r", 4); // a point with its word beside it is drawn at full size
          dot.setAttribute("class", "word-pt");
          break;
        }
      }
    }
    root.append(labels);
    // the words that found no room: drawn small, read by pointing at them, and counted under the plot
    const rest = root.querySelectorAll(".word-pt.small").length;
    const note = document.getElementById("leth-rest");
    note.hidden = rest === 0;
    note.textContent = w.rest.replace("{n}", String(rest));
  });
}

function initCompare(d) {
  const figure = document.getElementById("fig-cmp");
  if (!figure) return;
  const w = figure.dataset;
  const pts = d.cells.map((c) => [Number(c.x), Number(c.y)]);
  const kind = { "-1": ["less", w.keyLess], 0: ["equal", w.keyEqual], 1: ["greater", w.keyGreater] };
  plane(document.getElementById("cmp-plot"), pts, { aria: w.aria, x: w.x, y: w.y }, {}, ({ root, X, Y, width, k }) => {
    d.cells.forEach((c, i) => {
      const x = X(pts[i][0]);
      const y = Y(pts[i][1]);
      const [cls, name] = kind[c.outcome];
      const mark = cls === "less" ? svg("circle", { cx: x, cy: y, r: 4.6, class: "cell less" }) : cls === "greater" ? svg("path", { d: diamond(x, y, 5.6), class: "cell greater" }) : svg("rect", { x: x - 4, y: y - 4, width: 8, height: 8, class: "cell equal" });
      mark.setAttribute("data-cell", `${c.cur}/${c.prev}`);
      tipOn(mark, [[name], [`${c.cur} / ${c.prev}`]]);
      root.append(mark);
    });
    const arrows = svg("g", { "aria-hidden": "true" });
    const L = Math.min(110, 1.9 * k);
    const from = [X(0.3), Y(-3.3)]; // the arrows are directions; they start where the plane is empty
    for (const [t, cls, text] of [["357", "c-b", w.arrow357], ["472", "c-c", w.arrow472]]) {
      const [dx, dy] = d.reads[t].map(Number);
      const n = Math.hypot(dx, dy);
      arrow(arrows, from[0], from[1], from[0] + (dx / n) * L, from[1] - (dy / n) * L, cls, text, width);
    }
    root.append(arrows);
  });
}

// all orders of six example lines at the answer position: one point per history, coloured by its count of ABA minus ABB lines
function initAverage(d) {
  const figure = document.getElementById("fig-avg");
  if (!figure || !d) return;
  const w = figure.dataset;
  const pts = d.histories.map((x) => [Number(x.x), Number(x.y)]);
  const most = Math.max(...d.histories.map((x) => Math.abs(Number(x.d))));
  plane(document.getElementById("avg-plot"), pts, { aria: w.aria, x: w.x, y: w.y }, { height: 0.78, pad: 34 }, ({ root, X, Y, width }) => {
    d.histories.forEach((x, i) => {
      const v = Number(x.d);
      const dot = svg("circle", { cx: X(pts[i][0]), cy: Y(pts[i][1]), r: width < 400 ? 2.4 : 3, class: `hist ${v > 0 ? "more-a" : v < 0 ? "more-b" : "even"}`, style: `--t:${(Math.abs(v) / most).toFixed(3)}`, "data-types": x.types });
      tipOn(dot, [[h("b", { text: x.types })], [`${w.x} `, h("b", { text: x.x })], [`${w.y} `, h("b", { text: x.y })]]);
      root.append(dot);
    });
    const notes = svg("g", { "aria-hidden": "true" });
    for (const [types, text] of [["AAAAAA", w.cornerA], ["BBBBBB", w.cornerB], ["CCCCCC", w.cornerC]]) {
      const [cx, cy] = d.corners[types].map(Number);
      const x = X(cx);
      const y = Y(cy);
      notes.append(svg("circle", { cx: x, cy: y, r: 6, class: "corner" }));
      const end = x > width * 0.6;
      notes.append(svg("text", { x: x + (end ? -10 : 10), y: y + (types === "CCCCCC" ? 18 : -10), "text-anchor": end ? "end" : "start", class: "on-plot strong" }, text));
    }
    root.append(notes);
  });
}

export function initGeom(geom) {
  initAverage(geom.average);
  initAba(geom.aba);
  initLethality(geom.lethality);
  initCompare(geom.compare);
  initState(geom.state);
}

// one direction of a group's frame added on the tokens of a sentence in the prompt: the fraction of outputs containing
// a raise statement or an isinstance call, against the dose. state: { series[] = { key, points[] = { dose, rate, lo, hi } },
// controls[] = { series, dose, rate }, instructed }
function initState(d) {
  const figure = document.getElementById("fig-su");
  if (!figure || !d) return;
  const w = figure.dataset;
  const box = document.getElementById("su-plot");
  const style = { neutral: "series s-unit c-c", plain: "series s-n", second: "series s-unit c-b", third: "series s-r recorded" };
  const label = { neutral: w.lineNeutral, plain: w.linePlain, second: w.lineSecond, third: w.lineThird };
  const doses = [...new Set(d.series.flatMap((s) => s.points.map((p) => Number(p.dose))))].sort((a, b) => a - b);
  let at = doses.indexOf(2) >= 0 ? 2 : doses[0];
  let width = 0;
  const M = { l: 40, r: 14, t: 26, b: 40 };
  function draw() {
    if (!width) return;
    const height = Math.round(Math.min(270, Math.max(220, width * 0.5)));
    const x = linear(doses[0], doses[doses.length - 1], M.l, width - M.r);
    const yt = niceTicks(0, 1, 4);
    const y = linear(0, 1, height - M.b, M.t);
    const root = svg("svg", { width, height, role: "img", "aria-label": w.aria });
    const axis = svg("g", { "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      if (tick < 0 || tick > 1) continue;
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    for (const v of doses) axis.append(svg("text", { x: x(v), y: height - M.b + 14, "text-anchor": "middle" }, String(v)));
    axis.append(svg("text", { x: (M.l + width - M.r) / 2, y: height - 4, "text-anchor": "middle", class: "axis-label" }, w.axisX));
    axis.append(svg("text", { x: 0, y: 10, class: "axis-label" }, w.axisY));
    // the rate with the real instruction in the prompt
    axis.append(svg("path", { d: `M${M.l} ${y(Number(d.instructed))}H${width - M.r}`, class: "level-instructed" }));
    axis.append(svg("text", { x: width - M.r, y: y(Number(d.instructed)) - 5, "text-anchor": "end", class: "on-plot quiet" }, w.instructed));
    root.append(axis);
    root.append(svg("path", { d: `M${x(at)} ${M.t}V${height - M.b}`, class: "chosen-line" }));
    for (const c of d.controls) root.append(svg("circle", { cx: x(Number(c.dose)), cy: y(Number(c.rate)), r: 2.8, class: "control-mark", "data-series": c.series }));
    for (const s of d.series) {
      const pts = s.points.map((p) => [x(Number(p.dose)), y(Number(p.rate))]);
      root.append(svg("path", { d: "M" + pts.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("L"), class: style[s.key], "data-series": s.key }));
      s.points.forEach((p, i) => {
        if (s.key === "neutral") root.append(svg("path", { d: `M${pts[i][0]} ${y(Number(p.lo))}V${y(Number(p.hi))}`, class: "interval" }));
        const mark = svg("circle", { cx: pts[i][0], cy: pts[i][1], r: Number(p.dose) === at ? 4.2 : 3, class: `mark ${style[s.key].replace("series ", "")}`, "data-series": s.key, "data-dose": p.dose });
        tipOn(mark, [[label[s.key]], [`${w.dose} `, h("b", { text: p.dose })], [h("b", { text: p.rate }), ` (${p.lo} to ${p.hi})`]]);
        root.append(mark);
      });
    }
    const move = (event) => {
      const px = event.clientX - root.getBoundingClientRect().left;
      const best = doses.reduce((a, b) => (Math.abs(x(b) - px) < Math.abs(x(a) - px) ? b : a));
      if (best !== at) {
        at = best;
        draw();
      }
    };
    root.addEventListener("pointermove", move);
    root.addEventListener("pointerdown", move);
    clear(box).append(root);
    const readout = clear(document.getElementById("su-readout"));
    readout.append(h("span", {}, `${w.dose} `, h("b", { text: String(at) })));
    for (const s of d.series) {
      const p = s.points.find((q) => Number(q.dose) === at);
      if (p) readout.append(h("span", { "data-series": s.key }, `${label[s.key]} `, h("b", { text: p.rate })));
    }
    figure.dataset.at = String(at);
  }
  onResize(box, (v) => {
    width = v;
    draw();
  });
}
