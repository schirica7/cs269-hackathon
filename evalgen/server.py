"""EvalGen interface revibe: Wizard (Infer / Manual / Grade First) -> Pick Criteria -> Grade -> Report Card -> Table View.

Run:  python3 -m evalgen.server --pipeline medical --gen haiku   then open http://localhost:8765
State is kept in memory and mirrored to data/sessions/<pipeline>__<gen>.json so human grades are preserved.
"""
from __future__ import annotations
import argparse, json, threading, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from . import pipeline, criteria as crit_mod, assertions, align, llm

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "ui" / "index.html").read_text()

class State:
    def __init__(self, name, gen, synth_model="opus", grader_model="haiku"):
        self.name, self.gen, self.synth_model, self.grader_model = name, gen, synth_model, grader_model
        self.prompt = pipeline.PROMPTS[name]
        self.outputs = pipeline.load_outputs(name, gen)
        self.by_id = {o["id"]: o for o in self.outputs}
        self.criteria: list[dict] = []
        self.candidates: list[dict] = []
        self.results: dict = {}
        self.grades: dict = {}        # output_id -> {"grade": 1/0, "feedback": str}
        self.status = "idle"          # idle | implementing | done
        self.ffr_threshold = 0.1
        self.path = ROOT / "data" / "sessions" / f"{name}__{gen}.json"; self.path.parent.mkdir(exist_ok=True)
        if self.path.exists():
            d = json.loads(self.path.read_text()); self.grades = d.get("grades", {}); self.criteria = d.get("criteria", [])
            self.candidates = d.get("candidates", []); self.results = d.get("results", {}); self.status = d.get("status", "idle")
        self.lock = threading.Lock()
    def save(self):
        self.path.write_text(json.dumps({"grades": self.grades, "criteria": self.criteria, "candidates": self.candidates,
                                         "results": self.results, "status": self.status}))
    def grade_dict(self):
        return {o: g["grade"] for o, g in self.grades.items() if g.get("grade") in (0, 1)}
    def next_to_grade(self, policy="alternating"):
        scores = align.confidence_scores(self.results, [o["id"] for o in self.outputs]) if self.results else {o["id"]: 0 for o in self.outputs}
        pick = align.sample(policy, scores, 1, graded=set(self.grades))
        return pick[0] if pick else None
    def implement(self):
        self.status = "implementing"; self.save()
        def work():
            cands = []
            for c in self.criteria:
                for j, cand in enumerate(assertions.synthesize(c, self.prompt, [o["output"] for o in self.outputs[:3]], model=self.synth_model, k=3)):
                    cands.append({"id": f"{c['id']}_{j+1}", "criterion_id": c["id"], **cand})
                with self.lock: self.candidates = list(cands); self.save()
            # stream results per candidate so grading can use confidence scores as they arrive
            for cand in cands:
                r = assertions.execute([cand], self.outputs, grader_model=self.grader_model)
                with self.lock: self.results[cand["id"]] = r[cand["id"]]; self.save()
            with self.lock: self.status = "done"; self.save()
        threading.Thread(target=work, daemon=True).start()
    def report(self):
        grades = self.grade_dict()
        sel = align.select_evalgen(self.candidates, self.results, grades, self.ffr_threshold) if grades and self.candidates else {"chosen": [], "detail": {}}
        agg = align.metrics(self.results, sel["chosen"], grades) if grades else {}
        per = {}
        for c in self.criteria:
            cands = [x for x in self.candidates if x["criterion_id"] == c["id"]]
            per[c["id"]] = []
            for x in cands:
                m = align.metrics(self.results, [x["id"]], grades) if grades else {}
                cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}  # positive = flagged bad
                for o, g in grades.items():
                    f = self.results.get(x["id"], {}).get(o) == 0
                    cm[("tp" if g == 0 else "fp") if f else ("fn" if g == 0 else "tn")] += 1
                per[c["id"]].append({**x, "metrics": m, "confusion": cm, "selected": x["id"] in sel["chosen"],
                                     "selectivity": align.selectivity(self.results.get(x["id"], {}))})
        return {"chosen": sel["chosen"], "aggregate": agg, "per_criterion": per, "n_graded": len(grades)}
    def table(self):
        chosen = set(self.report()["chosen"]) if self.grades else set()
        cols = [c for c in self.candidates if (not chosen or c["id"] in chosen)]
        return {"columns": [{"id": c["id"], "name": c["name"], "criterion": c["criterion_id"]} for c in cols],
                "rows": [{"id": o["id"], "output": o["output"], "grade": self.grades.get(o["id"], {}).get("grade"),
                          "cells": {c["id"]: self.results.get(c["id"], {}).get(o["id"]) for c in cols}} for o in self.outputs]}

