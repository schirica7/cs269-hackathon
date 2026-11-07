# Revibeability rubric for EvalGen (Adar et al., "Revibing Code from Papers", UIST 2026)

Scoring per the paper: each test = 2 (full success) / 1 (partial) / 0 (fail); revibeability = sum / (2 x number of tests).
Tests were written from the EvalGen paper (Sec. 3, Sec. 4, Fig. 2) before grading. Grader: the same agent that built the revibe,
executing each test against the running server with scripted requests and by reading the UI code (no second grader; the paper also used a single grader).

| # | Test | Score | Notes |
|---|---|---|---|
| T1 | Wizard with Infer / Manual / Grade First and a description | 2 | Present (`ui/index.html` wizard screen). Entry point is a standalone page, not a node button (see T14). |
| T2 | Infer: LLM proposes binary criteria from the prompt | 2 | `/api/criteria/suggest` -> opus; 5 criteria with code/llm type; verified by request. |
| T3 | Pick Criteria: edit, toggle code/LLM, delete, deselect, add | 2 | All five operations are in the criteria screen; `/api/criteria` persists them. |
| T4 | Grade First: grade >=5 then suggestions use feedback | 2 | Grade screen reachable before criteria; suggest() passes graded bad outputs + feedback into the prompt (verified in criteria experiment: surfaced 'No meta-commentary'). |
| T5 | Implement It: one LLM call per criterion -> several candidates (code / grader prompt), executed on outputs | 2 | 3 candidates per criterion via one structured-output call; code runs in a subprocess, grader prompts via haiku; 12 candidates x 100 outputs executed. |
| T6 | Streaming: results arrive progressively while grading | 1 | Execution results are published per candidate as each finishes; candidates within one criterion are not streamed from a partial LLM response (the paper parsed JSON markers mid-stream). |
| T7 | Grade screen: output in focus, vars, prompt, Good/Bad, feedback, I'm tired, no fixed end point | 2 | All elements present; progress bar shown only as count, matching the paper's choice not to impose an end point. |
| T8 | Sampler: alternating policy over selectivity-weighted confidence scores, updated live | 2 | `align.confidence_scores` + `align.sample('alternating')`; `/api/next` recomputes on every call from current results and grades. |
| T9 | Coverage / FFR / alignment as defined; per-criterion argmax subject to FFR threshold | 2 | `align.metrics`, `align.select_evalgen`; threshold editable in the Report Card (`/api/threshold`). |
| T10 | Report Card: per-criterion alignment + confusion matrix, aggregate coverage/FFR, implementations visible | 2 | Confusion matrix is shown inline rather than on hover; all candidates listed with the selected one highlighted. |
| T11 | Return to main interface: selected assertions in a Multi-Eval node runnable on all outputs | 1 | Assertions are already executed on all outputs and shown in the Table View, but there is no ChainForge node to return to. |
| T12 | Table View: rows outputs, columns assertions, pass/fail cells, grades visible | 2 | Implemented; expands output text per row. |
| T13 | Navigate back / revise a prior grade | 1 | `/api/ungrade` exists and grades are a map, but the UI has no arrow buttons to step back; revision requires reopening the grading screen. |
| T14 | Embedded in ChainForge (nodes, prompt node, LLM querying) | 0 | Not rebuilt; the revibe is a standalone app around the pipeline runner. |

**Revibeability = 23 / 28 = 0.82**  (unaided protocol: one agent, paper text only; two fix rounds for launch errors, none needed).

Excluding T14 (ChainForge embedding, which the paper treats as the host system rather than EvalGen's contribution): 23 / 26 = 0.88.

Caveats the Revibing paper itself raises apply here: agents are stochastic, and a different grader could reasonably score T6, T11 and T13 differently.
