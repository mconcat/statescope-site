// Entry point. Loads the generated data files (relative URLs) and starts each interactive figure.
// Every value shown comes from data/*.json, which tools/build_data.py writes from the repository's files.
import { initLayers, initFourB } from "./layers.js";
import { initDemo } from "./demo.js";
import { measureCharacter } from "./tokens.js";

async function load(name) {
  const response = await fetch(`data/${name}`);
  if (!response.ok) throw new Error(`data/${name}: ${response.status}`);
  return response.json();
}

function fail(id, error) {
  const box = document.getElementById(id);
  if (box) {
    box.hidden = false;
    box.textContent = `The data for this figure could not be loaded (${error.message}). The tables on this page still hold the numbers.`;
  }
  console.error(error);
}

// the token text is drawn on a scale of one character; measure that character once the mono face is there
measureCharacter();
document.fonts?.ready.then(measureCharacter);

// a "Copy" button on each code block
for (const block of document.querySelectorAll(".codeblock")) {
  if (!navigator.clipboard) break;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(block.querySelector("code").textContent);
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = "Copy"), 1600);
  });
  block.querySelector(".lang").append(button);
}

Promise.all([load("layers.json"), load("splice.json")])
  .then(([layers, splice]) => initLayers(layers, splice))
  .catch((error) => fail("load-error-layers", error));

load("demo.json")
  .then((demo) => initDemo(demo, load))
  .catch((error) => fail("load-error-demo", error));

// Optional sections. tools/build_page.py writes their markup only when their data file exists, so nothing is fetched otherwise.
if (document.getElementById("fig-lengths")) {
  Promise.all([import("./generated-lines.js"), load("generated-lines.json")])
    .then(([module, data]) => module.initGeneratedLines(data))
    .catch((error) => console.error(error));
}
if (document.getElementById("fig-4b")) {
  load("layers-4b.json")
    .then(initFourB)
    .catch((error) => console.error(error));
}
if (document.getElementById("fig-steer")) {
  // "Steering one unit by a dose": data/steer.json
  Promise.all([import("./steer.js"), load("steer.json")])
    .then(([module, steer]) => module.initSteer(steer))
    .catch((error) => console.error(error));
}
if (document.getElementById("fig-curve")) {
  // the count as a curve inside one group's frame, and how two transforms read it: data/count-curve.json, data/count-readout.json
  Promise.all([import("./curve.js"), load("count-curve.json"), load("count-readout.json")])
    .then(([module, curve, readout]) => module.initCurve(curve, readout))
    .catch((error) => console.error(error));
}
if (document.getElementById("fig-path")) {
  // the path of the count through the layers (animated) and the causal test at layer 12: data/trace.json
  Promise.all([import("./path.js"), load("trace.json")])
    .then(([module, trace]) => {
      module.initPath(trace);
      module.initCausal(trace);
    })
    .catch((error) => console.error(error));
}
if (document.getElementById("fig-aba")) {
  // three planes inside state-group frames of the 4B set: data/geom-4b.json
  Promise.all([import("./geom4b.js"), load("geom-4b.json")])
    .then(([module, geom]) => module.initGeom(geom))
    .catch((error) => console.error(error));
}
