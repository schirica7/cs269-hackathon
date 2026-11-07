"""Build the shareable HTML report (results/report.html) from results/*.json. Narrative lives in NARRATIVE below."""
import json, statistics, html
from pathlib import Path
R = Path(__file__).resolve().parent.parent / "results"
def L(p):
    p = R / p; return json.loads(p.read_text()) if p.exists() else None
def esc(s): return html.escape(str(s))
def pc(x, d=0): return "–" if x is None else f"{100*x:.{d}f}%"

# ---------- SVG helpers (drawn to scale; colors via CSS vars so both themes work)
def hbars(groups, vmax=100, unit="%", width=560, colors=("var(--s1)", "var(--s2)", "var(--s3)"), legend=()):
    """groups: [(label, [v1, v2, ...])] values in 0..vmax. Grouped horizontal bars with direct value labels."""
    n = max(len(g[1]) for g in groups); bh = 14; gap = 3; row_h = n * (bh + gap) + 14; label_w = 190; pad_r = 56
    H = len(groups) * row_h + 10 + (24 if legend else 0); plot_w = width - label_w - pad_r
    out = [f'<svg viewBox="0 0 {width} {H}" width="100%" style="max-width:{width}px;display:block" role="img" aria-label="bar chart">']
    for i, (lab, vals) in enumerate(groups):
        y0 = i * row_h + 8 + (24 if legend else 0)
        out.append(f'<text x="{label_w-10}" y="{y0 + (n*(bh+gap))/2 + 4}" text-anchor="end" class="axl">{esc(lab)}</text>')
        for j, v in enumerate(vals):
            if v is None: continue
            y = y0 + j * (bh + gap); w = max(0, min(v, vmax)) / vmax * plot_w
            out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bh}" rx="3" fill="{colors[j % len(colors)]}"/>')
            out.append(f'<text x="{label_w + w + 6:.1f}" y="{y + bh - 3}" class="val">{v:.0f}{unit}</text>')
    for k in range(0, vmax + 1, 25):
        x = label_w + k / vmax * plot_w
        out.append(f'<line x1="{x:.1f}" y1="{(24 if legend else 0)+4}" x2="{x:.1f}" y2="{H-4}" class="grid"/>')
    if legend:
        for j, name in enumerate(legend):
            x = label_w + j * 170
            out.append(f'<rect x="{x}" y="4" width="12" height="12" rx="3" fill="{colors[j]}"/><text x="{x+18}" y="14" class="axl">{esc(name)}</text>')
    out.append("</svg>"); return "\n".join(out)

def table(headers, rows, cls=""):
    h = "".join(f"<th>{esc(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

e1 = {n: L(f"e1_{n}.json") for n in ["medical", "product"]}
e2 = {n: L(f"e2_{n}.json") for n in ["medical", "product"]}
e3 = {n: L(f"e3_{n}.json") for n in ["medical", "product"]}
cr = {n: L(f"criteria_{n}.json") for n in ["medical", "product"]}
gf = L("e1_product_gradefirst.json")
rub = (R / "REVIBE_RUBRIC.md").read_text() if (R / "REVIBE_RUBRIC.md").exists() else ""
import re
rub_rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in rub.splitlines() if l.startswith("| T")]
rub_score = re.search(r"Revibeability = (\d+) / (\d+) = ([0-9.]+)", rub)

NARR = json.loads((R / "narrative.json").read_text()) if (R / "narrative.json").exists() else {}
def N(k, default=""): return NARR.get(k, default)

# ---------- sections
sec = []
# hero stats
agent_acc = None
if e2["medical"] and e2["product"]:
    accs = [r["vs_expert"]["accuracy"] for n in e2 for r in e2[n]["agents"].values()]
    agent_acc = (min(accs), max(accs))
