"""Evaluator agents: an LLM standing in for the human grader of EvalGen's Grade screen.

Modes
  isolated   - each output graded in its own call (the standard 'LLM-as-judge' agent)
  criteria   - same, but the agent is given the explicit criteria list
  sequential - the agent sees its own previous outputs+verdicts (tests whether an LLM grader 'drifts' like humans did)
"""
from __future__ import annotations
import json
from . import llm

GRADE_SCHEMA = {"type": "object", "properties": {"good": {"type": "boolean"}, "feedback": {"type": "string"}},
                "required": ["good", "feedback"], "additionalProperties": False}

SYSTEM = ("You are the evaluator agent in a two-agent LLM pipeline. A separate programmer agent produced a response to a "
          "prompt. Your job is to grade that response as a careful human developer would: thumbs-up (good) if it fully "
          "satisfies the prompt's instructions and would be acceptable to ship, thumbs-down (bad) otherwise. Give one short "
          "sentence of feedback explaining the main problem when the grade is bad.")

def _body(pipeline_prompt: str, vars: dict, output: str) -> str:
    return (f"PROMPT TEMPLATE:\n```\n{pipeline_prompt}\n```\n\nINPUT VARIABLES:\n```\n{json.dumps(vars)[:9000]}\n```\n\n"
            f"RESPONSE TO GRADE:\n```\n{output}\n```")

def grade_many(pipeline_prompt: str, outputs: list[dict], model: str = "sonnet", mode: str = "isolated",
               criteria: list[dict] | None = None, history_k: int = 8, workers: int = 8) -> dict:
    """Returns {output_id: {"grade": 1/0, "feedback": str}}"""
    crit_txt = ""
    if mode == "criteria" and criteria:
        crit_txt = "\n\nThe developer cares about these criteria (a response is good only if it satisfies all of them):\n" + \
                   "\n".join(f"- {c['title']}: {c['description']}" for c in criteria)
    if mode in ("isolated", "criteria"):
        jobs = [{"prompt": _body(pipeline_prompt, o["vars"], o["output"]) + crit_txt + "\n\nGrade this response.",
                 "system": SYSTEM, "model": model, "schema": GRADE_SCHEMA, "tag": f"grader-{mode}"} for o in outputs]
        res = llm.complete_many(jobs, workers=workers, desc=f"grader {model}/{mode}")
        return {o["id"]: {"grade": int(bool(r["structured"]["good"])), "feedback": r["structured"]["feedback"]} if r.get("structured")
                else {"grade": None, "feedback": r.get("error", "")} for o, r in zip(outputs, res)}
    # sequential: carry the agent's own recent verdicts forward, like a human grading one after another
    out, hist = {}, []
    for o in outputs:
        h = ""
        if hist:
            h = "\n\nYou have already graded these responses in this session (most recent last):\n" + "\n".join(
                f"--- RESPONSE {i+1} ({'GOOD' if g['grade'] else 'BAD'}; feedback: {g['feedback']}):\n{g['output'][:700]}" for i, g in enumerate(hist[-history_k:]))
            h += "\n\nStay consistent with your previous verdicts where appropriate."
        r = llm.complete(_body(pipeline_prompt, o["vars"], o["output"]) + h + "\n\nGrade this response.", system=SYSTEM,
                         model=model, schema=GRADE_SCHEMA, tag="grader-sequential")
        g = {"grade": int(bool(r["structured"]["good"])), "feedback": r["structured"]["feedback"]}
        out[o["id"]] = g; hist.append({**g, "output": o["output"]})
    return out
