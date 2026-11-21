// The path of the count through the layers, as one mesh in one fixed coordinate system, and the causal test at layer 12.
// data/trace.json (written by tools/build_data.py, every value a string):
//   widths, counts[W] = [first, last]
//   path: { highlight, connect, stops[] = { id, kind: "state" | "before", group, spread: { count, remaining },
//           curves[W]: { x[], y[], z[] }   mean position of each (count, width) cell in ONE fixed view (no stop is re-aligned or re-scaled),
//           frame: { axes[2] = [x, y, z], holds, shared?: { directions, cosines[] }, write_inside? }   the main group's frame in the view,
//           cuts[] = { transform, shape: "line", direction: [x, y], offset, plane3d?: { normal, offset } }   the transform fires where direction . p > offset
//                  | { transform, shape: "points", kind: up | down, points: { W: { x, y, z, count, remaining } } } } }
//   causal: { counts[], arms: { clean, shift40, shift60, perm40 } }
// The mesh: one curve per width (the count runs along it) and connectors across the widths at equal count. Every stop is a
// measured state. Between two stops the positions are interpolated (a visual device), except between the stop of kind "before"
// and the stop after it: there the positions are the state before the write plus a fraction of the head's measured write.
// The sentences and words shown come from the page (the story beside the figure, data attributes).
import { svg, h, clear, linear, niceTicks, tickText, onResize, segmented } from "./svg.js";

const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const SEG = 4; // cells per coloured piece of a curve

// Intersect a validated threshold plane with the box enclosing all the measured states.
// Ordering in the plane keeps the same patch attached to the data as the camera turns.
function planePatch(plane, lo, hi) {
  const normal = plane.normal.map(Number);
  const corners = [];
  for (let d = 0; d < 3; d++) {
    if (Math.abs(normal[d]) < 1e-9) continue;
    const a = (d + 1) % 3, b = (d + 2) % 3;
    for (const u of [lo[a], hi[a]]) for (const v of [lo[b], hi[b]]) {
      const t = (Number(plane.offset) - normal[a] * u - normal[b] * v) / normal[d];
      if (t < lo[d] || t > hi[d]) continue;
      const p = [0, 0, 0];
      p[d] = t;
      p[a] = u;
      p[b] = v;
      corners.push(p);
    }
  }
  if (corners.length < 3) return [];
  const components = normal.map(Math.abs);
  const d = components.indexOf(Math.max(...components));
  const a = (d + 1) % 3, b = (d + 2) % 3;
  const mean = (axis) => corners.reduce((sum, p) => sum + p[axis], 0) / corners.length;
  const u = mean(a), v = mean(b);
  const angle = (p) => Math.atan2(p[b] - v, p[a] - u);
  return corners.sort((p, q) => angle(p) - angle(q));
}

