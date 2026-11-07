"""LLM backend.

No API key is available on this machine, so every model call goes through the
Claude Code binary in headless mode (`claude -p`) with tools disabled and a
custom system prompt, which makes it behave like a plain Messages API call.
Calls are cached on disk so experiments are reproducible and re-runs are free.
"""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
CWD_DIR = ROOT / "data" / ".llm_cwd"   # empty dir so the agent sees no project files
CACHE_DIR.mkdir(parents=True, exist_ok=True); CWD_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_BIN = "/Users/willhuang/.vscode/extensions/anthropic.claude-code-2.1.319-darwin-arm64/resources/native-binary/claude"
CLAUDE_BIN = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or _DEFAULT_BIN

MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
_lock = threading.Lock()
STATS = {"calls": 0, "cached": 0, "cost_usd": 0.0, "errors": 0}

def _key(**kw) -> str:
    return hashlib.sha256(json.dumps(kw, sort_keys=True).encode()).hexdigest()[:32]

def complete(prompt: str, system: str | None = None, model: str = "haiku", schema: dict | None = None,
             effort: str | None = None, tag: str = "", use_cache: bool = True, retries: int = 3) -> dict:
    """Return {"text", "structured", "model", "cost_usd", "ms", "cached"}."""
    model = MODELS.get(model, model)
    k = _key(prompt=prompt, system=system, model=model, schema=schema, effort=effort, tag=tag)
    path = CACHE_DIR / f"{k}.json"
    if use_cache and path.exists():
        with _lock: STATS["cached"] += 1
        d = json.loads(path.read_text()); d["cached"] = True; return d
    cmd = [CLAUDE_BIN, "-p", "--model", model, "--no-session-persistence", "--tools", "",
           "--output-format", "json", "--max-turns", "3"]
    if system: cmd += ["--system-prompt", system]
    if schema: cmd += ["--json-schema", json.dumps(schema)]
    if effort: cmd += ["--effort", effort]
    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=900, cwd=CWD_DIR)
            d = json.loads(p.stdout)
            if d.get("is_error") or (schema and d.get("structured_output") is None):
                raise RuntimeError(f"claude error: {str(d.get('result'))[:300]}")
            out = {"text": d.get("result") or "", "structured": d.get("structured_output"), "model": model,
                   "cost_usd": d.get("total_cost_usd", 0.0), "ms": int((time.time() - t0) * 1000), "cached": False}
            with _lock:
                STATS["calls"] += 1; STATS["cost_usd"] += out["cost_usd"]
            path.write_text(json.dumps(out))
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e; time.sleep(2 * (attempt + 1))
    with _lock: STATS["errors"] += 1
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err}")

def complete_many(jobs: list[dict], workers: int = 8, desc: str = "") -> list[dict]:
    """jobs: list of kwargs for complete(). Returns results in the same order."""
    results = [None] * len(jobs); done = 0; t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(complete, **j): i for i, j in enumerate(jobs)}
        for f in as_completed(futs):
            i = futs[f]
            try: results[i] = f.result()
            except Exception as e:  # noqa: BLE001
                results[i] = {"text": "", "structured": None, "error": str(e), "cost_usd": 0, "cached": False}
            done += 1
            if done % 10 == 0 or done == len(jobs):
                print(f"  [{desc}] {done}/{len(jobs)}  {time.time()-t0:.0f}s  cost so far ${STATS['cost_usd']:.2f}", file=sys.stderr, flush=True)
    return results
