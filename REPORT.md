# Who validates the validator agent? — EvalGen revibed, re-measured, and run without the human

**Paper:** Shankar, Zamfirescu-Pereira, Hartmann, Parameswaran, Arawjo. *Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences.* UIST 2024.
**Target type:** system (EvalGen) + the finding it rests on (criteria drift), then one change: the human grader is replaced by an LLM evaluator agent.

EvalGen (Shankar et al., UIST 2024) rebuilt from the paper alone, its offline evaluation re-run with 2026 models, and then one change: the human grader is replaced by an LLM evaluator agent, the way most 'programmer agent + evaluator agent' pipelines in industry are wired today.

## 1. What was rebuilt (revibe)

The agent was given the paper text and asked to reimplement EvalGen as a web tool. The result is a Python package plus a single-page UI: Claude Opus 5.5 proposes binary criteria from the prompt under test (optionally after the user has graded a few outputs); a second call per criterion writes three candidate implementations, Python functions or LLM grader prompts; candidates run on every pipeline output while the user grades outputs thumbs-up / thumbs-down with optional feedback; the next output to grade is chosen by the paper's alternating policy over selectivity-weighted confidence scores; and the most aligned candidate per criterion is selected under a false-failure-rate threshold and shown in a Report Card (per-criterion confusion matrices, aggregate coverage / FFR / alignment) and a Table View. The paper's SPADE baseline is re-implemented as a search for the smallest assertion set meeting the FFR threshold. No API key was available, so every model call runs through Claude Code in headless mode with tools disabled.

### Revibeability
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

The rebuild scores 23/28 = 0.82 (0.89 excluding the ChainForge-embedding test, which the paper treats as host infrastructure). This sits inside the 0.80–1.00 range Adar et al. report for ten UIST systems. Misses: no step-back arrows on the grading screen, candidates are not streamed from a partially generated LLM response, and there is no ChainForge node to return to.

## 2. Re-running the paper's offline evaluation (E1)



### E1. Table 1 re-run (paper criteria, generator = Claude Haiku 5.5, 16 alternating-sampled grades)

| Pipeline | Good rate (paper) | Method | # assertions | Coverage | FFR | Alignment | Paper alignment |
|---|---|---|---|---|---|---|---|
| medical | 74% (68%) | EvalGen (16 grades) | 3 | 1.00 | 0.52 | 65.2% | 48.3% (n=3, cov 0.33, FFR 0.10) |
| medical | 74% (68%) | SPADE-like (all grades) | 3 | 1.00 | 0.06 | 96.7% | 48.3% (n=5, cov 0.33, FFR 0.10) |
| medical | 74% (68%) | EvalGen (all grades) | 3 | 1.00 | 0.06 | 96.7% | – |
| product | 92% (51%) | EvalGen (16 grades) | 4 | 0.38 | 0.28 | 49.3% | 66.5% (n=4, cov 0.73, FFR 0.39) |
| product | 92% (51%) | SPADE-like (all grades) | 4 | 0.38 | 0.28 | 49.3% | 54.4% (n=9, cov 0.49, FFR 0.39) |
| product | 92% (51%) | EvalGen (all grades) | 4 | 0.38 | 0.28 | 49.3% | – |

**Sampling policy (Fig. 4 re-run; alignment of the selected set on all grades, 10 trials, 16 grades):**

| Pipeline | random (mean ± sd) | highest | lowest | alternating |
|---|---|---|---|---|
| medical | 92% ± 6 | 74% | 87% | 65% |
| product | 19% ± 23 | 40% | 19% | 49% |

