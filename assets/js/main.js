// Entry point. Loads the generated data files (relative URLs) and starts each interactive view.
// Every value shown comes from data/*.json, which tools/build_data.py writes from the repository's files.
import { initLayers } from "./layers.js";
import { initDemo } from "./demo.js";

async function load(name) {
  const response = await fetch(`data/${name}`);
  if (!response.ok) throw new Error(`data/${name}: ${response.status}`);
  return response.json();
}

function fail(id, error) {
  const box = document.getElementById(id);
  if (box) {
    box.hidden = false;
    box.textContent = `The data for this view could not be loaded (${error.message}). The tables on this page still hold the numbers.`;
  }
  console.error(error);
}

// "Show the table" buttons
for (const button of document.querySelectorAll("[data-toggle]")) {
  const target = document.getElementById(button.dataset.toggle);
  button.addEventListener("click", () => {
    const open = target.classList.toggle("open");
    button.setAttribute("aria-expanded", String(open));
    button.textContent = open ? "Hide the table" : "Show the table";
    target.dispatchEvent(new CustomEvent("toggle-open", { detail: open }));
  });
}

// mark the section in view in the bar
const links = [...document.querySelectorAll(".section-nav a")];
const byId = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
const seen = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      for (const a of links) a.removeAttribute("aria-current");
      byId.get(entry.target.id)?.setAttribute("aria-current", "true");
    }
  },
  { rootMargin: "-45% 0px -50% 0px" },
);
for (const id of byId.keys()) seen.observe(document.getElementById(id));

Promise.all([load("layers.json"), load("splice.json")])
  .then(([layers, splice]) => initLayers(layers, splice))
  .catch((error) => fail("load-error-layers", error));

load("demo.json")
  .then((demo) => initDemo(demo, load))
  .catch((error) => fail("load-error-demo", error));

// ------------------------------------------------------------------------------------------------ SLOT (empty on purpose)
// "Steering one unit by a dose": a slider over a strength alpha with precomputed margins from data/steer.json.
// When that file and its section in tools/page.template.html exist, add assets/js/steer.js and start it here:
//
//   import { initSteer } from "./steer.js";
//   load("steer.json").then(initSteer).catch((error) => fail("load-error-steer", error));
//
// Until then nothing is fetched and nothing is rendered.
// ------------------------------------------------------------------------------------------------

// ------------------------------------------------------------------------------------------------ SLOT (empty on purpose)
// "Qwen3.5-4B set": a later section with its own data files (for example data/layers-4b.json, written by a tools/ script).
// initLayers() takes its rows as an argument, so the same panels can be reused for a second set.
// Until then nothing is fetched and nothing is rendered.
// ------------------------------------------------------------------------------------------------