sec.append(f"""
<header class="hero">
  <p class="eyebrow">CS 269 · revibe + replication · Shankar et al., UIST 2024</p>
  <h1>Who validates the validator agent?</h1>
  <p class="lede">{esc(N('lede', 'EvalGen rebuilt from the paper, its offline evaluation re-run with 2026 models, and then one change: the human grader is replaced by an LLM evaluator agent, the way most "programmer agent + evaluator agent" pipelines work today.'))}</p>
  <div class="tiles">
    <div class="tile"><div class="k">Revibeability</div><div class="v">{rub_score.group(3) if rub_score else '–'}</div><div class="s">{rub_score.group(1)+'/'+rub_score.group(2)+' rubric points' if rub_score else ''}</div></div>
    <div class="tile"><div class="k">Good outputs today</div><div class="v">{pc(e1['medical']['good_rate']) if e1['medical'] else '–'} · {pc(e1['product']['good_rate']) if e1['product'] else '–'}</div><div class="s">medical · product (paper: 68% · 51%)</div></div>
    <div class="tile"><div class="k">Evaluator-agent accuracy vs expert</div><div class="v">{(pc(agent_acc[0])+'–'+pc(agent_acc[1])) if agent_acc else 'pending'}</div><div class="s">range over 6 agent configurations</div></div>
  </div>
</header>""")

# 1 system
sec.append(f"""
<section id="system"><h2>1 · What was rebuilt</h2>
<p>{esc(N('system', 'The agent was given the paper text and asked to reimplement EvalGen as a web tool. The result is a Python package plus a single-page UI: an LLM proposes binary criteria from the prompt under test; a second LLM writes several candidate implementations per criterion (Python functions or LLM grader prompts); candidates run on every pipeline output while the user grades outputs thumbs-up / thumbs-down; a sampler picks what to grade next from selectivity-weighted confidence scores; and the most aligned candidate per criterion is selected under a false-failure-rate threshold and shown in a report card and a table view.'))}</p>
<div class="flow"><span>Prompt under test</span><span>→ Criteria (LLM)</span><span>→ Candidate assertions (code / LLM)</span><span>→ Execute on outputs</span><span>→ Human grades (alternating sampler)</span><span>→ Select by alignment</span><span>→ Report card · Table view</span></div>
<h3>Revibeability rubric (Adar et al., UIST 2026: 2 full / 1 partial / 0 fail per test)</h3>
{table(["#", "Test", "Score", "Notes"], [[r[0], esc(r[1]), f'<span class="sc sc{r[2]}">{r[2]}</span>', esc(r[3])] for r in rub_rows], "rubric")}
<p class="note">{esc(N('rubric_note', 'Score: ' + (rub_score.group(0) if rub_score else '') + '. The misses are ChainForge embedding (the host system), stepping back through graded outputs, and mid-response streaming of candidates.'))}</p>
</section>""")

# 2 E1
if e1["medical"] and e1["product"]:
    groups = []
    for n in ["medical", "product"]:
        d = e1[n]; P = d["paper"]
        groups.append((f"{n}: EvalGen", [P["evalgen"]["alignment"], 100 * d["evalgen_16"]["alignment"]]))
        groups.append((f"{n}: SPADE", [P["spade"]["alignment"], 100 * d["spade"]["alignment"]]))
    rows = []
    for n in ["medical", "product"]:
        d = e1[n]; P = d["paper"]
        for key, lab, pk in [("evalgen_16", "EvalGen · 16 grades", "evalgen"), ("spade", "SPADE-like · all grades", "spade"), ("evalgen_all", "EvalGen · all grades", None)]:
            e = d[key]; rows.append([n, lab, e["n_assertions"], f"{e['coverage']:.2f}", f"{e['ffr']:.2f}", f"<b>{pc(e['alignment'],1)}</b>", f"{P[pk]['alignment']:.1f}% (n={P[pk]['n_assertions']})" if pk else "–"])
    samp = []
    for n in ["medical", "product"]:
        s = e1[n]["sampling"]; samp.append((n, [100*statistics.mean(s["random"]), 100*s["highest"][0], 100*s["lowest"][0], 100*s["alternating"][0]]))
    sec.append(f"""
<section id="e1"><h2>2 · Re-running the paper's offline evaluation</h2>
<p>{esc(N('e1_intro', 'Same two pipelines and prompts as the paper (84 ACI-Bench doctor–patient transcripts; 100 Amazon All Beauty products with reviews), the same four + three criteria, 16 alternating-sampled grades, and the paper\'s FFR thresholds (10% medical, 40% product). The generator is Claude Haiku 5.5 in place of GPT-3.5-Turbo; candidates are written by Claude Opus 5.5 in place of GPT-4; LLM graders run on Haiku. Ground truth is one careful grader with a fixed rule set (see Method).'))}</p>
<figure>{hbars(groups, legend=("Paper (2024)", "This re-run (2026)"))}<figcaption>Alignment of the selected assertion set, scored on all ground-truth grades.</figcaption></figure>
{table(["Pipeline", "Method", "# assertions", "Coverage", "FFR", "Alignment", "Paper"], rows)}
<p>{esc(N('e1_finding', ''))}</p>
<h3>Sampling policy (paper Fig. 4)</h3>
<figure>{hbars(samp, legend=("random (mean of 10)", "highest", "lowest", "alternating"), colors=("var(--s4)", "var(--s2)", "var(--s3)", "var(--s1)"))}<figcaption>Alignment on all grades after 16 grades under each policy.</figcaption></figure>
<p>{esc(N('sampling_finding', ''))}</p>
</section>""")