S: State = None

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = UI.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        if self.path == "/api/state":
            return self._json({"pipeline": S.name, "gen_model": S.gen, "prompt": S.prompt, "n_outputs": len(S.outputs), "criteria": S.criteria,
                               "candidates": [{k: v for k, v in c.items()} for c in S.candidates], "n_results": len(S.results),
                               "status": S.status, "grades": S.grades, "ffr_threshold": S.ffr_threshold, "cost_usd": llm.STATS["cost_usd"]})
        if self.path.startswith("/api/next"):
            oid = S.next_to_grade()
            if oid is None: return self._json({"done": True})
            o = S.by_id[oid]; return self._json({"id": oid, "vars": o["vars"], "output": o["output"], "n_graded": len(S.grades), "n_total": len(S.outputs)})
        if self.path.startswith("/api/output/"):
            o = S.by_id.get(self.path.rsplit("/", 1)[1]); return self._json(o or {}, 200 if o else 404)
        if self.path == "/api/report": return self._json(S.report())
        if self.path == "/api/table": return self._json(S.table())
        self._json({"error": "not found"}, 404)
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/grade":
            with S.lock: S.grades[body["id"]] = {"grade": int(body["grade"]), "feedback": body.get("feedback", "")}; S.save()
            return self._json({"ok": True, "n_graded": len(S.grades)})
        if self.path == "/api/ungrade":
            with S.lock: S.grades.pop(body["id"], None); S.save()
            return self._json({"ok": True})
        if self.path == "/api/criteria/suggest":
            graded = [{"output": S.by_id[o]["output"], **g} for o, g in S.grades.items()]
            sug = crit_mod.suggest(S.prompt, model=S.synth_model, graded_examples=graded or None)
            with S.lock: S.criteria = sug; S.save()
            return self._json({"criteria": sug})
        if self.path == "/api/criteria":          # user edits / adds / removes criteria
            with S.lock:
                S.criteria = [{"id": c.get("id") or f"u{i+1}", "title": c["title"], "description": c["description"],
                               "eval_type": c["eval_type"], "source": c.get("source", "user")} for i, c in enumerate(body["criteria"])]
                S.save()
            return self._json({"criteria": S.criteria})
        if self.path == "/api/implement":
            S.implement(); return self._json({"status": S.status})
        if self.path == "/api/threshold":
            S.ffr_threshold = float(body["ffr_threshold"]); return self._json({"ok": True})
        self._json({"error": "not found"}, 404)

def main():
    global S
    ap = argparse.ArgumentParser(); ap.add_argument("--pipeline", default="medical"); ap.add_argument("--gen", default="haiku")
    ap.add_argument("--port", type=int, default=8765); ap.add_argument("--synth-model", default="opus"); ap.add_argument("--grader-model", default="haiku")
    a = ap.parse_args(); S = State(a.pipeline, a.gen, a.synth_model, a.grader_model)
    print(f"EvalGen revibe on http://localhost:{a.port}  ({a.pipeline}, {len(S.outputs)} outputs)", file=sys.stderr)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()

if __name__ == "__main__": main()
