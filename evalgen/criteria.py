"""Criteria Suggestion (paper Sec 4.1): an LLM proposes binary criteria from the prompt under test."""
from __future__ import annotations
from . import llm

CRITERIA_SCHEMA = {"type": "object", "properties": {"criteria": {"type": "array", "items": {"type": "object", "properties": {
    "title": {"type": "string"}, "description": {"type": "string"},
    "eval_type": {"type": "string", "enum": ["code", "llm"]}}, "required": ["title", "description", "eval_type"],
    "additionalProperties": False}}}, "required": ["criteria"], "additionalProperties": False}

SUGGEST_SYSTEM = ("You are an expert at evaluating outputs of LLM pipelines. You help developers write concise, binary "
                  "(pass/fail) evaluation criteria for the responses produced by a prompt template.")

def suggest(pipeline_prompt: str, model: str = "opus", n: int = 5, graded_examples: list[dict] | None = None) -> list[dict]:
    ex = ""
    if graded_examples:
        ex = "\n\nThe developer has already graded some outputs. Bad outputs with their feedback:\n" + "\n".join(
            f"- OUTPUT: {g['output'][:600]!r}\n  FEEDBACK: {g.get('feedback','')}" for g in graded_examples if g.get("grade") == 0)
    prompt = (f"Here is my LLM prompt template (placeholders in curly braces are filled at runtime):\n\n```\n{pipeline_prompt}\n```\n"
              f"Suggest {n} distinct binary evaluation criteria that an output should satisfy. Each criterion needs a short title, "
              "a one-sentence description precise enough to implement, and eval_type: 'code' if a plain Python function could "
              "check it reliably (format, counts, forbidden strings), or 'llm' if judging it needs language understanding." + ex)
    r = llm.complete(prompt, system=SUGGEST_SYSTEM, model=model, schema=CRITERIA_SCHEMA, tag="suggest")
    out = []
    for i, c in enumerate(r["structured"]["criteria"]):
        out.append({"id": f"c{i+1}", **c, "source": "llm"})
    return out

# The fixed criteria the authors used for the offline evaluation (Sec 5.2.1), so Table 1 can be re-run as-is.
PAPER_CRITERIA = {
 "medical": [
  {"id": "m1", "title": "Word count", "description": "The response is around 150 words (roughly 100 to 200 words).", "eval_type": "code"},
  {"id": "m2", "title": "Six keys present", "description": "The response contains all six targeted keys: chief complaint, history of present illness, physical examination, symptoms, new medications, follow-up instructions.", "eval_type": "code"},
  {"id": "m3", "title": "No PII", "description": "The response contains no personally identifiable information such as the patient's name, age, gender, or ID; it refers to 'the patient'.", "eval_type": "llm"},
 ],
 "product": [
  {"id": "p1", "title": "No negative statements", "description": "The description does not mention weaknesses, complaints, or negative review content about the product; it stays entirely positive.", "eval_type": "llm"},
  {"id": "p2", "title": "No links", "description": "The description contains no URLs or hyperlinks.", "eval_type": "code"},
  {"id": "p3", "title": "Markdown with subheadings", "description": "The description is in Markdown format and is divided into chunks with subheadings.", "eval_type": "code"},
  {"id": "p4", "title": "Word count limit", "description": "The description is around 200 words and no more than 300 words.", "eval_type": "code"},
 ],
}
