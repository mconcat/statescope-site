// Token-level text: one span per token, set in the mono face so that one character is one unit of the horizontal axis.
// The markup is the one tools/build_page.py writes for the first figure:
//   .ttext[style=--w:<wrapping width>] > .ruler, .tline* ; .tline > .tok[.a][.b][.c][.nl][.u][.last]* , .count
// a, b, c: the gate of L8 transform 189, L9 transform 410, L9 transform 1749 is open at that token (from the item files).
import { h, clear, showTip, hideTip } from "./svg.js";

// token indices of each line; a line-break token closes its line
export function tokenLines(pieces) {
  const lines = [[]];
  pieces.forEach((piece, i) => {
    lines[lines.length - 1].push(i);
    if (piece === "\n") lines.push([]);
  });
  return lines.filter((line) => line.length);
}

// characters in the line up to and including each token (a line-break token has 0), as the demonstration script counts them
function counts(pieces) {
  let n = 0;
  return pieces.map((piece) => (n = piece === "\n" ? 0 : n + piece.length));
}

// options: { width, units: [a, b, c] names in item.gate, tail: number of last lines or 0 for all, kind: "clean" | "corrupt" }
export function renderText(box, item, options) {
  const { width, units, tail, kind } = options;
  const pieces = item[kind];
  const clean = kind === "clean";
  const chars = clean ? item.chars : counts(pieces);
  const all = tokenLines(pieces);
  const lines = tail ? all.slice(-tail) : all;
  const last = pieces.length - 1;
  let seenBreak = lines[0][0] > 0 && pieces[lines[0][0] - 1] === "\n";
  const widest = Math.max(width, ...lines.map((line) => line.reduce((n, i) => n + (pieces[i] === "\n" ? 0 : pieces[i].length), 0)));

  const text = h("div", { class: `ttext interactive ${kind}`, style: `--w:${width}` });
  const ruler = h("div", { class: "ruler", "aria-hidden": "true" });
  for (let x = 0; x <= widest; x += 20) ruler.append(h("span", { style: `--at:${x}`, text: String(x) }));
  text.append(ruler);
  for (const line of lines) {
    const row = h("div", { class: "tline" });
    for (const i of line) {
      const cls = ["tok"];
      if (clean) {
        units.forEach((unit, k) => item.gate[unit][i] === "1" && cls.push("abc"[k]));
        if (item.known[i] === "0") cls.push("u");
      } else {
        cls.push("plain");
        if (!seenBreak) cls.push("u");
      }
      if (pieces[i] === "\n") cls.push("nl");
      if (i === last) cls.push("last");
      row.append(h("span", { class: cls.join(" "), "data-i": i, "data-c": chars[i], text: pieces[i] === "\n" ? "⏎" : pieces[i] }));
    }
    const end = pieces[line[line.length - 1]] === "\n" ? line[line.length - 2] : line[line.length - 1];
    const known = clean ? item.known[end] === "1" : seenBreak;
    if (end !== undefined && known) row.append(h("span", { class: "count", "aria-hidden": "true", text: String(chars[end]) }));
    if (pieces[line[line.length - 1]] === "\n") seenBreak = true;
    text.append(row);
  }
  clear(box).append(text);
  box.dataset.tokens = String(lines.reduce((n, line) => n + line.length, 0));
  // keep the last token, where the margin is read, in view
  const lastTok = text.querySelector(".tok.last");
  if (lastTok && box.scrollWidth > box.clientWidth) {
    box.scrollLeft = Math.max(0, lastTok.offsetLeft + lastTok.offsetWidth - box.clientWidth + 48);
  }
  return text;
}

// a hint on each token: what it is, how many characters the line holds after it, and which gates are open
export function tokenHints(root, names) {
  root.addEventListener("pointermove", (event) => {
    const tok = event.target.closest?.(".tok");
    if (!tok || !root.contains(tok)) return hideTip();
    showTip(event, (tip) => {
      const piece = tok.classList.contains("nl") ? "line break" : JSON.stringify(tok.textContent);
      tip.append(h("div", { class: "t", text: piece }));
      if (tok.classList.contains("u")) {
        tip.append(h("div", { text: "Before the first line break of the text: the number of characters in this line is not known." }));
      } else if (!tok.classList.contains("nl")) {
        tip.append(h("div", {}, "The line holds ", h("b", { text: tok.dataset.c }), " characters up to this token."));
      }
      if (!tok.classList.contains("plain")) {
        const on = names.filter((_, k) => tok.classList.contains("abc"[k]));
        tip.append(h("div", { text: on.length ? `On: ${on.join(", ")}.` : "None of the three transforms is on." }));
      }
      if (tok.classList.contains("last")) tip.append(h("div", { text: "Last token: the margin is read here." }));
    });
  });
  root.addEventListener("pointerleave", hideTip);
}

// the real width of one character of the token text, for the ruler, the wrapping rule and the chart below the first figure
export function measureCharacter() {
  const probe = h("span", { class: "ttext", style: "position:absolute;visibility:hidden;min-width:0", text: "0".repeat(100) });
  document.body.append(probe);
  const width = probe.getBoundingClientRect().width / 100;
  probe.remove();
  if (width > 0) document.documentElement.style.setProperty("--cw", `${width}px`);
  return width;
}
