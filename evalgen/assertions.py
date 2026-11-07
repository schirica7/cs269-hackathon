"""Candidate Assertion Synthesis and Execution (paper Sec 4.1).

For each criterion one LLM call produces several candidate implementations: Python functions
(`def evaluate(output: str, inputs: dict) -> bool`) or LLM grader prompts that output true/false.
Candidates are executed on every pipeline output; results are 1 (pass), 0 (fail) or None (error).
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import llm

ROOT = Path(__file__).resolve().parent.parent

CODE_SCHEMA = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
    "name": {"type": "string"}, "code": {"type": "string"}}, "required": ["name", "code"], "additionalProperties": False}}},
    "required": ["candidates"], "additionalProperties": False}
PROMPT_SCHEMA = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
    "name": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "prompt"], "additionalProperties": False}}},
    "required": ["candidates"], "additionalProperties": False}
GRADE_SCHEMA = {"type": "object", "properties": {"pass": {"type": "boolean"}, "reason": {"type": "string"}},
                "required": ["pass", "reason"], "additionalProperties": False}

SYNTH_SYSTEM = "You are an expert Python developer and prompt engineer who writes evaluation functions for LLM pipeline outputs."

def synthesize(criterion: dict, pipeline_prompt: str, example_outputs: list[str], model: str = "opus", k: int = 3) -> list[dict]:
    ex = "\n\n".join(f"EXAMPLE OUTPUT {i+1}:\n{o[:1200]}" for i, o in enumerate(example_outputs[:3]))
    base = (f"The prompt template under test is:\n```\n{pipeline_prompt}\n```\n\nSome example outputs:\n{ex}\n\n"
            f"Criterion: {criterion['title']}\nDescription: {criterion['description']}\n\n")
    if criterion["eval_type"] == "code":
        prompt = base + (f"Write {k} different candidate Python implementations of this criterion, each with a different, "
            "reasonable interpretation (e.g. stricter vs. looser thresholds, regex vs. parsing). Each must define "
            "`def evaluate(output: str, inputs: dict) -> bool` returning True if the output PASSES the criterion. Use only "
            "the standard library (re, json, string, etc.). No I/O, no network, no imports beyond the standard library.")
        r = llm.complete(prompt, system=SYNTH_SYSTEM, model=model, schema=CODE_SCHEMA, tag="synth")
        return [{"type": "code", "name": c["name"], "code": c["code"]} for c in r["structured"]["candidates"][:k]]
    prompt = base + (f"Write {k} different candidate LLM grader prompts for this criterion, each with a different reasonable "
        "interpretation or level of strictness. Each prompt must contain the literal placeholder {output} where the response "
        "to be judged will be inserted (and may contain {inputs} for the pipeline inputs). The grader will answer with a "
        "JSON object {\"pass\": true|false, \"reason\": ...}; tell it that pass=true means the output satisfies the criterion.")
    r = llm.complete(prompt, system=SYNTH_SYSTEM, model=model, schema=PROMPT_SCHEMA, tag="synth")
    return [{"type": "llm", "name": c["name"], "prompt": c["prompt"]} for c in r["structured"]["candidates"][:k]]

_RUNNER = r'''
import json, sys
payload = json.loads(sys.stdin.read())
ns = {}
exec(payload["code"], ns)
res = ns["evaluate"](payload["output"], payload["inputs"])
print(json.dumps({"pass": bool(res)}))
'''

def run_code(code: str, output: str, inputs: dict, timeout: float = 10.0):
    try:
        p = subprocess.run([sys.executable, "-I", "-c", _RUNNER], input=json.dumps({"code": code, "output": output, "inputs": inputs}),
                           capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
        if p.returncode != 0: return None
        return 1 if json.loads(p.stdout.strip().splitlines()[-1])["pass"] else 0
    except Exception:  # noqa: BLE001
        return None

def run_llm_grader(prompt_tpl: str, output: str, inputs: dict, model: str = "haiku"):
    try:
        prompt = prompt_tpl.replace("{output}", output).replace("{inputs}", json.dumps(inputs)[:6000])
    except Exception:  # noqa: BLE001
        prompt = prompt_tpl + "\n\nOUTPUT:\n" + output
    try:
        r = llm.complete(prompt, system="You are a careful evaluator. Judge only what is asked and answer in the required JSON format.",
                         model=model, schema=GRADE_SCHEMA, tag="assert")
        return 1 if r["structured"]["pass"] else 0
    except Exception:  # noqa: BLE001
        return None

def execute(candidates: list[dict], outputs: list[dict], grader_model: str = "haiku", workers: int = 8) -> dict:
    """results[candidate_id][output_id] -> 1/0/None"""
    results = {c["id"]: {} for c in candidates}
    def job(c, o):
        if c["type"] == "code": return c["id"], o["id"], run_code(c["code"], o["output"], o["vars"])
        return c["id"], o["id"], run_llm_grader(c["prompt"], o["output"], o["vars"], grader_model)
    jobs = [(c, o) for c in candidates for o in outputs]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (cid, oid, val) in enumerate(ex.map(lambda a: job(*a), jobs), 1):
            results[cid][oid] = val
            if n % 50 == 0 or n == len(jobs): print(f"  [execute] {n}/{len(jobs)}", file=sys.stderr, flush=True)
    return results

def build(pipeline: str, gen_model: str, criteria: list[dict], outputs: list[dict], pipeline_prompt: str,
          synth_model: str = "opus", grader_model: str = "haiku", k: int = 3, label: str = "paper") -> dict:
    path = ROOT / "data" / "assertions" / f"{pipeline}__{gen_model}__{label}.json"
    if path.exists():
        return json.loads(path.read_text())
    cands = []
    for c in criteria:
        for j, cand in enumerate(synthesize(c, pipeline_prompt, [o["output"] for o in outputs[:3]], model=synth_model, k=k)):
            cands.append({"id": f"{c['id']}_{j+1}", "criterion_id": c["id"], **cand})
        print(f"  synthesized {c['id']} ({c['eval_type']})", file=sys.stderr, flush=True)
    results = execute(cands, outputs, grader_model=grader_model)
    bundle = {"pipeline": pipeline, "gen_model": gen_model, "criteria": criteria, "candidates": cands, "results": results,
              "synth_model": synth_model, "grader_model": grader_model}
    path.write_text(json.dumps(bundle, indent=1))
    return bundle
