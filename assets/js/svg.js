// Small helpers for hand-written SVG charts and DOM building. No dependencies.
const NS = "http://www.w3.org/2000/svg";

export function svg(name, attrs = {}, ...children) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

export function h(name, attrs = {}, ...children) {
  const node = document.createElement(name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "text") node.textContent = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  node.append(...children);
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function linear(d0, d1, r0, r1) {
  return (x) => r0 + ((x - d0) / (d1 - d0)) * (r1 - r0);
}

// "nice" axis ticks between lo and hi (inclusive), about `count` of them; returns { ticks, step, lo, hi }
export function niceTicks(lo, hi, count = 4) {
  const span = hi - lo || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 0.5) || 10 * mag;
  const first = Math.floor(lo / step + 1e-9) * step;
  const last = Math.ceil(hi / step - 1e-9) * step;
  const ticks = [];
  for (let v = first; v <= last + step * 1e-6; v += step) ticks.push(Math.abs(v) < step * 1e-6 ? 0 : v);
  return { ticks, step, lo: first, hi: last };
}

// axis tick text only; every data value on the page is a string written by tools/build_data.py
export function tickText(v, step) {
  const digits = step >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(step) - 1e-9) + (String(step).includes("25") ? 1 : 0));
  return v.toFixed(digits);
}

// call render(width) now and whenever the container's width changes
export function onResize(container, render) {
  let last = -1;
  const run = () => {
    const w = Math.floor(container.clientWidth);
    if (w > 0 && w !== last) {
      last = w;
      render(w);
    }
  };
  new ResizeObserver(run).observe(container);
  run();
  return () => {
    last = -1;
    run();
  };
}

export function diamond(cx, cy, r) {
  return `M${cx} ${cy - r}L${cx + r} ${cy}L${cx} ${cy + r}L${cx - r} ${cy}z`;
}

const tip = () => document.getElementById("tip");

export function showTip(event, build) {
  const node = tip();
  clear(node);
  build(node);
  node.hidden = false;
  const pad = 14;
  const rect = node.getBoundingClientRect();
  let x = event.pageX + pad;
  let y = event.pageY + pad;
  const maxX = window.scrollX + document.documentElement.clientWidth - rect.width - 8;
  if (x > maxX) x = Math.max(window.scrollX + 8, event.pageX - rect.width - pad);
  node.style.left = `${x}px`;
  node.style.top = `${y}px`;
}

export function hideTip() {
  tip().hidden = true;
}

// a group of buttons where exactly one is pressed
export function segmented(container, onChange) {
  const buttons = () => [...container.querySelectorAll("button")];
  container.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !container.contains(button)) return;
    set(button.dataset.value);
    onChange(button.dataset.value);
  });
  function set(value) {
    for (const b of buttons()) b.setAttribute("aria-pressed", String(b.dataset.value === value));
  }
  return { set };
}
