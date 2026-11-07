"""The two 'prompts under test' from Appendix B of the paper, run over the datasets."""
from __future__ import annotations
import json, sys
from pathlib import Path
from . import llm

ROOT = Path(__file__).resolve().parent.parent

PROMPTS = {
 "medical": ("You are extracting insights from some medical records. The records contain a medical note and a dialogue "
  "between a doctor and a patient. You need to extract values for the following: Chief complaint, History of present "
  "illness, Physical examination, Symptoms experienced by the patient, New medications prescribed or changed, including "
  "dosages (N/A if not provided), and Follow-up instructions (N/A if not provided). Your answer should not include any "
  "personal identifiable information (PII) such as name, age, gender, or ID. Use \"the patient\" instead of their name, "
  "for example. Return your answer as a bullet list, where each bullet is formatted like `chief complaint: xx.` If there "
  "is no value for the key, the value should be `N/A`. Keep your response around 150 words (you may have to summarize "
  "some extracted values to stay within the word limit).\n\n{transcript}"),
 "product": ("You are an expert copywriter. You need to write an e-commerce product description based on the product "
  "details and customer reviews. Your description should be SEO-optimized. It should use an active voice and include the "
  "product's features, benefits, unique selling points without overpromising, and a call to action for the buyer. "
  "Benefits describe how product features will work for the buyer, addressing exactly how the product will improve their "
  "lives. Clearly distinguish between features (e.g., lightweight, USB-chargeable) and benefits (e.g., convenience, "
  "nutritious drinks on-the-go). Don't mention weaknesses of the product or use generic or repetitive language. Don't "
  "make up review text or quotes. Don't include any links. Don't cite the reviews too heavily. Divide your description "
  "into readable chunks divided by relevant subheadings. Keep your description around 200 words, no more than 300, in "
  "Markdown format.\n\n{document}"),
}
DATASETS = {"medical": ("data/medical.jsonl", "transcript"), "product": ("data/products.jsonl", "document")}

def load_inputs(name: str) -> list[dict]:
    path, var = DATASETS[name]
    rows = [json.loads(l) for l in (ROOT / path).read_text().splitlines() if l.strip()]
    return [{"id": r["id"], "vars": {var: r[var]}} for r in rows]

def fill(name: str, vars: dict) -> str:
    return PROMPTS[name].format(**vars)

def outputs_path(name: str, model: str) -> Path:
    return ROOT / "data" / "outputs" / f"{name}__{model}.jsonl"

def run(name: str, model: str = "haiku", limit: int | None = None, workers: int = 8) -> list[dict]:
    inputs = load_inputs(name)[:limit]
    jobs = [{"prompt": fill(name, x["vars"]), "model": model, "tag": "pipeline"} for x in inputs]
    res = llm.complete_many(jobs, workers=workers, desc=f"{name}/{model}")
    rows = [{"id": x["id"], "vars": x["vars"], "output": r["text"], "model": llm.MODELS.get(model, model)} for x, r in zip(inputs, res)]
    p = outputs_path(name, model); p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"wrote {len(rows)} outputs -> {p}  (cost ${llm.STATS['cost_usd']:.2f})", file=sys.stderr)
    return rows

def load_outputs(name: str, model: str) -> list[dict]:
    return [json.loads(l) for l in outputs_path(name, model).read_text().splitlines() if l.strip()]

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("pipeline", choices=list(PROMPTS)); ap.add_argument("--model", default="haiku")
    ap.add_argument("--limit", type=int); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(); run(a.pipeline, a.model, a.limit, a.workers)