# 3 criteria drift
if cr["product"]:
    rows = [[n, "<br>".join(esc(x["title"]) for x in cr[n]["infer"]), "<br>".join(esc(x["title"]) for x in cr[n]["grade_first"])] for n in ["medical", "product"] if cr[n]]
    gfrows = ""
    if gf:
        gfrows = table(["Method", "# assertions", "Coverage", "FFR", "Alignment"], [[lab, gf[k]["n_assertions"], f"{gf[k]['coverage']:.2f}", f"{gf[k]['ffr']:.2f}", f"<b>{pc(gf[k]['alignment'],1)}</b>"] for k, lab in [("evalgen_16", "EvalGen · 16 grades"), ("evalgen_all", "EvalGen · all grades"), ("spade", "SPADE-like")]])
    sec.append(f"""
<section id="drift"><h2>3 · Criteria drift, two years later</h2>
<p>{esc(N('drift_intro', ''))}</p>
{table(["Pipeline", "Infer (prompt only)", "Grade First (prompt + 8 graded bad outputs)"], rows)}
<p>{esc(N('drift_finding', ''))}</p>
{('<h3>Second iteration: implement the Grade-First criteria (product)</h3>' + gfrows) if gf else ''}
<p>{esc(N('gf_finding', ''))}</p>
</section>""")

# 4 E2
if e2["medical"] and e2["product"]:
    rows = []; g_acc = []; g_align = []
    for n in ["medical", "product"]:
        d = e2[n]; human = 100 * e1[n]["evalgen_16"]["alignment"]; exp_bad = 1 - e1[n]["good_rate"]
        for k, r in d["agents"].items():
            v = r["vs_expert"]
            rows.append([n, k, f"{pc(v['agent_bad_rate'])} <span class='mut'>({pc(exp_bad)})</span>", pc(v["accuracy"]), f"{v['coverage']:.2f}", f"{v['ffr']:.2f}", f"<b>{pc(v['alignment'])}</b>", f"{pc(r['evalgen_16_agent']['alignment'])} <span class='mut'>(n={r['evalgen_16_agent']['n_assertions']})</span>", f"{pc(r['evalgen_all_agent']['alignment'])}", pc(e1[n]["evalgen_16"]["alignment"])])
            g_acc.append((f"{n}: {k}", [100 * v["coverage"], 100 * (1 - v["ffr"]), 100 * v["accuracy"]]))
            g_align.append((f"{n}: {k}", [human, 100 * r["evalgen_16_agent"]["alignment"], 100 * r["evalgen_all_agent"]["alignment"]]))
    sec.append(f"""
<section id="e2"><h2>4 · The change: an evaluator agent replaces the human grader</h2>
<p>{esc(N('e2_intro', 'Six evaluator agents (Claude Haiku 5.5, Sonnet 5.5, Opus 5.5; each either shown only the prompt, or also the explicit criteria list) graded every output good/bad with one sentence of feedback, exactly the signal EvalGen collects from a person. Two questions: how well does the agent agree with the expert grader, and what happens to the assertion set EvalGen selects when the agent\'s grades drive selection?'))}</p>
<figure>{hbars(g_acc, legend=("coverage (catches expert-bad)", "1 − FFR (passes expert-good)", "accuracy"), colors=("var(--s1)", "var(--s3)", "var(--s2)"))}<figcaption>The evaluator agent treated as a single assertion, scored against expert grades.</figcaption></figure>
<figure>{hbars(g_align, legend=("16 human grades", "16 agent grades", "all agent grades"), colors=("var(--s1)", "var(--s2)", "var(--s4)"))}<figcaption>Alignment of the EvalGen-selected assertion set with expert truth, depending on who supplied the grades.</figcaption></figure>
{table(["Pipeline", "Agent", "Agent bad-rate (expert)", "Accuracy", "Coverage", "FFR", "Alignment", "EvalGen w/ 16 agent grades", "EvalGen w/ all agent grades", "EvalGen w/ 16 human grades"], rows)}
<p>{esc(N('e2_finding', ''))}</p>
<p>{esc(N('e2_examples', ''))}</p>
</section>""")

