// Check that the browser demo's EvalGen logic reproduces the offline experiment.
// Feeds the reference grades through the page's own sampler and selection, then compares with results/e1_*.json.
// Usage: node scripts/check_demo.mjs
import { readFileSync } from "node:fs";
const html = readFileSync(new URL("../demo/evalgen-live.html", import.meta.url), "utf8");
const data = JSON.parse(html.match(/<script id="eg-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const core = html.match(/<script id="eg-core">([\s\S]*?)<\/script>/)[1];
globalThis.window = globalThis;
new Function(core)();
const runs = [["medical", "paper", "e1_medical.json"], ["product", "paper", "e1_product.json"], ["product", "gradefirst", "e1_product_gradefirst.json"]];
let ok = true;
for (const [p, k, file] of runs) {
  const pipe = data.pipes[p], set = pipe.sets[k], ids = pipe.outputs.map(o => o.id);
  const off = JSON.parse(readFileSync(new URL(`../results/${file}`, import.meta.url), "utf8")).evalgen_16;
  const graded = new Set(), gm = new Map(), sampled = [];
  for (let step = 0; step < 16; step++) { const i = EG.next(set, ids, graded, graded.size % 2); graded.add(i); gm.set(i, pipe.outputs[i].exp); sampled.push(ids[i]); }
  const sel = EG.select(set, gm, pipe.thr);
  const m = EG.metrics(set, sel.chosen, new Map(pipe.outputs.map((o, i) => [i, o.exp])));
  const same = JSON.stringify(sampled) === JSON.stringify(off.sampled) && JSON.stringify(sel.chosen) === JSON.stringify(off.chosen) && Math.abs(m.alignment - off.alignment) < 1e-9;
  ok &&= same;
  console.log(`${same ? "MATCH" : "DIFF "} ${p}/${k}: alignment ${(100 * m.alignment).toFixed(1)}% vs offline ${(100 * off.alignment).toFixed(1)}%, checks ${sel.chosen.join(",")}`);
}
process.exit(ok ? 0 : 1);
