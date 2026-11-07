"""Build demo/evalgen-live.html: the browser-only EvalGen grading demo, with every cached result embedded."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def jl(p): return [json.loads(l) for l in (ROOT / p).read_text().splitlines() if l.strip()]

AGENTS = [(f"{m}/{mode}", f"{m.capitalize()} 5.5 · {'prompt only' if mode == 'isolated' else 'with criteria'}", m[0].upper() + ("+" if mode == "criteria" else ""))
          for m in ["haiku", "sonnet", "opus"] for mode in ["isolated", "criteria"]]
PIPES = {
 "medical": {"label": "Medical notes", "thr": 0.10, "inputLabel": "Visit transcript",
   "blurb": "Doctor and patient visit transcripts summarized into six fields, with no personal details, in about 150 words. 84 outputs from Claude Haiku 5.5."},
 "product": {"label": "Product copy", "thr": 0.40, "inputLabel": "Product details and customer reviews",
   "blurb": "SEO product descriptions for beauty products, written from listings and reviews, with no weaknesses mentioned, in about 200 words. 100 outputs from Claude Haiku 5.5."},
}
SETS = {"paper": ("2024 paper criteria", "The criteria the authors used in the paper's offline evaluation."),
        "gradefirst": ("Grade First criteria", "Criteria Claude Opus 5.5 suggested after reading 8 graded bad outputs and their notes.")}

import sys; sys.path.insert(0, str(ROOT))
from evalgen.pipeline import PROMPTS
data = {"pipes": {}, "agents": [{"key": k, "label": l, "short": s} for k, l, s in AGENTS]}
for p, meta in PIPES.items():
    outs = jl(f"data/outputs/{p}__haiku.jsonl")
    ref = {r["id"]: r for r in jl(f"data/grades/{p}__haiku__expert.jsonl")}
    ag = {k: {r["id"]: r.get("grade") for r in jl(f"data/grades/{p}__haiku__agent-{k.replace('/', '-')}.jsonl")} for k, _, _ in AGENTS}
    ids = [o["id"] for o in outs]
    rows = [{"id": o["id"], "out": o["output"], "inp": next(iter(o["vars"].values())), "exp": ref[o["id"]]["grade"],
             "expf": ref[o["id"]].get("feedback", ""), "ag": {k: ag[k].get(o["id"]) for k, _, _ in AGENTS}} for o in outs]
    sets = {}
    for label in ["paper", "gradefirst"]:
        f = ROOT / "data" / "assertions" / f"{p}__haiku__{label}.json"
        if not f.exists(): continue
        b = json.loads(f.read_text())
        sets[label] = {"label": SETS[label][0], "blurb": SETS[label][1],
                       "criteria": [{"id": c["id"], "title": c["title"], "description": c["description"], "type": c["eval_type"]} for c in b["criteria"]],
                       "cands": [{"id": c["id"], "crit": c["criterion_id"], "type": c["type"], "name": c["name"], "body": c.get("code") or c.get("prompt", "")} for c in b["candidates"]],
                       "res": {c["id"]: [b["results"][c["id"]].get(i) for i in ids] for c in b["candidates"]}}
    data["pipes"][p] = {**meta, "prompt": PROMPTS[p], "outputs": rows, "sets": sets}

payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
html = (ROOT / "demo" / "template.html").read_text().replace("/*__DATA__*/", payload)
(ROOT / "demo" / "evalgen-live.html").write_text(html)
print(f"wrote demo/evalgen-live.html ({len(html)/1e6:.2f} MB)")