# 5 E3
if e3["medical"] and e3["product"]:
    rows = []
    for n in ["medical", "product"]:
        d = e3[n]; b = d["bad_rate"]; a = d["accuracy"]
        rows.append([n, pc(d["flip_iso_vs_seq_fwd"]), pc(d["flip_iso_vs_seq_rev"]), pc(d["flip_seq_fwd_vs_rev"]), f"{pc(b['isolated'])} / {pc(b['seq_fwd'])} / {pc(b['seq_rev'])} / <b>{pc(b['expert'])}</b>", f"{pc(a['isolated'])} / {pc(a['seq_fwd'])} / {pc(a['seq_rev'])}", " → ".join(pc(x) for x in d["seq_fwd_bad_rate_by_quartile"])])
    sec.append(f"""
<section id="e3"><h2>5 · Does the evaluator agent drift like the participants did?</h2>
<p>{esc(N('e3_intro', 'The paper\'s participants changed their criteria as they graded. To test the analogue, Claude Sonnet 5.5 graded each output three ways: in isolation; sequentially, seeing its own last eight verdicts (forward order); and sequentially in reverse order.'))}</p>
{table(["Pipeline", "Flips: isolated → seq (fwd)", "isolated → seq (rev)", "seq fwd → seq rev", "Bad-rate: iso / fwd / rev / expert", "Accuracy: iso / fwd / rev", "Bad-rate by quartile of the forward pass"], rows)}
<p>{esc(N('e3_finding', ''))}</p>
</section>""")

sec.append(f"""
<section id="method"><h2>6 · Method notes and caveats</h2>
<ul>
<li>{esc(N('m1', 'Ground truth: all 184 outputs were graded by one grader (Claude Fable 5.1 working interactively in this session, not a human) under a fixed written rule set: medical bad = PII (name, age, gender incl. pronouns, DOB, MRN), more than 210 words, missing key, or no bullet list; product bad = negative statements, links, no Markdown subheadings, more than 300 words, or non-copy text addressed to the requester. The paper used two authors. Treat agreement numbers as expert-stand-in agreement, not human agreement.'))}</li>
<li>{esc(N('m2', 'Models: generator Haiku 5.5 (the paper used GPT-3.5-Turbo), criteria and candidate synthesis Opus 5.5 (paper: GPT-4), LLM-based assertions executed with Haiku 5.5, evaluator agents Haiku / Sonnet / Opus 5.5. All calls went through Claude Code in headless mode with tools disabled; roughly 3,300 calls were made and every one is cached, so results/ is reproducible offline.'))}</li>
<li>{esc(N('m3', 'The SPADE baseline is a re-implementation of its selection objective (smallest assertion set covering every criterion under the FFR threshold, then maximum coverage) over the same candidate pool, not the SPADE system, which generates its own candidates from prompt history.'))}</li>
<li>{esc(N('m4', 'Datasets: ACI-Bench train + valid dialogues (84 of 87 sampled with seed 0), and Amazon Reviews 2023 All Beauty items joined to their reviews, keeping items with at least four reviews including at least one rated 2 or below, so the "no negative statements" criterion has something to catch.'))}</li>
</ul>
<p class="note">Repository: <code>cs269-hackathon</code> · <code>evalgen/</code> (package), <code>ui/index.html</code>, <code>results/</code>, <code>REPORT.md</code>.</p>
</section>""")

