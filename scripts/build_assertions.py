"""Synthesize (opus) and execute (code / haiku grader) candidate assertions for a pipeline's outputs."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evalgen import pipeline, criteria, assertions, llm
name, gen = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "haiku")
p = pipeline.outputs_path(name, gen)
while not p.exists(): time.sleep(5)
outs = pipeline.load_outputs(name, gen)
b = assertions.build(name, gen, criteria.PAPER_CRITERIA[name], outs, pipeline.PROMPTS[name], synth_model="opus", grader_model="haiku", k=3, label="paper")
print(json.dumps({c["id"]: {"type": c["type"], "name": c["name"], "selectivity": round(sum(v for v in b["results"][c["id"]].values() if v) / max(1, len([v for v in b["results"][c["id"]].values() if v is not None])), 3),
       "errors": sum(v is None for v in b["results"][c["id"]].values())} for c in b["candidates"]}, indent=1))
print("cost", llm.STATS)
