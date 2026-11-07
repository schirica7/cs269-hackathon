# EvalGen revibe — does the "programmer agent + evaluator agent" pipeline validate itself?

Hackathon project for CS 269. Target reading: Shankar et al., *Who Validates the Validators? Aligning LLM-Assisted
Evaluation of LLM Outputs with Human Preferences* (EvalGen, UIST 2024).

Two things are in this repo:

1. **A revibe of EvalGen** (`evalgen/`, `ui/`): criteria suggestion, candidate assertion synthesis (Python functions and
   LLM grader prompts), streaming execution, selectivity / confidence scores, the alternating grading sampler, alignment-based
   selection with an FFR threshold, the Report Card, and the Multi-Eval Table View. The web UI reproduces the Wizard
   (Infer / Manual / Grade First) -> Pick Criteria -> Grade -> Report Card -> Table View flow.
2. **Experiments** (`evalgen/experiments.py`, `results/`): the paper's offline evaluation re-run with today's models, and the
   "change one thing" study: the human grader is replaced by an LLM evaluator agent.

## Setup

No API key is needed: every model call goes through the Claude Code binary in headless mode (`claude -p --tools ""`),
so it uses your Claude subscription. Set `CLAUDE_BIN` if the binary is not on your PATH. Python 3.11+, standard library only.

```bash
python3 -m evalgen.pipeline medical --model haiku      # generate outputs for the medical pipeline (84 ACI-Bench transcripts)
python3 -m evalgen.pipeline product --model haiku      # 100 Amazon All_Beauty products with reviews
python3 scripts/build_assertions.py medical haiku      # synthesize (opus) + execute candidate assertions for the paper's criteria
python3 -m evalgen.experiments all                     # E1 (Table 1 / Fig 4), criteria suggestion, E2 (agent graders), E3 (drift)
python3 -m evalgen.server --pipeline medical --gen haiku   # the EvalGen UI at http://localhost:8765
```

Raw downloads (ACI-Bench CSVs, Amazon Reviews 2023 All_Beauty) are not committed; the sampled datasets built from them are in
`data/medical.jsonl` and `data/products.jsonl`.

Expert (human-stand-in) grades live in `data/grades/*__expert.jsonl`; evaluator-agent grades in `data/grades/*__agent-*.jsonl`.
All LLM calls are cached in `data/cache/` so every number in `results/` is reproducible offline.

See `REPORT.md` for findings and the revibeability score.