CSS = """
<title>Who Validates the Validator Agent</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* layout: one reading column (~68ch) with full-width tables; a report-card feel: ruled sections, numeric columns in mono */
:root{--bg:#f6f7f9;--fg:#15202b;--mute:#5b6675;--line:#d9dee6;--panel:#ffffff;--acc:#2a5bd7;--acc-ink:#1d44a8;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#8a93a3;--good:#1f8a4c;--bad:#c6373a;--warn:#b97200;
 --display:"Fraunces",Georgia,serif;--body:"IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;--mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#121619;--fg:#e8ecf1;--mute:#a2acb9;--line:#2a323c;--panel:#1a2026;--acc:#6f9bff;--acc-ink:#9ab8ff;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#7c8696;--good:#3fb36f;--bad:#e66767;--warn:#d99a2b;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121619;--fg:#e8ecf1;--mute:#a2acb9;--line:#2a323c;--panel:#1a2026;--acc:#6f9bff;--acc-ink:#9ab8ff;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#7c8696;--good:#3fb36f;--bad:#e66767;--warn:#d99a2b;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:16px/1.55 var(--body);margin:0}
.wrap{max-width:980px;margin:0 auto;padding-block:28px 64px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.hero{border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:8px}
.eyebrow{font:500 12px/1.4 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 10px}
h1{font:700 clamp(30px,5vw,46px)/1.08 var(--display);margin:0 0 14px;text-wrap:balance;letter-spacing:-.01em}
h2{font:600 clamp(22px,3vw,28px)/1.2 var(--display);margin:40px 0 12px;text-wrap:balance}
h3{font:600 17px/1.3 var(--body);margin:26px 0 8px}
p,li{max-width:68ch} p{margin:0 0 12px}
.lede{font-size:18px;color:var(--fg);max-width:70ch}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:20px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile .k{font:500 12px/1.3 var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--mute)}
.tile .v{font:700 30px/1.1 var(--display);margin:6px 0 4px;font-variant-numeric:tabular-nums}
.tile .s{font-size:13px;color:var(--mute)}
.flow{display:flex;flex-wrap:wrap;gap:6px 10px;font:500 13px/1.4 var(--mono);color:var(--acc-ink);margin:10px 0 6px}
.tw{overflow-x:auto;margin:10px 0 14px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font:600 12px/1.3 var(--mono);letter-spacing:.03em;color:var(--mute);background:var(--bg);position:sticky;top:0}
td{font-variant-numeric:tabular-nums} tbody tr:last-child td{border-bottom:0}
.rubric td:nth-child(2){min-width:260px} .rubric td:nth-child(4){min-width:300px;color:var(--mute)}
.sc{display:inline-block;min-width:22px;text-align:center;border-radius:6px;font:600 12px/20px var(--mono);color:#fff}
.sc2{background:var(--good)} .sc1{background:var(--warn)} .sc0{background:var(--bad)}
figure{margin:14px 0 6px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 14px 8px}
figcaption{font-size:13px;color:var(--mute);margin-top:6px}
.axl{font:12.5px var(--body);fill:var(--fg)} .val{font:500 11.5px var(--mono);fill:var(--mute)} .grid{stroke:var(--line);stroke-width:1}
.mut{color:var(--mute)} .note{font-size:14px;color:var(--mute)} code{font:13px var(--mono);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:1px 5px}
a{color:var(--acc-ink)} ul{padding-left:20px} li{margin-bottom:8px}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
</style>"""
(R / "report.html").write_text(CSS + '\n<div class="wrap">' + "\n".join(sec) + "</div>\n")
print("wrote", R / "report.html", (R / "report.html").stat().st_size, "bytes")
