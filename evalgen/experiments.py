"""Offline experiments.

E1  Re-run the paper's Table 1 / Fig 4 (EvalGen vs SPADE-like baseline; sampling policies) with the expert grades.
E2  The change: replace the human grader with an evaluator agent (haiku / sonnet / opus; with and without explicit criteria).
    Measure (a) how well the agent's grades agree with the expert, treating the agent as an assertion itself, and
    (b) the alignment of the assertion set EvalGen selects when the agent's grades drive selection, scored on expert truth.
E3  Criteria drift in evaluator agents: isolated vs sequential (agent sees its own previous verdicts), forward vs reverse order.
"""
from __future__ import annotations
import json, statistics, sys
from pathlib import Path
from . import pipeline, align, grader, llm, criteria as crit_mod

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"; RES.mkdir(exist_ok=True)
PAPER = {"medical": {"evalgen": {"n_assertions": 3, "coverage": 0.33, "ffr": 0.10, "alignment": 48.29}, "spade": {"n_assertions": 5, "coverage": 0.33, "ffr": 0.10, "alignment": 48.29}, "ffr_threshold": 0.10, "good_rate": 0.68, "n": 84},
         "product": {"evalgen": {"n_assertions": 4, "coverage": 0.73, "ffr": 0.39, "alignment": 66.46}, "spade": {"n_assertions": 9, "coverage": 0.49, "ffr": 0.39, "alignment": 54.35}, "ffr_threshold": 0.40, "good_rate": 0.51, "n": 100}}

def load_grades(name, gen="haiku", who="expert") -> dict:
    p = ROOT / "data" / "grades" / f"{name}__{gen}__{who}.jsonl"
    return {r["id"]: r for r in map(json.loads, p.read_text().splitlines()) if r.get("grade") in (0, 1)}

def load_bundle(name, gen="haiku", label="paper"):
    return json.loads((ROOT / "data" / "assertions" / f"{name}__{gen}__{label}.json").read_text())

def pct(x): return None if x is None else round(100 * x, 1)

def agent_as_assertion(agent: dict, truth: dict) -> dict:
    """Treat the evaluator agent's thumbs-down as a single assertion and score it against the expert."""
    res = {"agent": {o: (g["grade"] if g["grade"] is not None else 1) for o, g in agent.items()}}
    m = align.metrics(res, ["agent"], {o: g["grade"] for o, g in truth.items()})
    acc = sum(res["agent"][o] == truth[o]["grade"] for o in truth) / len(truth)
    return {**m, "accuracy": acc, "agent_bad_rate": 1 - sum(res["agent"].values()) / len(res["agent"])}

def e1(name, gen="haiku", label="paper"):
    b = load_bundle(name, gen, label); truth = {o: g["grade"] for o, g in load_grades(name, gen).items()}
    thr = PAPER[name]["ffr_threshold"]
    out = {"pipeline": name, "n": len(truth), "n_bad": sum(1 for v in truth.values() if v == 0), "good_rate": sum(truth.values()) / len(truth), "ffr_threshold": thr,
           "candidates": [{"id": c["id"], "criterion": c["criterion_id"], "type": c["type"], "name": c["name"],
                           "selectivity": align.selectivity(b["results"][c["id"]]), **align.metrics(b["results"], [c["id"]], truth)} for c in b["candidates"]]}
    # EvalGen with 16 alternating-sampled human grades (paper setup), 10 seeds for the tie-breaking in random policy only; alternating is deterministic
    out["evalgen_16"] = align.simulate_evalgen(b, truth, n_grades=16, policy="alternating", ffr_threshold=thr)
    out["evalgen_all"] = {**align.select_evalgen(b["candidates"], b["results"], truth, thr)}
    out["evalgen_all"].update(align.metrics(b["results"], out["evalgen_all"]["chosen"], truth))
    sp = align.select_spade(b["candidates"], b["results"], truth, thr); out["spade"] = {**sp, **align.metrics(b["results"], sp["chosen"], truth)}
    # Fig 4: sampling policy study, 10 trials x 4 policies, 16 grades
    out["sampling"] = {p: [align.simulate_evalgen(b, truth, 16, p, thr, seed=s)["alignment"] for s in range(10)] for p in ["random", "highest", "lowest", "alternating"]}
    out["paper"] = PAPER[name]
    (RES / (f"e1_{name}.json" if label == "paper" else f"e1_{name}_{label}.json")).write_text(json.dumps(out, indent=1, default=str))
    print(f"[E1 {name}] good_rate={out['good_rate']:.2f} (paper {PAPER[name]['good_rate']})  EvalGen16: n={out['evalgen_16']['n_assertions']} cov={out['evalgen_16']['coverage']:.2f} ffr={out['evalgen_16']['ffr']:.2f} align={pct(out['evalgen_16']['alignment'])}  "
          f"SPADE: n={out['spade']['n_assertions']} cov={out['spade']['coverage']:.2f} ffr={out['spade']['ffr']:.2f} align={pct(out['spade']['alignment'])} feasible={sp['feasible']}", file=sys.stderr)
    for p, v in out["sampling"].items(): print(f"   policy {p:11s} mean align {statistics.mean(v)*100:5.1f}  sd {statistics.pstdev(v)*100:4.1f}", file=sys.stderr)
    return out

