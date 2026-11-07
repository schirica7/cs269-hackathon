"""Selectivity, confidence scores, grading samplers, alignment metrics, and assertion selection (Sec 4.2, App. A)."""
from __future__ import annotations
import itertools, random

def selectivity(res: dict) -> float:
    vals = [v for v in res.values() if v is not None]
    return sum(vals) / len(vals) if vals else 1.0

def confidence_scores(results: dict, output_ids: list[str]) -> dict:
    """score(o) = sum over assertions that FAIL o of selectivity(a). 0 = nothing failed it (likely good)."""
    sel = {cid: selectivity(r) for cid, r in results.items()}
    return {oid: sum(sel[cid] for cid, r in results.items() if r.get(oid) == 0) for oid in output_ids}

def sample(policy: str, scores: dict, n: int, graded: set[str] = frozenset(), seed: int = 0) -> list[str]:
    pool = [o for o in scores if o not in graded]
    if policy == "random":
        rng = random.Random(seed); return rng.sample(pool, min(n, len(pool)))
    hi = sorted(pool, key=lambda o: (-scores[o], o)); lo = sorted(pool, key=lambda o: (scores[o], o))
    if policy == "highest": return hi[:n]
    if policy == "lowest": return lo[:n]
    if policy == "alternating":
        out, seen = [], set()
        for a, b in zip(hi, lo):
            for x in (a, b):
                if x not in seen and len(out) < n: out.append(x); seen.add(x)
        return out
    raise ValueError(policy)

def set_fails(results: dict, chosen: list[str], oid: str) -> bool:
    return any(results[c].get(oid) == 0 for c in chosen)

def metrics(results: dict, chosen: list[str], grades: dict) -> dict:
    """grades: output_id -> 1 (good) / 0 (bad). Coverage = P(set fails | bad); FFR = P(set fails | good)."""
    bad = [o for o, g in grades.items() if g == 0]; good = [o for o, g in grades.items() if g == 1]
    cov = sum(set_fails(results, chosen, o) for o in bad) / len(bad) if bad else 0.0
    ffr = sum(set_fails(results, chosen, o) for o in good) / len(good) if good else 0.0
    inv = 1 - ffr
    align = 2 * cov * inv / (cov + inv) if (cov + inv) > 0 else 0.0
    return {"coverage": cov, "ffr": ffr, "alignment": align, "n_bad": len(bad), "n_good": len(good), "n_assertions": len(chosen)}

def select_evalgen(candidates: list[dict], results: dict, grades: dict, ffr_threshold: float = 0.1) -> dict:
    """Per criterion, keep the candidate with the highest alignment on the graded outputs, subject to FFR <= threshold."""
    chosen, detail = [], {}
    for crit in sorted({c["criterion_id"] for c in candidates}):
        cands = [c for c in candidates if c["criterion_id"] == crit]
        scored = [(c["id"], metrics(results, [c["id"]], grades)) for c in cands]
        ok = [s for s in scored if s[1]["ffr"] <= ffr_threshold + 1e-9]
        detail[crit] = {cid: m for cid, m in scored}
        if ok:
            best = max(ok, key=lambda s: (s[1]["alignment"], s[1]["coverage"]))
            chosen.append(best[0]); detail[crit]["selected"] = best[0]
        else:
            detail[crit]["selected"] = None
    return {"chosen": chosen, "detail": detail}

def select_spade(candidates: list[dict], results: dict, grades: dict, ffr_threshold: float = 0.1, max_extra: int = 2) -> dict:
    """SPADE-like baseline: smallest set covering every criterion with FFR <= threshold; ties -> max coverage."""
    crits = sorted({c["criterion_id"] for c in candidates}); ids = [c["id"] for c in candidates]
    crit_of = {c["id"]: c["criterion_id"] for c in candidates}
    best = None
    for k in range(len(crits), min(len(ids), len(crits) + max_extra) + 1):
        for combo in itertools.combinations(ids, k):
            if {crit_of[c] for c in combo} != set(crits): continue
            m = metrics(results, list(combo), grades)
            if m["ffr"] <= ffr_threshold + 1e-9 and (best is None or m["coverage"] > best[1]["coverage"]):
                best = (list(combo), m)
        if best: break
    return {"chosen": best[0] if best else [], "feasible": best is not None}

def simulate_evalgen(bundle: dict, grades_all: dict, n_grades: int = 16, policy: str = "alternating", ffr_threshold: float = 0.1,
                     seed: int = 0, grade_source: dict | None = None) -> dict:
    """Offline EvalGen run: sample n outputs to grade (alternating by default), select assertions on those grades,
    then score the chosen set against ALL ground-truth grades. grade_source lets a different grader (e.g. an LLM
    evaluator agent) supply the sampled grades while ground truth stays human."""
    results, cands = bundle["results"], bundle["candidates"]
    oids = list(grades_all)
    scores = confidence_scores(results, oids)
    sampled = sample(policy, scores, n_grades, seed=seed)
    src = grade_source or grades_all
    sample_grades = {o: src[o] for o in sampled if o in src}
    sel = select_evalgen(cands, results, sample_grades, ffr_threshold)
    m = metrics(results, sel["chosen"], grades_all)
    return {"sampled": sampled, "sample_grades": sample_grades, "chosen": sel["chosen"], "detail": sel["detail"], **m}