Two things changed in two years. First, the generator got better: 74% and 92% of outputs are good versus 68% and 51% in the paper, so a 16-grade sample for the product pipeline contains only two bad outputs. Second, the failure modes changed. In the medical pipeline, PII leaks (the paper's dominant failure) appear in 3 of 84 outputs while 14 outputs are simply too long, so word-count code catches almost everything and alignment is far above the paper's 48%. In the product pipeline, none of the paper's failures (negative review content, links, bad Markdown, length) occur any more. All 8 bad outputs fail for a reason the 2024 criteria do not name: the model appends notes addressed to the requester after the copy ('Notes for your review: I omitted...'). The paper-era criteria therefore top out at 38% coverage, and alignment drops from the paper's 66% to 49%. The absolute numbers in Table 1 did not hold; the mechanism behind them did.

The paper reported that any non-random policy beats random sampling. Here the result splits by pipeline. On product, alternating is best (49% vs 19% random) because the bad outputs are rare and random samples of 16 usually contain none. On medical, random beats alternating (92% vs 65%): the alternating sample happened to contain no output on which the strict 120–180-word candidate false-fails, so EvalGen picked it, and on the full set that candidate fails 44% of good outputs. The sampler is only as good as the 16 grades let it be; with rare failures the policy matters, with common failures a bad draw matters more.

## 3. Criteria drift, two years later

The paper's central qualitative finding is criteria drift: people cannot fully define criteria before seeing outputs, and grading outputs changes the criteria. The offline numbers above are the quantitative face of the same thing. Asked for criteria from the prompt alone (Infer), Claude Opus 5.5 proposes essentially the paper's 2024 list. Given eight graded bad outputs with feedback (Grade First), it proposes the criterion the outputs actually violate.

### Criteria suggestion: Infer (prompt only) vs Grade First (prompt + graded bad outputs)

- **medical** · Infer: All six keys in bullet format; Word count near 150; No personally identifiable information; Faithful to the transcript; Correct N/A and dosage handling
  · Grade First: Word count within limit; No gender or age PII; All six keys as bullets in order; Faithful to transcript; Medications and follow-up complete with correct N/A use
- **product** · Infer: Word count within limit; Has Markdown subheadings; No links; Features and benefits kept distinct; No made-up quotes or claims
  · Grade First: No meta-commentary; No author-voice markers; Word count within limit; Subheadings present, no links; Ends with call to action

For the product pipeline the Grade-First list leads with 'No meta-commentary' and 'No author-voice markers', neither of which exists in the Infer list or the paper. For medical, Grade First sharpens the PII criterion to 'No gender or age PII' because the graded bad outputs leaked gender through pronouns and age through phrases like '55-year-old male'. This is the paper's claim reproduced with a different grader and different models: criteria depend on the outputs observed.

### Second EvalGen iteration on product (criteria from Grade First)

| Method | # assertions | Coverage | FFR | Alignment |
|---|---|---|---|---|
| EvalGen (16 grades) | 5 | 1.00 | 0.12 | 93.6% |
| EvalGen (all grades) | 5 | 1.00 | 0.03 | 98.3% |
| SPADE-like | 5 | 1.00 | 0.12 | 93.6% |

Implementing the Grade-First criteria and re-running EvalGen on the same 100 outputs lifts coverage from 0.38 to 1.00 and alignment from 49% to 94% with the same 16 grades (98% with all grades). The 'no meta-commentary' criterion is caught equally well by a regex for first-person asides and by an LLM grader, which is also what participants in the paper wanted: code where code suffices, an LLM where it does not.

## 4. The change: an evaluator agent replaces the human grader (E2)



### E2. Replace the human grader with an evaluator agent

Agent-as-assertion = treat the agent's thumbs-down as one assertion and score it against the expert grades. EvalGen(agent) = assertion set selected using the agent's grades, scored against expert truth.

| Pipeline | Evaluator agent | Agent bad-rate (expert) | Accuracy vs expert | Agent coverage | Agent FFR | Agent alignment | EvalGen align. w/ 16 agent grades | EvalGen align. w/ all agent grades | EvalGen align. w/ 16 human grades |
|---|---|---|---|---|---|---|---|---|---|
| medical | haiku/isolated | 60% (26%) | 62% | 0.91 | 0.48 | 66% | 63% (n=3) | 94% (n=3) | 65% |
| medical | haiku/criteria | 35% (26%) | 87% | 0.91 | 0.15 | 88% | 65% (n=3) | 97% (n=3) | 65% |
| medical | sonnet/isolated | 57% (26%) | 69% | 1.00 | 0.42 | 73% | 65% (n=3) | 97% (n=3) | 65% |
| medical | sonnet/criteria | 25% (26%) | 94% | 0.86 | 0.03 | 91% | 65% (n=3) | 97% (n=3) | 65% |
| medical | opus/isolated | 68% (26%) | 58% | 1.00 | 0.56 | 61% | 65% (n=3) | 72% (n=3) | 65% |
| medical | opus/criteria | 31% (26%) | 93% | 0.95 | 0.08 | 94% | 65% (n=3) | 97% (n=3) | 65% |
| product | haiku/isolated | 49% (8%) | 55% | 0.75 | 0.47 | 62% | 16% (n=4) | 37% (n=4) | 49% |
| product | haiku/criteria | 11% (8%) | 85% | 0.25 | 0.10 | 39% | 16% (n=4) | 37% (n=4) | 49% |
| product | sonnet/isolated | 38% (8%) | 62% | 0.50 | 0.37 | 56% | 16% (n=4) | 37% (n=4) | 49% |
| product | sonnet/criteria | 9% (8%) | 87% | 0.25 | 0.08 | 39% | 19% (n=4) | 49% (n=4) | 49% |
| product | opus/isolated | 60% (8%) | 48% | 1.00 | 0.57 | 61% | 16% (n=4) | 37% (n=4) | 49% |
| product | opus/criteria | 12% (8%) | 92% | 0.75 | 0.07 | 83% | 19% (n=4) | 49% (n=4) | 49% |

Shown only the prompt, every evaluator agent is far stricter than the expert grader: it fails 57–68% of medical outputs (expert: 26%) and 38–60% of product outputs (expert: 8%), reaching for criteria the expert did not apply, such as 'overpromises', 'benefits are vague', or 'bold labels instead of plain key: value'. Coverage is high (it catches nearly every expert-bad output) but the false failure rate runs 37–57%, so accuracy sits at 48–69%, and Opus is the strictest of the three. Handing the agent the explicit criteria list changes everything: false failure rates fall to 3–15%, accuracy rises to 85–94%, and the agent's bad-rate lands within a few points of the expert's. With criteria, the agent's own grades are as aligned as the better single assertions (88–94% alignment on medical; 83% for Opus on product). The residual errors are instructive: with criteria, the agent still fails good outputs for being too short ('131 words falls well short of around 200') or for safety text it reads as a drawback, and it passes two of the eight meta-commentary outputs, exactly the failure the 2024 criteria do not name. For the pipeline question, the assertion set EvalGen selects from 16 agent grades is about as good as the one it selects from 16 human grades (65% vs 65% medical; 16–19% vs 49% product, where two bad outputs in the sample are too few for either grader). Letting the agent grade all 84–100 outputs, which costs nothing, reaches the all-human-grades ceiling on medical (97%) for four of six agents.

In other words, the evaluator agent is a reasonable validator once a human has written down what counts, and an unreliable one when asked to infer that from the prompt alone. The strictness is not noise: agents disagreed with the expert in the same direction, by applying unstated criteria. The paper's phrase for this was 'tacit criteria'; here the tacit criteria belong to the model.

## 5. Does the evaluator agent drift? (E3)

The paper's participants changed their criteria as they graded, and one of them admitted grading for consistency with earlier verdicts rather than belief. To test the analogue, Claude Sonnet 5.5 graded each output three ways: in isolation; sequentially, seeing its own last eight outputs and verdicts (forward order); and sequentially in reverse order.

### E3. Does an evaluator agent drift? (Claude Sonnet 5.5; isolated vs sequential with its own prior verdicts)

| Pipeline | Flip rate iso→seq(fwd) | iso→seq(rev) | seq(fwd)→seq(rev) | Bad-rate iso / fwd / rev / expert | Accuracy iso / fwd / rev | Bad-rate by quartile (fwd) |
|---|---|---|---|---|---|---|
| medical | 39% | 40% | 20% | 57% / 18% / 17% / 26% | 69% / 77% / 74% | 52% → 5% → 10% → 5% |
| product | 30% | 26% | 6% | 38% / 10% / 14% / 8% | 62% / 84% / 80% | 12% → 12% → 4% → 12% |

The agent drifts, and in a recognisable direction. Seeing its own history makes it markedly more lenient: on medical the bad-rate falls from 57% in isolation to 18% (forward) and 17% (reverse), on product from 38% to 10% and 14%, in both cases landing near the expert's 26% and 8%. Within the forward medical pass the threshold visibly moves: 52% of the first quartile is flagged bad, then 5%, 10% and 5% for the rest. The feedback text says why: 'about 185 words, which is acceptable for a dense transcript and matches the earlier accepted case.' Thirty to forty percent of verdicts flip between the isolated and sequential conditions, and 6–20% flip between the two orderings of the same outputs, so the grade an output receives depends on which outputs preceded it. The drift happens to improve agreement with the expert here (accuracy 69% → 77% medical, 62% → 84% product), because the isolated agent is too strict and the history pulls it toward the base rate. That is a property of this sample, not a guarantee: the same mechanism would pull an agent toward leniency on a batch of bad outputs. The paper's claim that criteria depend on the outputs observed holds for the LLM grader too, and at a faster time scale.

## 6. Method notes and caveats

- 
- Models: generator Haiku 5.5 (the paper used GPT-3.5-Turbo), criteria and candidate synthesis Opus 5.5 (paper: GPT-4), LLM-based assertions executed with Haiku 5.5, evaluator agents Haiku / Sonnet / Opus 5.5. All calls went through Claude Code in headless mode with tools disabled; about 2,800 distinct calls were made (roughly $25 at list price) and every one is cached, so results/ is reproducible offline.
- 
- 

## 7. Answer to the course question: would the findings still hold?

Would the findings still hold? The system does: EvalGen revibes to 0.82 on the Adar et al. rubric from the paper text alone, in one session. Table 1 does not: both pipelines' generators are now good enough that the 2024 failure modes mostly vanished (74% and 92% good outputs vs 68% and 51%), and the product pipeline's only remaining failures are a kind the 2024 criteria never name, so the paper's criteria score 49% alignment where the paper reported 66%. Criteria drift holds and is now the whole story: a criterion inferred from the prompt alone misses the real failures, a criterion suggested from eight graded outputs catches all of them (94% alignment with the same 16 grades). For the pipeline the user asked about, programmer agent plus evaluator agent, the answer is conditional. Asked to judge from the prompt alone, every evaluator agent tested (Haiku, Sonnet, Opus 5.5) fails two to seven times more outputs than the expert, applying criteria the developer never wrote down; given the criteria list, it agrees with the expert 85–94% of the time, and its grades can drive EvalGen's selection as well as 16 human grades. It still passes a quarter of the one novel failure type, and its verdicts drift with its own recent history. Two years on, the paper's title question stands and sharpens: the evaluator agent is cheap and competent at applying stated criteria, and nothing in the pipeline can tell it which criteria the outputs actually demand. That part has not been automated; it has only been hidden one agent further from the human.