export function initPath(trace) {
  const figure = document.getElementById("fig-path");
  if (!figure) return;
  const words = figure.dataset;
  const path = trace.path;
  const box = document.getElementById("path-plot");
  const widths = trace.widths;
  const first = Object.fromEntries(widths.map((w) => [w, Number(trace.counts[w][0])]));
  const maxCount = Math.max(...widths.map((w) => Number(trace.counts[w][1])));
  const stops = path.stops.map((s) => ({
    ...s,
    pts: Object.fromEntries(widths.map((w) => {
      const { x, y, z } = s.curves[w];
      return [w, x.map((v, i) => [Number(v), Number(y[i]), Number(z?.[i] ?? 0)])];
    })),
  }));
  const before = stops.findIndex((s) => s.kind === "before");
  // the five stages of the story: where the mesh stands, and what is marked there
  const stages = [
    { key: "a", at: 0, cuts: true },
    { key: "b", at: before - 1 },
    { key: "c", at: before + 1, trail: true },
    { key: "d", at: stops.findIndex((s, i) => i > before + 1 && s.cuts.length), cuts: true },
    { key: "e", at: stops.length - 1 },
  ];
  const names = Object.fromEntries(stages.map((s) => [s.key, figure.getAttribute(`data-stage-${s.key}`)]));
  const points = stops.flatMap((s) => widths.flatMap((w) => s.pts[w]));
  const lo = [0, 1, 2].map((d) => Math.min(...points.map((p) => p[d])));
  const hi = [0, 1, 2].map((d) => Math.max(...points.map((p) => p[d])));
  const center = lo.map((v, d) => (v + hi[d]) / 2);
  for (const stop of stops) for (const cut of stop.cuts) {
    if (cut.plane3d) cut.patch = planePatch(cut.plane3d, lo, hi);
  }
  const state = { stage: 0, pos: 0, colour: "count" };
  let yaw = 0, pitch = 0;
  let camera = [[1, 0, 0], [0, 1, 0]];
  let playing = null, timer = null;
  let width = 0;
  let nodes = null;

  // The camera looks along the third common direction at rest. Every stop and
  // its annotations use this one orthographic camera throughout playback.
  function rotateVector([x, y, z]) {
    return camera.map(([a, b, c]) => a * x + b * y + c * z);
  }

  function project(p) {
    const [x, y] = rotateVector(p.map((v, d) => v - center[d]));
    return [nodes.width / 2 + x * nodes.k, nodes.height / 2 - y * nodes.k];
  }

  function fitCamera() {
    // Fit every stop together. The scale changes only for a resize or a camera turn.
    let k = nodes.frontScale;
    for (const p of points) {
      const [x, y] = rotateVector(p.map((v, d) => v - center[d]));
      if (x) k = Math.min(k, nodes.halfWidth / Math.abs(x));
      if (y) k = Math.min(k, nodes.halfHeight / Math.abs(y));
    }
    nodes.k = k;
    figure.dataset.scale = k.toFixed(1);
  }

  function build() {
    if (!width) return;
    const M = width < 420 ? 14 : 22;
    // the read-out keeps the height of its tallest stage, so the plot does not move from stage to stage
    const readout = document.getElementById("path-readout");
    readout.style.minHeight = "";
    let tall = 0;
    stages.forEach((st, i) => {
      tall = Math.max(tall, fill(i, st.at).offsetHeight);
    });
    readout.style.minHeight = `${tall}px`;
    // beside the story the figure stays in view: the plot takes the height that the window leaves
    const panel = box.parentElement;
    const beside = window.matchMedia("(min-width: 1001px)").matches;
    const room = beside ? window.innerHeight - (panel.offsetHeight - box.offsetHeight) - 30 : Infinity;
    const most = Math.max(200, Math.min(window.innerHeight * 0.7, room));
    // one fixed scale for both directions and all stops; the plot is as tall as the path needs at that scale
    const k = Math.min((width - 2 * M) / (hi[0] - lo[0]), (most - 2 * M) / (hi[1] - lo[1]));
    const height = Math.round(k * (hi[1] - lo[1]) + 2 * M);
    const root = svg("svg", { width, height, role: "img", "aria-label": words.aria });
    const ghost = svg("g", { class: "ghost", "aria-hidden": "true" });
    const connectors = [];
    for (let c = path.connect; c <= maxCount; c += path.connect) {
      const has = widths.filter((w) => c >= first[w] && c - first[w] < stops[0].pts[w].length);
      if (has.length > 1) connectors.push({ c, has, node: svg("path", { class: "mesh-connector" }) });
    }
    const pieces = widths.map((w) => {
      const n = stops[0].pts[w].length;
      const list = [];
      for (let a = 0; a < n - 1; a += SEG) {
        const b = Math.min(n - 1, a + SEG);
        const count = first[w] + (a + b) / 2;
        list.push({ a, b, count, remaining: Number(w) - count, node: svg("path", { class: "mesh-curve" }) });
      }
      return list;
    });
    const ends = widths.map((w) => svg("path", { class: "mesh-end", "data-width": w }));
    const labels = widths.map((w) => svg("text", { class: "on-plot quiet", "aria-hidden": "true" }, w));
    const marks = svg("g", { "aria-hidden": "true" });
    // the frame of the current layer's main group: its two directions closest to the view's plane and the patch between them,
    // in the view's own coordinates and at the mesh's scale, set in a corner
    const axes = stops[0].frame ? [svg("path", { class: "frame-patch" }), svg("path", { class: "frame-axis" }), svg("path", { class: "frame-axis" })] : [];
    const frame = svg("g", { class: "frame-axes", "aria-hidden": "true" }, ...axes);
    const planes = svg("g", { "aria-hidden": "true" });
    root.append(planes, ghost, ...connectors.map((c) => c.node), ...pieces.flat().map((p) => p.node), ...ends, ...labels, marks, frame);
    clear(box).append(root);
    nodes = { k, frontScale: k, halfWidth: width / 2 - M, halfHeight: height / 2 - M,
      planes, ghost, connectors, pieces, ends, labels, marks, width, height, axes };
    fitCamera();
    colour();
    place();
    show();
  }

  function colour() {
    if (!nodes) return;
    nodes.pieces.forEach((list, i) => {
      for (const p of list) {
        const t = state.colour === "count" ? p.count / maxCount : 1 - Math.min(1, p.remaining / maxCount);
        p.node.setAttribute("style", `--t:${t.toFixed(3)}`);
      }
    });
  }

  function position(w, t) {
    const a = stops[Math.floor(t)];
    const b = stops[Math.min(stops.length - 1, Math.floor(t) + 1)];
    const f = t - Math.floor(t);
    // the step of the write is linear: the state before plus a fraction of the write; the other steps are eased
    const e = Math.floor(t) === before ? f : f * f * (3 - 2 * f);
    return a.pts[w].map((p, j) => p.map((v, d) => v + (b.pts[w][j][d] - v) * e));
  }

  const line = (pts) => "M" + pts.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("L");

  function place() {
    if (!nodes) return;
    const { ghost, connectors, pieces, ends, labels, marks, planes } = nodes;
    const front = yaw === 0 && pitch === 0;
    const at = {};
    widths.forEach((w, i) => {
      const pts = position(w, state.pos).map(project);
      at[w] = pts;
      for (const piece of pieces[i]) piece.node.setAttribute("d", line(pts.slice(piece.a, piece.b + 1)));
      const from = Math.max(0, Number(w) - path.highlight - first[w]);
      ends[i].setAttribute("d", line(pts.slice(Math.min(from, pts.length - 2))));
      const last = pts[pts.length - 1];
      const prev = pts[Math.max(0, pts.length - 5)];
      const d = Math.hypot(last[0] - prev[0], last[1] - prev[1]) || 1;
      const labelX = last[0] + ((last[0] - prev[0]) / d) * 14 - 8;
      const labelY = last[1] + ((last[1] - prev[1]) / d) * 14 + 4;
      labels[i].setAttribute("x", Math.max(1, Math.min(nodes.width - 7 * w.length, labelX)).toFixed(1));
      labels[i].setAttribute("y", Math.max(12, Math.min(nodes.height - 2, labelY)).toFixed(1));
    });
    for (const c of connectors) c.node.setAttribute("d", line(c.has.map((w) => at[w][c.c - first[w]])));
    if (nodes.axes.length) {
      const i0 = Math.floor(state.pos);
      const i1 = Math.min(stops.length - 1, i0 + 1);
      const f = state.pos - i0;
      const vectors = [0, 1].map((i) => {
        const a = stops[i0].frame.axes[i].map(Number);
        const b = stops[i1].frame.axes[i].map(Number);
        const [x, y] = rotateVector([0, 1, 2].map((d) => (a[d] ?? 0) * (1 - f) + (b[d] ?? 0) * f));
        return [x * nodes.k, -y * nodes.k];
      });
      // Anchor the inset by its projected bounds, including a turn that reverses an axis.
      const origin = [0, 1].map((d) => 12 - Math.min(0, vectors[0][d]) - Math.min(0, vectors[1][d]));
      const tip = vectors.map(([x, y]) => [origin[0] + x, origin[1] + y]);
      nodes.axes[0].setAttribute("d", line([origin, tip[0], [tip[0][0] + tip[1][0] - origin[0], tip[0][1] + tip[1][1] - origin[1]], tip[1]]) + "Z");
      nodes.axes[1].setAttribute("d", line([origin, tip[0]]));
      nodes.axes[2].setAttribute("d", line([origin, tip[1]]));
    }
    clear(planes);
    clear(ghost);
    clear(marks);
    const stage = stages[state.stage];
    const inWrite = state.pos >= before && state.pos <= before + 1;
    if (inWrite && (stage.trail || state.pos < before + 1)) {
      // the state before the write, faint, and how far the end of each line has been moved by the write
      for (const w of widths) {
        const b = stops[before].pts[w].map(project);
        ghost.append(svg("path", { d: line(b), class: "ghost-curve" }));
        const j = b.length - 1;
        ghost.append(svg("path", { d: line([b[j], at[w][j]]), class: "trail", "data-width": w }));
        ghost.append(svg("circle", { cx: b[j][0], cy: b[j][1], r: 2.6, class: "trail-start" }));
      }
    }
    if (Number.isInteger(state.pos) && stage.cuts && stage.at === state.pos) {
      for (const cut of stops[state.pos].cuts) {
        const g = svg("g", { class: "level", "data-transform": cut.transform, "data-shape": cut.shape, "data-kind": cut.kind || null });
        let tip;
        if (cut.shape === "line" && !front) {
          if (!cut.patch?.length) continue;
          const polygon = cut.patch.map(project);
          planes.append(svg("path", { d: line(polygon) + "Z", class: "threshold-plane", "data-transform": cut.transform }));
          const top = polygon.reduce((p, q) => p[1] < q[1] ? p : q);
          tip = [Math.min(nodes.width - 8, Math.max(8, top[0])), Math.max(14, top[1] - 5)];
        } else if (cut.shape === "line") {
          // a straight cut: the line direction . p = offset, and the side where the transform fires, lightly shaded
          const u = [Number(cut.direction[0]), -Number(cut.direction[1])];
          const [ox, oy] = project([0, 0, 0]);
          const value = (p) => (u[0] * (p[0] - ox) + u[1] * (p[1] - oy)) / nodes.k - Number(cut.offset);
          const corners = [[1, 1], [nodes.width - 1, 1], [nodes.width - 1, nodes.height - 1], [1, nodes.height - 1]];
          const side = [];
          const ends2 = [];
          corners.forEach((a, i) => {
            const b = corners[(i + 1) % 4];
            const va = value(a);
            const vb = value(b);
            if (va >= 0) side.push(a);
            if (va >= 0 !== vb >= 0) {
              const m = [a[0] + ((b[0] - a[0]) * va) / (va - vb), a[1] + ((b[1] - a[1]) * va) / (va - vb)];
              side.push(m);
              ends2.push(m);
            }
          });
          if (ends2.length === 2) {
            g.append(svg("path", { d: line(side) + "Z", class: "level-side" }), svg("path", { d: line(ends2), class: "level-line straight" }));
            const top = ends2[0][1] < ends2[1][1] ? ends2[0] : ends2[1];
            const other = top === ends2[0] ? ends2[1] : ends2[0];
            const d = Math.hypot(other[0] - top[0], other[1] - top[1]) || 1;
            tip = [top[0] + ((other[0] - top[0]) / d) * 26 - u[0] * 22, top[1] + ((other[1] - top[1]) / d) * 26 - u[1] * 22];
          }
        } else {
          const pts = widths.filter((w) => cut.points[w]).map((w) => {
            const p = cut.points[w];
            return project([Number(p.x), Number(p.y), Number(p.z ?? 0)]);
          });
          if (pts.length > 1) g.append(svg("path", { d: line(pts), class: "level-line" }));
          for (const p of pts) g.append(svg("circle", { cx: p[0], cy: p[1], r: 4, class: "level-pt" }));
          tip = [pts[0][0] + (pts[0][0] < nodes.width - 60 ? 9 : -9), pts[0][1] - 9];
        }
        if (tip) g.append(svg("text", { x: tip[0], y: tip[1], "text-anchor": tip[0] < nodes.width - 60 ? "start" : "end", class: "on-plot strong" }, String(cut.transform)));
        marks.append(g);
      }
    }
  }

  // the read-out of one stage standing at one stop
  function fill(stageIndex, stopIndex) {
    const stage = stages[stageIndex];
    const s = stops[stopIndex];
    const readout = clear(document.getElementById("path-readout"));
    const head = h("div", { class: "readout-row" }, h("span", {}, h("b", { text: `${stageIndex + 1} / ${stages.length}` }), ` ${names[stage.key]}`), h("span", {}, h("b", { text: s.id })));
    if (s.group) head.append(h("span", {}, "group ", h("b", { text: String(s.group) })));
    readout.append(head);
    if (s.frame && words.frameHolds) {
      // the frame of this stop's group: what it shares with the previous group's frame, and how much of the shape it holds
      const row = h("div", { class: "readout-row" });
      if (s.frame.shared) row.append(h("span", {}, `${words.frameShared} `, h("b", { text: s.frame.shared.cosines.join(", ") })));
      row.append(h("span", {}, `${words.frameHolds} `, h("b", { text: s.frame.holds })));
      if (s.frame.write_inside && stage.trail) row.append(h("span", {}, `${words.writeInside} `, h("b", { text: s.frame.write_inside })));
      readout.append(row);
    }
    readout.append(h("div", { class: "readout-row" }, h("span", {}, `${words.spreadCount} `, h("b", { text: s.spread.count })), h("span", {}, `${words.spreadRemaining} `, h("b", { text: s.spread.remaining }))));
    return readout;
  }

  function show() {
    const stage = stages[state.stage];
    fill(state.stage, Math.round(state.pos));
    figure.dataset.stage = stage.key;
    figure.dataset.at = String(Math.round(state.pos));
    for (const step of document.querySelectorAll("#story .story-step")) step.classList.toggle("active", step.dataset.stage === stage.key);
    document.getElementById("path-prev").disabled = state.stage === 0;
    document.getElementById("path-next").disabled = state.stage === stages.length - 1;
  }

  function stop() {
    clearTimeout(timer);
    if (playing !== null) cancelAnimationFrame(playing);
    playing = null;
    button.textContent = words.play;
    button.setAttribute("aria-pressed", "false");
  }

  // move the mesh to a stage; `then` runs when it stands there
  function travel(index, then) {
    const target = stages[index];
    const from = state.pos;
    let to = target.at;
    let start = from;
    if (target.trail && !(from >= before && from < to)) start = before; // the write is always shown from the state before it
    state.stage = index;
    if (target.trail && !reduced()) state.pos = start;
    place();
    show();
    if (reduced() || (from === to && !target.trail)) {
      state.pos = to;
      place();
      show();
      if (then) playing = requestAnimationFrame(() => then());
      return;
    }
    const duration = target.trail ? 2600 : 700 + 500 * Math.abs(to - start);
    let t0 = null;
    const tick = (now) => {
      if (t0 === null) t0 = now;
      const f = Math.min(1, (now - t0) / duration);
      state.pos = start + (to - start) * f;
      if (f === 1) state.pos = to;
      place();
      if (f < 1) playing = requestAnimationFrame(tick);
      else {
        show();
        playing = null;
        if (then) then();
      }
    };
    if (playing) cancelAnimationFrame(playing);
    playing = requestAnimationFrame(tick);
  }

  function setStage(index) {
    const i = Math.max(0, Math.min(stages.length - 1, index));
    stop();
    travel(i);
  }

  function play() {
    if (button.getAttribute("aria-pressed") === "true") return stop();
    button.textContent = words.pause;
    button.setAttribute("aria-pressed", "true");
    let i = state.pos === stages[state.stage].at ? state.stage + 1 : state.stage;
    if (i === stages.length) {
      state.pos = 0;
      state.stage = 0;
      place();
      show();
      i = 1;
    }
    const rest = reduced() ? 1800 : 1500;
    const next = () => {
      if (button.getAttribute("aria-pressed") !== "true") return;
      if (i >= stages.length) return stop();
      travel(i, () => {
        i += 1;
        timer = setTimeout(next, rest);
      });
    };
    timer = setTimeout(next, 500);
  }

  const button = document.getElementById("path-play");
  button.addEventListener("click", play);
  document.getElementById("path-prev").addEventListener("click", () => setStage(state.stage - 1));
  document.getElementById("path-next").addEventListener("click", () => setStage(state.stage + 1));
  const toggle = segmented(document.getElementById("path-colour"), (value) => {
    state.colour = value;
    figure.dataset.colour = value;
    colour();
  });
  toggle.set("count");
  figure.dataset.colour = "count";

  const viewControls = document.getElementById("path-view");
  if (viewControls && path.stops.every((s) => widths.every((w) => s.curves[w].z?.length === s.curves[w].x.length))) {
    const reset = document.getElementById("path-reset");
    const turn = (horizontal, vertical) => {
      yaw = horizontal;
      pitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, vertical));
      const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      camera = [[cy, 0, sy], [-sy * sp, cp, cy * sp]];
      reset.disabled = yaw === 0 && pitch === 0;
      if (nodes) {
        fitCamera();
        place();
      }
    };
    viewControls.hidden = false;
    box.classList.add("rotatable");
    box.tabIndex = 0;
    let drag = null;
    box.addEventListener("pointerdown", (event) => {
      if (!event.isPrimary || event.button !== 0 || drag) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY, yaw, pitch };
      box.setPointerCapture(event.pointerId);
      box.classList.add("dragging");
    });
    box.addEventListener("pointermove", (event) => {
      if (drag?.id !== event.pointerId) return;
      const radiansPerPixel = Math.PI / Math.max(240, width);
      turn(drag.yaw + (event.clientX - drag.x) * radiansPerPixel, drag.pitch - (event.clientY - drag.y) * radiansPerPixel);
    });
    box.addEventListener("lostpointercapture", (event) => {
      if (drag?.id === event.pointerId) {
        drag = null;
        box.classList.remove("dragging");
      }
    });
    box.addEventListener("keydown", (event) => {
      const step = Math.PI / 18;
      switch (event.key) {
        case "ArrowLeft": turn(yaw - step, pitch); break;
        case "ArrowRight": turn(yaw + step, pitch); break;
        case "ArrowUp": turn(yaw, pitch + step); break;
        case "ArrowDown": turn(yaw, pitch - step); break;
        case "Home": turn(0, 0); break;
        default: return;
      }
      event.preventDefault();
    });
    reset.addEventListener("click", () => turn(0, 0));
  }

  // the story beside the figure: selecting a paragraph shows its stage; on a wide screen the paragraph at the middle of the
  // window does the same while the reader scrolls (the page is never scrolled by the script)
  const steps = [...document.querySelectorAll("#story .story-step")];
  const stageOf = (el) => stages.findIndex((s) => s.key === el.dataset.stage);
  for (const step of steps) {
    step.addEventListener("click", () => setStage(stageOf(step)));
    step.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        setStage(stageOf(step));
      }
    });
  }
  if ("IntersectionObserver" in window) {
    const wide = window.matchMedia("(min-width: 1001px)");
    const observer = new IntersectionObserver(
      (entries) => {
        if (!wide.matches || button.getAttribute("aria-pressed") === "true") return;
        for (const entry of entries) if (entry.isIntersecting && stageOf(entry.target) !== state.stage) setStage(stageOf(entry.target));
      },
      { rootMargin: "-46% 0px -46% 0px" },
    );
    for (const step of steps) observer.observe(step);
  }

  figure.classList.add("live");
  figure.jump = (index) => {
    // for checks: stand at a stage at once
    stop();
    state.stage = index;
    state.pos = stages[index].at;
    place();
    show();
  };
  figure.at = (pos) => {
    state.pos = pos;
    place();
    show();
  };
  onResize(box, (w) => {
    width = w;
    build();
  });
  show();
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
    ["inside", "series inside", words.lineInside],
    ["rest", "series outside", words.lineRest],
    ["state", "series state-edit", words.lineState],
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
    root.append(svg("path", { d: `M${M.l} ${y(Number(words.level))}H${width - M.r}`, class: "margin-level" }));
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
