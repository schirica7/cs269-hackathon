"""Run the evaluator agents (isolated + criteria modes) on all outputs so E2 is instant later (results are cached on disk)."""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evalgen import pipeline, grader, criteria, llm
for name in ["medical", "product"]:
    outs = pipeline.load_outputs(name, "haiku")
    for model in ["haiku", "sonnet", "opus"]:
        for mode in ["isolated", "criteria"]:
            g = grader.grade_many(pipeline.PROMPTS[name], outs, model=model, mode=mode, criteria=criteria.PAPER_CRITERIA[name], workers=10)
            bad = sum(1 for v in g.values() if v["grade"] == 0); err = sum(1 for v in g.values() if v["grade"] is None)
            print(f"{name} {model}/{mode}: bad={bad}/{len(g)} errors={err}  cost so far ${llm.STATS['cost_usd']:.2f}", flush=True)
