"""Assemble REPORT.md from results/narrative.json + the tables from make_report.py."""
import json, subprocess, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; R = ROOT / "results"
N = json.loads((R / "narrative.json").read_text())
tables = subprocess.run([sys.executable, str(ROOT / "scripts/make_report.py")], capture_output=True, text=True).stdout
def sec(title): 
    m = re.search(rf"(### {re.escape(title)}.*?)(?=\n### |\Z)", tables, re.S); return m.group(1).strip() if m else ""
rub = (R / "REVIBE_RUBRIC.md").read_text()
rub_body = rub.split("\n", 1)[1] if rub.startswith("#") else rub
doc = f"""# Who validates the validator agent? — EvalGen revibed, re-measured, and run without the human

**Paper:** Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran, Arawjo. *Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences.* UIST 2024.
**Target type:** system (EvalGen) + the finding it rests on (criteria drift), then one change: the human grader is replaced by an LLM evaluator agent.

{N.get('lede','')}

## 1. What was rebuilt (revibe)

{N.get('system', 'See README.md for the package layout; `evalgen/` holds criteria suggestion, assertion synthesis/execution, selectivity/confidence scores, the alternating sampler, alignment selection, and a SPADE-like baseline; `ui/index.html` + `evalgen/server.py` reproduce the Wizard → Pick Criteria → Grade → Report Card → Table View flow.')}

### Revibeability
{rub_body.strip()}

{N.get('rubric_note','')}

## 2. Re-running the paper's offline evaluation (E1)

{N.get('e1_intro','')}

{sec('E1. Table 1 re-run')}

{N.get('e1_finding','')}

{N.get('sampling_finding','')}

## 3. Criteria drift, two years later

{N.get('drift_intro','')}

{sec('Criteria suggestion')}

{N.get('drift_finding','')}

{sec('Second EvalGen iteration on product')}

{N.get('gf_finding','')}

## 4. The change: an evaluator agent replaces the human grader (E2)

{N.get('e2_intro','')}

{sec('E2. Replace the human grader')}

{N.get('e2_finding','')}

{N.get('e2_examples','')}

## 5. Does the evaluator agent drift? (E3)

{N.get('e3_intro','')}

{sec('E3. Does an evaluator agent drift')}

{N.get('e3_finding','')}

## 6. A live grading demo for the class

{N.get('demo','')}

Demo: {N.get('demo_url','')} (private until shared; saving grades to class results needs Contributor access).

{N.get('demo_check','')}

## 7. Method notes and caveats

- {N.get('m1','')}
- {N.get('m2','')}
- {N.get('m3','')}
- {N.get('m4','')}

## 8. Answer to the course question: would the findings still hold?

{N.get('conclusion','')}
"""
(ROOT / "REPORT.md").write_text(doc); print("wrote REPORT.md", len(doc), "chars")
