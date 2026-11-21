import { h, svg } from "./svg.js";

// One Unicode code point is one measured character, including when a fallback
// typeface would give its glyph more or less space than a Latin mono character.
function ruledText(text) {
  return Array.from(text.matchAll(/[\x00-\x7f]+|[^\x00-\x7f]+/gu), ([run]) =>
    run.codePointAt(0) < 128 ? run : svg("svg", { class: "text-run", width: `${[...run].length}ch`, height: "1.4em" },
      svg("text", { y: "1em", textLength: "100%", lengthAdjust: "spacingAndGlyphs" }, run)));
}

export function initGeneratedLines({ examples, rows }) {
  const baseline = document.getElementById("line-baseline");
  const comparison = document.getElementById("line-comparison");
  const tablist = document.getElementById("line-tabs");
  const tabs = [...tablist.querySelectorAll("button")];
  const prev = document.getElementById("line-prev");
  const next = document.getElementById("line-next");
  let index = 0;

  function render(block, arm) {
    const doc = examples[index];
    const lines = doc.text[arm].split("\n");
    const label = rows[arm].label;
    block.dataset.arm = arm;
    block.querySelector("h5").textContent = label;
    block.querySelector(".prompt-end").textContent = doc.prompt_ends[arm === "ref:40" ? "40" : "100"];
    block.querySelector(".sample-text").replaceChildren(...lines.map((line, i) =>
      h("span", { class: i === lines.length - 1 ? "unfinished" : null }, i ? "\n" : "", ...ruledText(line))));
    block.querySelector(".line-toggle input").checked = false;
    const scroll = block.querySelector(".text-scroll");
    scroll.setAttribute("aria-label", label + " continuation");
    scroll.scrollLeft = 0;
  }

  function show(i) {
    index = i;
    render(baseline, "none");
    render(comparison, comparison.dataset.arm);
    document.getElementById("line-document").textContent = i + 1;
    document.getElementById("line-corpus").textContent = examples[i].corpus_line;
    prev.disabled = i === 0;
    next.disabled = i === examples.length - 1;
  }

  function select(tab) {
    for (const item of tabs) {
      item.setAttribute("aria-selected", String(item === tab));
      item.tabIndex = item === tab ? 0 : -1;
    }
    comparison.setAttribute("aria-labelledby", tab.id);
    if (comparison.dataset.arm !== tab.dataset.arm) render(comparison, tab.dataset.arm);
  }
  for (const [i, tab] of tabs.entries()) {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      const target = {
        ArrowLeft: tabs[(i + tabs.length - 1) % tabs.length],
        ArrowRight: tabs[(i + 1) % tabs.length],
        Home: tabs[0],
        End: tabs[tabs.length - 1],
      }[event.key];
      if (!target) return;
      event.preventDefault();
      select(target);
      target.focus();
    });
  }
  comparison.setAttribute("role", "tabpanel");
  select(tablist.querySelector('[aria-selected="true"]'));
  tablist.hidden = false;
  prev.addEventListener("click", () => show(index - 1));
  next.addEventListener("click", () => show(index + 1));
  document.getElementById("line-stepper").hidden = false;
}