def e2(name, gen="haiku", models=("haiku", "sonnet", "opus"), modes=("isolated", "criteria")):
    b = load_bundle(name, gen); truth_rows = load_grades(name, gen); truth = {o: g["grade"] for o, g in truth_rows.items()}
    outs = [o for o in pipeline.load_outputs(name, gen) if o["id"] in truth]; thr = PAPER[name]["ffr_threshold"]
    res = {"pipeline": name, "agents": {}}
    for model in models:
        for mode in modes:
            key = f"{model}/{mode}"
            ag = grader.grade_many(pipeline.PROMPTS[name], outs, model=model, mode=mode, criteria=b["criteria"])
            (ROOT / "data" / "grades" / f"{name}__{gen}__agent-{model}-{mode}.jsonl").write_text("\n".join(json.dumps({"id": o, **g}) for o, g in ag.items()) + "\n")
            agent_grades = {o: g["grade"] for o, g in ag.items() if g["grade"] is not None}
            r = {"vs_expert": agent_as_assertion(ag, truth_rows)}
            # EvalGen driven by the agent's grades on the same 16 alternating-sampled outputs, scored on expert truth
            r["evalgen_16_agent"] = align.simulate_evalgen(b, truth, 16, "alternating", thr, grade_source=agent_grades)
            # Fully automated: agent grades everything (cheap), EvalGen selects on all of them, scored on expert truth
            sel = align.select_evalgen(b["candidates"], b["results"], agent_grades, thr)
            r["evalgen_all_agent"] = {"chosen": sel["chosen"], **align.metrics(b["results"], sel["chosen"], truth)}
            # Disagreement examples
            r["false_passes"] = [o for o in truth if truth[o] == 0 and agent_grades.get(o) == 1][:20]
            r["false_fails"] = [{"id": o, "feedback": ag[o]["feedback"]} for o in truth if truth[o] == 1 and agent_grades.get(o) == 0][:20]
            res["agents"][key] = r
            v = r["vs_expert"]
            print(f"[E2 {name}] {key:16s} acc={v['accuracy']:.2f} agent_bad_rate={v['agent_bad_rate']:.2f} | as-assertion cov={v['coverage']:.2f} ffr={v['ffr']:.2f} align={pct(v['alignment'])} | "
                  f"EvalGen(16 agent grades) align={pct(r['evalgen_16_agent']['alignment'])} n={r['evalgen_16_agent']['n_assertions']} | EvalGen(all agent grades) align={pct(r['evalgen_all_agent']['alignment'])}", file=sys.stderr)
    (RES / f"e2_{name}.json").write_text(json.dumps(res, indent=1, default=str))
    return res

