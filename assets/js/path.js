// The path of the count through the layers (an animated figure), and the causal test at layer 12.
// data/trace.json (written by tools/build_data.py, every value a string):
//   widths, counts[W] = [first, last]; stops[] = { id, kind: "state" | "before", group, geometry: { by_count, by_remaining },
//     curves[W]: { x[], y[] }  mean position of each (count, width) cell, aligned to the previous stop by a rotation and a scale,
//     readouts[]: { layer, transform, crossings: { up | down: { W: { x, y, count, remaining } } } } }
//   causal: { counts[], arms: { clean, shift40, shift60, perm40 } }
// Every stop is a measured state. Between two stops the positions are interpolated: that movement is a visual device. A stop of
// kind "before" is the state before a mixer's stored write, seen in the same frame, so the step from it to the next stop moves
// each cell by the measured write. The sentences and words shown come from the page (the list #path-labels, data attributes).
import { svg, h, clear, linear, niceTicks, tickText, onResize } from "./svg.js";

const DASH = ["1 3", "5 3", "", "9 3 2 3", "12 4"]; // one line style per width, narrowest first
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function initPath(trace) {
  const figure = document.getElementById("fig-path");
  if (!figure) return;
  const words = figure.dataset;
  const box = document.getElementById("path-plot");
  const labels = [...document.querySelectorAll("#path-labels li")];
  const range = document.getElementById("path-step");
  const button = document.getElementById("path-play");
  const widths = trace.widths;
  const maxCount = Math.max(...widths.map((w) => Number(trace.counts[w][1])));
  // Each stop is drawn at the same size: its points are centred and divided by their spread (the chain of fits between stops
  // carries a scale, which would let the later stops shrink). A state before a mixer's write shares the centre and the size of
  // the state after it, so that the step between the two is the write itself.
  const raw = trace.stops.map((s) => Object.fromEntries(widths.map((w) => [w, s.curves[w].x.map((x, i) => [Number(x), -Number(s.curves[w].y[i])])])));
  const frameOf = raw.map((pts) => {
    const all = widths.flatMap((w) => pts[w]);
    const c = [0, 1].map((k) => all.reduce((a, p) => a + p[k], 0) / all.length);
    const spread = Math.sqrt(all.reduce((a, p) => a + (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2, 0) / all.length);
    return { c, spread };
  });
  const norm = (i) => (trace.stops[i].kind === "before" ? frameOf[i + 1] : frameOf[i]);
  const place1 = (i, p) => [(p[0] - norm(i).c[0]) / norm(i).spread, (p[1] - norm(i).c[1]) / norm(i).spread];
  const stops = trace.stops.map((s, i) => ({ ...s, pts: Object.fromEntries(widths.map((w) => [w, raw[i][w].map((p) => place1(i, p))])) }));
  let lo = [Infinity, Infinity];
  let hi = [-Infinity, -Infinity];
  for (const s of stops) for (const w of widths) for (const p of s.pts[w]) for (const k of [0, 1]) {
    lo[k] = Math.min(lo[k], p[k]);
    hi[k] = Math.max(hi[k], p[k]);
  }
  range.max = String(stops.length - 1);
  let at = 0; // a real number: the stop, or a place between two stops while moving
  let playing = null;
  let width = 0;
  let nodes = null;

  function build() {
    if (!width) return;
    const M = 26;
    const height = Math.round(Math.min(520, Math.max(300, width * 0.6)));
    const k = Math.min((width - 2 * M) / (hi[0] - lo[0]), (height - 2 * M) / (hi[1] - lo[1])); // one scale for both directions
    const ox = (width - k * (hi[0] - lo[0])) / 2;
    const oy = (height - k * (hi[1] - lo[1])) / 2;
    const X = (v) => ox + (v - lo[0]) * k;
    const Y = (v) => oy + (v - lo[1]) * k;
    const root = svg("svg", { width, height, role: "img", "aria-label": words.aria });
    const lines = widths.map((w, i) => svg("path", { class: "path-line", "stroke-dasharray": DASH[i] || null, "data-width": w }));
    const dots = widths.map((w) => {
      const first = Number(trace.counts[w][0]);
      return stops[0].pts[w].map((p, j) => (j % 2 ? null : svg("circle", { r: width < 500 ? 2.2 : 2.8, class: "curve-pt", style: `--t:${((first + j) / maxCount).toFixed(3)}`, "data-width": w })));
    });
    const ends = widths.map((w) => svg("text", { class: "on-plot quiet", "aria-hidden": "true" }, w));
    const marks = svg("g", { "aria-hidden": "true" });
    root.append(...lines, ...dots.flat().filter(Boolean), ...ends, marks);
    clear(box).append(root);
    nodes = { X, Y, lines, dots, ends, marks, width };
    place();
  }

  function position(w, t) {
    const a = stops[Math.floor(t)];
    const b = stops[Math.min(stops.length - 1, Math.floor(t) + 1)];
    const f = t - Math.floor(t);
    const e = f * f * (3 - 2 * f);
    return a.pts[w].map((p, j) => [p[0] + (b.pts[w][j][0] - p[0]) * e, p[1] + (b.pts[w][j][1] - p[1]) * e]);
  }

  function place() {
    if (!nodes) return;
    const { X, Y, lines, dots, ends, marks } = nodes;
    widths.forEach((w, i) => {
      const pts = position(w, at);
      lines[i].setAttribute("d", "M" + pts.map((p) => `${X(p[0]).toFixed(1)} ${Y(p[1]).toFixed(1)}`).join("L"));
      pts.forEach((p, j) => {
        const dot = dots[i][j];
        if (dot) {
          dot.setAttribute("cx", X(p[0]).toFixed(1));
          dot.setAttribute("cy", Y(p[1]).toFixed(1));
        }
      });
      const last = pts[pts.length - 1];
      const prev = pts[pts.length - 4];
      const d = Math.hypot(last[0] - prev[0], last[1] - prev[1]) || 1;
      ends[i].setAttribute("x", (X(last[0]) + ((last[0] - prev[0]) / d) * 12 - 8).toFixed(1));
      ends[i].setAttribute("y", (Y(last[1]) + ((last[1] - prev[1]) / d) * 12 + 4).toFixed(1));
    });
    clear(marks);
    if (Number.isInteger(at)) {
      // where the transforms that read this frame cross their thresholds on each width's curve, joined across the widths
      for (const r of stops[at].readouts) {
        const cls = r.transform === 410 ? "c-b" : r.transform === 1749 ? "c-c" : "c-ink";
        for (const [kind, per] of Object.entries(r.crossings)) {
          const pts = widths.filter((w) => per[w]).map((w) => place1(at, [Number(per[w].x), -Number(per[w].y)])).map((p) => [X(p[0]), Y(p[1])]);
          if (!pts.length) continue;
          const g = svg("g", { class: `level ${cls}`, "data-transform": r.transform, "data-kind": kind });
          if (pts.length > 1) g.append(svg("path", { d: "M" + pts.map((p) => p.join(" ")).join("L"), class: "level-line" }));
          for (const p of pts) g.append(svg("circle", { cx: p[0], cy: p[1], r: 4.5, class: "level-pt" }));
          const tip = pts[pts.length - 1];
          const right = tip[0] < nodes.width - 96;
          g.append(svg("text", { x: tip[0] + (right ? 9 : -9), y: tip[1] - 8, "text-anchor": right ? "start" : "end", class: "on-plot strong" }, `${r.transform} ${kind === "up" ? "on" : "off"}`));
          marks.append(g);
        }
      }
    }
  }

  function show() {
    const i = Math.round(at);
    range.value = String(i);
    labels.forEach((li, j) => li.classList.toggle("current", j === i));
    const s = stops[i];
    const readout = clear(document.getElementById("path-readout"));
    readout.append(h("span", {}, `${words.stop} `, h("b", { text: `${i + 1} / ${stops.length}` })), h("span", {}, h("b", { text: s.id })));
    if (s.group) readout.append(h("span", {}, "group ", h("b", { text: String(s.group) })));
    readout.append(h("span", {}, `${words.countShare} `, h("b", { text: s.geometry.by_count })), h("span", {}, `${words.remainingShare} `, h("b", { text: s.geometry.by_remaining })));
    figure.dataset.at = String(i);
  }

  function stop() {
    if (playing) cancelAnimationFrame(playing);
    playing = null;
    button.textContent = words.play;
    button.setAttribute("aria-pressed", "false");
  }

  function go(target) {
    at = Math.max(0, Math.min(stops.length - 1, target));
    place();
    show();
  }

  function play() {
    if (playing) return stop();
    if (Math.round(at) >= stops.length - 1) go(0);
    button.textContent = words.pause;
    button.setAttribute("aria-pressed", "true");
    const MOVE = 1500;
    const REST = 1700;
    let from = Math.round(at);
    let t0 = null;
    const tick = (now) => {
      if (t0 === null) t0 = now;
      const dt = now - t0;
      if (reduced()) {
        // no tweening: one stop per rest period
        if (dt >= REST) {
          from += 1;
          t0 = now;
          go(from);
        }
      } else if (dt < MOVE) {
        at = from + dt / MOVE;
        place();
      } else if (at !== from + 1) {
        go(from + 1);
      } else if (dt >= MOVE + REST) {
        from += 1;
        t0 = now;
      }
      if (from >= stops.length - 1) return stop();
      playing = requestAnimationFrame(tick);
    };
    playing = requestAnimationFrame(tick);
  }

  button.addEventListener("click", play);
  range.addEventListener("input", () => {
    stop();
    go(Number(range.value));
  });
  figure.classList.add("live");
  onResize(box, (w) => {
    width = w;
    build();
  });
  go(0);
  stop();
}

// the causal test: mean margin by characters in the line, clean and with the read of head 13 shifted
export function initCausal(trace) {
  const figure = document.getElementById("fig-causal");
  if (!figure) return;
  const words = figure.dataset;
  const box = document.getElementById("causal-plot");
  const c = trace.causal;
  const xs = c.counts.map(Number);
  const arms = [
    ["clean", "series s-n", words.lineClean],
    ["shift40", "series s-unit c-c", figure.getAttribute("data-line-40")],
    ["shift60", "series s-unit c-b", figure.getAttribute("data-line-60")],
    ["perm40", "series s-r recorded", words.linePerm],
  ];
  let at = xs.indexOf(50) >= 0 ? xs.indexOf(50) : Math.floor(xs.length / 2);
  let width = 0;
  const M = { l: 44, r: 12, t: 26, b: 40 };
  function draw() {
    if (!width) return;
    const height = Math.round(Math.min(340, Math.max(240, width * 0.5)));
    const all = arms.flatMap(([k]) => c.arms[k].map(Number));
    const yt = niceTicks(Math.min(...all), Math.max(...all), 5);
    const x = linear(xs[0], xs[xs.length - 1], M.l, width - M.r);
    const y = linear(yt.lo, yt.hi, height - M.b, M.t);
    const root = svg("svg", { width, height, role: "img", "aria-label": words.aria });
    const axis = svg("g", { "data-axis": "causal", "aria-hidden": "true" });
    for (const tick of yt.ticks) {
      axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
      axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
    }
    for (const v of xs) if (v % 20 === 0) axis.append(svg("text", { x: x(v), y: height - M.b + 14, "text-anchor": "middle" }, String(v)));
    root.append(axis);
    const titles = svg("g", { "aria-hidden": "true" });
    titles.append(svg("text", { x: (M.l + width - M.r) / 2, y: height - 4, "text-anchor": "middle", class: "axis-label" }, words.axisX));
    titles.append(svg("text", { x: 0, y: 10, class: "axis-label" }, words.axisY));
    root.append(titles);
    for (const [key, cls] of arms) root.append(svg("path", { d: "M" + c.arms[key].map((v, i) => `${x(xs[i])} ${y(Number(v))}`).join("L"), class: cls, "data-arm": key }));
    root.append(svg("path", { d: `M${x(xs[at])} ${M.t}V${height - M.b}`, class: "chosen-line" }));
    for (const [key, cls] of arms) root.append(svg("circle", { cx: x(xs[at]), cy: y(Number(c.arms[key][at])), r: 3.6, class: `mark ${cls.replace("series ", "")}` }));
    const move = (event) => {
      const px = event.clientX - root.getBoundingClientRect().left;
      let best = 0;
      xs.forEach((v, i) => {
        if (Math.abs(x(v) - px) < Math.abs(x(xs[best]) - px)) best = i;
      });
      if (best !== at) {
        at = best;
        draw();
      }
    };
    root.addEventListener("pointermove", move);
    root.addEventListener("pointerdown", move);
    clear(box).append(root);
    const readout = clear(document.getElementById("causal-readout"));
    readout.append(h("span", {}, `${words.axisX} `, h("b", { text: c.counts[at] })));
    for (const [key, , label] of arms) readout.append(h("span", { "data-arm": key }, `${label} `, h("b", { text: c.arms[key][at] })));
  }
  onResize(box, (w) => {
    width = w;
    draw();
  });
}
