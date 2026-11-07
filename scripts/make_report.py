"""Compile results/*.json into markdown tables for REPORT.md (printed to stdout)."""
import json, statistics, sys
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"
def L(p): 
    p = R / p; return json.loads(p.read_text()) if p.exists() else None
def pc(x): return "–" if x is None else f"{100*x:.0f}%"
out = []
# ---- E1
out.append("### E1. Table 1 re-run (paper criteria, generator = Claude Haiku 5.5, 16 alternating-sampled grades)\n")
out.append("| Pipeline | Good rate (paper) | Method | # assertions | Coverage | FFR | Alignment | Paper alignment |")
out.append("|---|---|---|---|---|---|---|---|")
for n in ["medical", "product"]:
    d = L(f"e1_{n}.json"); 
    if not d: continue
    P = d["paper"]
    for key, label, pk in [("evalgen_16", "EvalGen (16 grades)", "evalgen"), ("spade", "SPADE-like (all grades)", "spade"), ("evalgen_all", "EvalGen (all grades)", None)]:
        e = d[key]; pa = f"{P[pk]['alignment']:.1f}% (n={P[pk]['n_assertions']}, cov {P[pk]['coverage']:.2f}, FFR {P[pk]['ffr']:.2f})" if pk else "–"
        out.append(f"| {n} | {pc(d['good_rate'])} ({pc(P['good_rate'])}) | {label} | {e['n_assertions']} | {e['coverage']:.2f} | {e['ffr']:.2f} | {100*e['alignment']:.1f}% | {pa} |")
out.append("\n**Sampling policy (Fig. 4 re-run; alignment of the selected set on all grades, 10 trials, 16 grades):**\n")
out.append("| Pipeline | random (mean ± sd) | highest | lowest | alternating |"); out.append("|---|---|---|---|---|")
for n in ["medical", "product"]:
    d = L(f"e1_{n}.json")
    if d: s = d["sampling"]; out.append(f"| {n} | {100*statistics.mean(s['random']):.0f}% ± {100*statistics.pstdev(s['random']):.0f} | {100*s['highest'][0]:.0f}% | {100*s['lowest'][0]:.0f}% | {100*s['alternating'][0]:.0f}% |")
# ---- criteria
out.append("\n### Criteria suggestion: Infer (prompt only) vs Grade First (prompt + graded bad outputs)\n")
for n in ["medical", "product"]:
    c = L(f"criteria_{n}.json")
    if c: out.append(f"- **{n}** · Infer: " + "; ".join(x["title"] for x in c["infer"]) + "\n  · Grade First: " + "; ".join(x["title"] for x in c["grade_first"]))
# ---- E2
out.append("\n### E2. Replace the human grader with an evaluator agent\n")
out.append("Agent-as-assertion = treat the agent's thumbs-down as one assertion and score it against the expert grades. EvalGen(agent) = assertion set selected using the agent's grades, scored against expert truth.\n")
out.append("| Pipeline | Evaluator agent | Agent bad-rate (expert) | Accuracy vs expert | Agent coverage | Agent FFR | Agent alignment | EvalGen align. w/ 16 agent grades | EvalGen align. w/ all agent grades | EvalGen align. w/ 16 human grades |")
out.append("|---|---|---|---|---|---|---|---|---|---|")
for n in ["medical", "product"]:
    d = L(f"e2_{n}.json"); e1 = L(f"e1_{n}.json")
    if not d: continue
    human = 100 * e1["evalgen_16"]["alignment"]; exp_bad = 1 - e1["good_rate"]
    for k, r in d["agents"].items():
        v = r["vs_expert"]
        out.append(f"| {n} | {k} | {pc(v['agent_bad_rate'])} ({pc(exp_bad)}) | {pc(v['accuracy'])} | {v['coverage']:.2f} | {v['ffr']:.2f} | {100*v['alignment']:.0f}% | {100*r['evalgen_16_agent']['alignment']:.0f}% (n={r['evalgen_16_agent']['n_assertions']}) | {100*r['evalgen_all_agent']['alignment']:.0f}% (n={r['evalgen_all_agent']['n_assertions']}) | {human:.0f}% |")
# ---- E3
out.append("\n### E3. Does an evaluator agent drift? (Claude Sonnet 5.5; isolated vs sequential with its own prior verdicts)\n")
out.append("| Pipeline | Flip rate iso→seq(fwd) | iso→seq(rev) | seq(fwd)→seq(rev) | Bad-rate iso / fwd / rev / expert | Accuracy iso / fwd / rev | Bad-rate by quartile (fwd) |"); out.append("|---|---|---|---|---|---|---|")
for n in ["medical", "product"]:
    d = L(f"e3_{n}.json")
    if d: b = d["bad_rate"]; a = d["accuracy"]; out.append(f"| {n} | {pc(d['flip_iso_vs_seq_fwd'])} | {pc(d['flip_iso_vs_seq_rev'])} | {pc(d['flip_seq_fwd_vs_rev'])} | {pc(b['isolated'])} / {pc(b['seq_fwd'])} / {pc(b['seq_rev'])} / {pc(b['expert'])} | {pc(a['isolated'])} / {pc(a['seq_fwd'])} / {pc(a['seq_rev'])} | {' → '.join(pc(x) for x in d['seq_fwd_bad_rate_by_quartile'])} |")
# ---- gradefirst iteration
g = L("e1_product_gradefirst.json")
if g:
    out.append("\n### Second EvalGen iteration on product (criteria from Grade First)\n")
    out.append("| Method | # assertions | Coverage | FFR | Alignment |"); out.append("|---|---|---|---|---|")
    for key, label in [("evalgen_16", "EvalGen (16 grades)"), ("evalgen_all", "EvalGen (all grades)"), ("spade", "SPADE-like")]:
        e = g[key]; out.append(f"| {label} | {e['n_assertions']} | {e['coverage']:.2f} | {e['ffr']:.2f} | {100*e['alignment']:.1f}% |")
print("\n".join(out))
