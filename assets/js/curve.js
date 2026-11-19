// The character count inside the frame of one state group, and how two transforms read it.
// data/count-curve.json:   widths[w]: { counts[], x[], y[], tokens[] }   the mean code by count, in the plane of its two largest components
// data/count-readout.json: threshold[t], direction[t] = [x, y] in the same plane,
//                          widths[w][t]: { gate[], frame[], rate[] }      means by count of the gate input, of its part from the frame, and the firing rate
// Every value is a string written by tools/build_data.py. One count is chosen for both figures; the words on the plots come from the page.
import { svg, h, clear, linear, niceTicks, tickText, onResize, segmented } from "./svg.js";

const SHAPE = { 60: "circle", 100: "square" };

export function initCurve(curve, readout) {
  const widthKeys = Object.keys(curve.widths).sort((a, b) => Number(a) - Number(b));
  const maxCount = Math.max(...widthKeys.map((w) => curve.widths[w].counts.length - 1));
  const state = { count: 30, transform: readout ? readout.transforms[0] : null, width: widthKeys[widthKeys.length - 1] };
  const listeners = [];
  const set = (change) => {
    Object.assign(state, change);
    for (const f of listeners) f();
  };

  // ---------------------------------------------------------------- the curve in its plane, shared by both figures
  const pts = widthKeys.flatMap((w) => curve.widths[w].counts.map((c, i) => ({ w, c: Number(c), x: Number(curve.widths[w].x[i]), y: Number(curve.widths[w].y[i]), tokens: curve.widths[w].tokens[i] })));
  const ext = { x0: Math.min(...pts.map((p) => p.x)), x1: Math.max(...pts.map((p) => p.x)), y0: Math.min(...pts.map((p) => p.y)), y1: Math.max(...pts.map((p) => p.y)) };

  function plane(box, words, { shade, arrow }) {
    let width = 0;
    function draw() {
      if (!width) return;
      const M = { l: 14, r: 14, t: 26, b: 26 };
      const height = Math.round(Math.min(480, Math.max(280, width * 0.66)));
      const k = Math.min((width - M.l - M.r) / (ext.x1 - ext.x0), (height - M.t - M.b) / (ext.y1 - ext.y0)); // one scale for both directions
      const ox = M.l + (width - M.l - M.r - k * (ext.x1 - ext.x0)) / 2;
      const oy = M.t + (height - M.t - M.b - k * (ext.y1 - ext.y0)) / 2;
      const X = (v) => ox + (v - ext.x0) * k;
      const Y = (v) => oy + (ext.y1 - v) * k;
      const root = svg("svg", { width, height, role: "img", "aria-label": words.aria });
      const labels = svg("g", { "aria-hidden": "true" });
      labels.append(svg("text", { x: width - 4, y: height - 6, "text-anchor": "end", class: "axis-label" }, words.x));
      labels.append(svg("text", { x: 4, y: 12, class: "axis-label" }, words.y));
      root.append(labels);
      const ticks = svg("g", { "data-axis": "count", "aria-hidden": "true" });
      for (const w of widthKeys) {
        const d = curve.widths[w];
        const line = d.counts.map((c, i) => `${X(Number(d.x[i]))} ${Y(Number(d.y[i]))}`);
        root.append(svg("path", { d: `M${line.slice(1).join("L")}`, class: "curve-path" }));
        d.counts.forEach((c, i) => {
          if (Number(c) > 0 && Number(c) % 20 === 0) ticks.append(svg("text", { x: X(Number(d.x[i])) + 7, y: Y(Number(d.y[i])) - 7 }, c));
        });
      }
      root.append(ticks);
      for (const p of pts) {
        const t = shade ? shade(p) : p.c / maxCount;
        const hot = p.c === state.count && (!arrow || p.w === state.width);
        const r = hot ? 6 : p.c === 0 ? 4.4 : 3.1;
        const attrs = { class: `curve-pt${hot ? " hot" : ""}${shade ? " by-rate" : ""}`, style: `--t:${t.toFixed(3)}`, "data-count": p.c, "data-width": p.w };
        root.append(SHAPE[p.w] === "circle" ? svg("circle", { cx: X(p.x), cy: Y(p.y), r, ...attrs }) : svg("rect", { x: X(p.x) - r, y: Y(p.y) - r, width: 2 * r, height: 2 * r, ...attrs }));
      }
      const first = pts.filter((p) => p.c === 0).sort((a, b) => a.y - b.y)[0];
      const note = svg("g", { "aria-hidden": "true" });
      note.append(svg("text", { x: X(first.x) + 9, y: Y(first.y) + 4, class: "on-plot quiet" }, words.first));
      if (arrow) {
        const [dx, dy] = arrow().map(Number);
        const len = Math.hypot(dx, dy);
        const L = Math.min(width, height) * 0.3;
        const ax = X(0) + (dx / len) * L;
        const ay = Y(0) - (dy / len) * L;
        const ux = (ax - X(0)) / L;
        const uy = (ay - Y(0)) / L;
        note.append(svg("path", { d: `M${X(0)} ${Y(0)}L${ax - ux * 9} ${ay - uy * 9}`, class: "arrow-mean read-arrow" }));
        note.append(svg("path", { d: `M${ax} ${ay}L${ax - ux * 12 - uy * 6} ${ay - uy * 12 + ux * 6}L${ax - ux * 12 + uy * 6} ${ay - uy * 12 - ux * 6}z`, class: "arrow-mean-head read-arrow" }));
        note.append(svg("text", { x: ax + (ux >= 0 ? 8 : -8), y: ay + (uy > 0 ? 14 : -6), "text-anchor": ux >= 0 ? "start" : "end", class: "on-plot strong" }, words.arrow));
      }
      root.append(note);
      const at = (event) => {
        const b = root.getBoundingClientRect();
        const px = event.clientX - b.left;
        const py = event.clientY - b.top;
        let best = null;
        let dist = 22 * 22;
        for (const p of pts) {
          if (arrow && p.w !== state.width) continue;
          const d = (X(p.x) - px) ** 2 + (Y(p.y) - py) ** 2;
          if (d < dist) {
            dist = d;
            best = p;
          }
        }
        if (best && best.c !== state.count) set({ count: best.c });
      };
      root.addEventListener("pointermove", at);
      root.addEventListener("pointerdown", at);
      clear(box).append(root);
    }
    onResize(box, (w) => {
      width = w;
      draw();
    });
    return draw;
  }

  function slider(id) {
    const range = document.getElementById(id);
    range.max = String(maxCount);
    range.addEventListener("input", () => set({ count: Number(range.value) }));
    return () => {
      range.value = String(state.count);
    };
  }

  // ---------------------------------------------------------------- the count as a curve
  const figure = document.getElementById("fig-curve");
  const drawPlane = plane(document.getElementById("curve-plot"), figure.dataset, {});
  const syncCurve = slider("curve-count");
  const keyOf = { 60: figure.querySelector(".keys li:nth-child(1)").textContent, 100: figure.querySelector(".keys li:nth-child(2)").textContent };
  listeners.push(() => {
    syncCurve();
    drawPlane();
    const box = clear(document.getElementById("curve-readout"));
    box.append(h("span", {}, `${figure.dataset.count} `, h("b", { text: String(state.count) })));
    for (const w of widthKeys) {
      const tokens = curve.widths[w].tokens[state.count];
      if (tokens !== undefined) box.append(h("span", {}, `${figure.dataset.tokens}, ${keyOf[w].toLowerCase()} `, h("b", { text: tokens })));
    }
  });

  // ---------------------------------------------------------------- how the two transforms read it
  const read = document.getElementById("fig-read");
  if (read && readout) {
    const words = read.dataset;
    const unitBox = document.getElementById("read-transform");
    for (const t of readout.transforms) unitBox.append(h("button", { type: "button", "data-value": t, "aria-pressed": "false", text: `L9 transform ${t}` }));
    const unitSeg = segmented(unitBox, (value) => set({ transform: value }));
    const widthBox = document.getElementById("read-width");
    for (const w of widthKeys) widthBox.append(h("button", { type: "button", "data-value": w, "aria-pressed": "false", text: w }));
    const widthSeg = segmented(widthBox, (value) => set({ width: value, count: Math.min(state.count, curve.widths[value].counts.length - 1) }));
    const syncRead = slider("read-count");
    const series = () => readout.widths[state.width][state.transform];
    const drawRead = plane(document.getElementById("read-plane"), { aria: words.ariaPlane, x: figure.dataset.x, y: figure.dataset.y, first: figure.dataset.first, arrow: words.arrow },
      { shade: (p) => Number(readout.widths[p.w][state.transform].rate[p.c]), arrow: () => readout.direction[state.transform] });

    const charts = { lines: document.getElementById("read-lines"), rate: document.getElementById("read-rate") };
    const cw = { lines: 0, rate: 0 };
    const M = { l: 40, r: 10, t: 12, b: 30 };
    function chart(kind) {
      const width = cw[kind];
      if (!width) return;
      const s = series();
      const n = s.gate.length;
      const height = kind === "lines" ? 230 : 130;
      const x = linear(0, maxCount, M.l, width - M.r);
      const root = svg("svg", { width, height, role: "img", "aria-label": kind === "lines" ? words.ariaLines : words.ariaRate });
      let yt;
      if (kind === "lines") {
        // one vertical scale per transform, over both widths, so that it does not move when the width changes
        const all = widthKeys.flatMap((w) => [...readout.widths[w][state.transform].gate, ...readout.widths[w][state.transform].frame].map(Number));
        yt = niceTicks(Math.min(...all), Math.max(...all), 4);
      } else {
        yt = { ticks: [0, 0.5, 1], step: 0.5, lo: 0, hi: 1 };
      }
      const y = linear(yt.lo, yt.hi, height - M.b, M.t);
      const axis = svg("g", { "data-axis": kind, "aria-hidden": "true" });
      for (const tick of yt.ticks) {
        axis.append(svg("path", { d: `M${M.l} ${y(tick)}H${width - M.r}`, class: tick === 0 ? "zero" : "gridline" }));
        axis.append(svg("text", { x: M.l - 7, y: y(tick) + 3.5, "text-anchor": "end" }, tickText(tick, yt.step)));
      }
      for (let c = 0; c <= maxCount; c += 20) axis.append(svg("text", { x: x(c), y: height - M.b + 14, "text-anchor": "middle" }, String(c)));
      root.append(axis);
      const labels = svg("g", { "aria-hidden": "true" });
      if (kind === "rate") labels.append(svg("text", { x: (M.l + width - M.r) / 2, y: height - 2, "text-anchor": "middle", class: "axis-label" }, words.axisX));
      root.append(labels);
      const line = (values) => "M" + values.map((v, i) => `${x(i)} ${y(Number(v))}`).join("L");
      if (kind === "lines") {
        const th = y(Number(readout.threshold[state.transform]));
        root.append(svg("path", { d: `M${M.l} ${th}H${width - M.r}`, class: "mean-line target" }));
        labels.append(svg("text", { x: width - M.r - 4, y: th - 5, "text-anchor": "end", class: "on-plot quiet" }, words.lineThreshold));
        root.append(svg("path", { d: line(s.frame), class: "series s-r" }));
        root.append(svg("path", { d: line(s.gate), class: "series s-unit" }));
      } else {
        root.append(svg("path", { d: `${line(s.rate)}L${x(n - 1)} ${y(0)}L${x(0)} ${y(0)}z`, class: "band-fill rate-fill" }));
        root.append(svg("path", { d: line(s.rate), class: "series s-unit" }));
      }
      const c = Math.min(state.count, n - 1);
      root.append(svg("path", { d: `M${x(c)} ${M.t}V${height - M.b}`, class: "chosen-line" }));
      const value = kind === "lines" ? s.gate[c] : s.rate[c];
      root.append(svg("circle", { cx: x(c), cy: y(Number(value)), r: 5, class: "mark s-unit chosen" }));
      const at = (event) => {
        const v = Math.round(((event.clientX - root.getBoundingClientRect().left - M.l) / (width - M.l - M.r)) * maxCount);
        const clamped = Math.max(0, Math.min(n - 1, v));
        if (clamped !== state.count) set({ count: clamped });
      };
      root.addEventListener("pointermove", at);
      root.addEventListener("pointerdown", at);
      clear(charts[kind]).append(root);
    }
    for (const kind of Object.keys(charts)) {
      onResize(charts[kind], (w) => {
        cw[kind] = w;
        chart(kind);
      });
    }
    listeners.push(() => {
      unitSeg.set(state.transform);
      widthSeg.set(state.width);
      syncRead();
      read.classList.remove("c-b", "c-c");
      read.classList.add(state.transform === readout.transforms[0] ? "c-b" : "c-c");
      drawRead();
      chart("lines");
      chart("rate");
      const s = series();
      const c = Math.min(state.count, s.gate.length - 1);
      const box = clear(document.getElementById("read-readout"));
      for (const [label, text] of [[words.count, String(c)], [words.readoutGate, s.gate[c]], [words.readoutFrame, s.frame[c]], [words.readoutThreshold, readout.threshold[state.transform]], [words.readoutRate, s.rate[c]]]) {
        box.append(h("span", {}, `${label} `, h("b", { text })));
      }
    });
  }
  set({});
}