def e3(name, gen="haiku", model="sonnet"):
    truth_rows = load_grades(name, gen); truth = {o: g["grade"] for o, g in truth_rows.items()}
    outs = [o for o in pipeline.load_outputs(name, gen) if o["id"] in truth]
    iso = {o: g["grade"] for o, g in grader.grade_many(pipeline.PROMPTS[name], outs, model=model, mode="isolated").items()}
    fwd_full = grader.grade_many(pipeline.PROMPTS[name], outs, model=model, mode="sequential")
    rev_full = grader.grade_many(pipeline.PROMPTS[name], list(reversed(outs)), model=model, mode="sequential")
    fwd = {o: g["grade"] for o, g in fwd_full.items()}; rev = {o: g["grade"] for o, g in rev_full.items()}
    ids = [o["id"] for o in outs]
    def flips(a, b): return sum(a[o] != b[o] for o in ids) / len(ids)
    def bad_rate_by_position(seq, order):
        n = len(order); q = n // 4
        return [1 - statistics.mean(seq[o] for o in order[i*q:(i+1)*q]) for i in range(4)]
    out = {"pipeline": name, "model": model, "n": len(ids),
           "flip_iso_vs_seq_fwd": flips(iso, fwd), "flip_iso_vs_seq_rev": flips(iso, rev), "flip_seq_fwd_vs_rev": flips(fwd, rev),
           "bad_rate": {"isolated": 1 - statistics.mean(iso.values()), "seq_fwd": 1 - statistics.mean(fwd.values()), "seq_rev": 1 - statistics.mean(rev.values()), "expert": 1 - statistics.mean(truth.values())},
           "seq_fwd_bad_rate_by_quartile": bad_rate_by_position(fwd, ids), "seq_rev_bad_rate_by_quartile": bad_rate_by_position(rev, list(reversed(ids))),
           "accuracy": {"isolated": sum(iso[o] == truth[o] for o in ids) / len(ids), "seq_fwd": sum(fwd[o] == truth[o] for o in ids) / len(ids), "seq_rev": sum(rev[o] == truth[o] for o in ids) / len(ids)},
           "examples_flipped": [{"id": o, "isolated": iso[o], "seq_fwd": fwd[o], "seq_rev": rev[o], "expert": truth[o], "fwd_feedback": fwd_full[o]["feedback"]} for o in ids if len({iso[o], fwd[o], rev[o]}) > 1][:15]}
    (RES / f"e3_{name}.json").write_text(json.dumps(out, indent=1))
    print(f"[E3 {name}] flips iso/fwd={out['flip_iso_vs_seq_fwd']:.2f} iso/rev={out['flip_iso_vs_seq_rev']:.2f} fwd/rev={out['flip_seq_fwd_vs_rev']:.2f}  bad_rate={ {k: round(v,2) for k,v in out['bad_rate'].items()} }  quartiles fwd={[round(x,2) for x in out['seq_fwd_bad_rate_by_quartile']]}", file=sys.stderr)
    return out

def grade_first_suggest(name, gen="haiku", model="opus"):
    """Does the 'Grade First' path surface the new failure type the paper-era criteria miss?"""
    truth_rows = load_grades(name, gen); outs = {o["id"]: o for o in pipeline.load_outputs(name, gen)}
    graded = [{"output": outs[o]["output"], "grade": g["grade"], "feedback": g["feedback"]} for o, g in truth_rows.items() if g["grade"] == 0][:8]
    infer = crit_mod.suggest(pipeline.PROMPTS[name], model=model)
    gf = crit_mod.suggest(pipeline.PROMPTS[name], model=model, graded_examples=graded)
    out = {"pipeline": name, "infer": infer, "grade_first": gf}
    (RES / f"criteria_{name}.json").write_text(json.dumps(out, indent=1))
    print(f"[criteria {name}] infer: {[c['title'] for c in infer]}\n   grade-first: {[c['title'] for c in gf]}", file=sys.stderr)
    return out

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("exp", choices=["e1", "e2", "e3", "criteria", "all"]); ap.add_argument("--pipeline", default="both"); ap.add_argument("--label", default="paper")
    a = ap.parse_args(); names = ["medical", "product"] if a.pipeline == "both" else [a.pipeline]
    for n in names:
        if a.exp in ("e1", "all"): e1(n, label=a.label)
        if a.exp in ("criteria", "all"): grade_first_suggest(n)
        if a.exp in ("e2", "all"): e2(n)
        if a.exp in ("e3", "all"): e3(n)
    print("LLM stats", llm.STATS, file=sys.stderr)
