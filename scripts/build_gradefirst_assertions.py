"""Second EvalGen iteration for the product pipeline: implement the criteria suggested via the Grade First path."""
import sys, json; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evalgen import pipeline, assertions, llm
name = sys.argv[1] if len(sys.argv) > 1 else "product"
crits = json.load(open(f"results/criteria_{name}.json"))["grade_first"]
for i, c in enumerate(crits): c["id"] = f"g{i+1}"
outs = pipeline.load_outputs(name, "haiku")
b = assertions.build(name, "haiku", crits, outs, pipeline.PROMPTS[name], synth_model="opus", grader_model="haiku", k=3, label="gradefirst")
print("done", len(b["candidates"]), "candidates; cost", llm.STATS)
