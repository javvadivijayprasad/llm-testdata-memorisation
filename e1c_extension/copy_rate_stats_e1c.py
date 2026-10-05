#!/usr/bin/env python3
"""E1c summary: copy rate (exact_text_pooled, near90_pooled, text_overlap_median) per schema x model, direct arm,
run 1; plus the HR edition result and the count of cells with a non-trivial copy rate. Writes results/E1c_stats.txt
and a LaTeX table. Conventions as copy_rate_stats.py (E1)."""
import csv, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(f"{HERE}/results/E1c_copy_rate.csv")))
S = ["northwind", "chinook", "pagila", "employees", "dellstore2", "classicmodels", "hr", "bikestores"]
NAME = {"northwind": "Northwind", "chinook": "Chinook", "pagila": "Pagila", "employees": "employees", "dellstore2": "Dell DVD Store 2",
        "classicmodels": "ClassicModels", "hr": "Oracle HR", "bikestores": "BikeStores"}
M = [("sonnet46", "Claude Sonnet 4.6"), ("sonnet55", "Claude Sonnet 5.5"), ("gpt4o", "GPT-4o"), ("gpt56terra", "GPT-5.6"), ("qwen3_235b", "Qwen3-235B")]
def get(s, m): return next((r for r in rows if r["schema"] == s and r["model_tag"] == m and r["run"] == "1"), None)
def pct(r, k): return "--" if r is None or r[k] in ("", None) else f"{100*float(r[k]):.1f}"
out = []
out.append("# E1c copy rate, direct arm, run 1: exact_text (share of emitted rows whose high-cardinality text fields occur verbatim in the fixture) / near90 / overlap")
out.append(f"{'schema':17s}" + "".join(f"{n:>22s}" for _, n in M))
for s in S:
    out.append(f"{NAME[s]:17s}" + "".join(f"{pct(get(s,m),'exact_text_pooled')+'/'+pct(get(s,m),'near90_pooled')+'/'+pct(get(s,m),'text_overlap_median'):>22s}" for m, _ in M))
thr = 0.01
out.append(f"\n# cells with exact_text >= {thr:.0%} (schema x model, run 1), by model:")
for m, n in M:
    cells = [s for s in S if get(s, m) and float(get(s, m)["exact_text_pooled"]) >= thr]
    tot = sum(1 for s in S if get(s, m))
    out.append(f"  {n:18s} {len(cells)}/{tot}: {', '.join(NAME[c] for c in cells)}")
out.append("# by schema:")
for s in S:
    cells = [n for m, n in M if get(s, m) and float(get(s, m)["exact_text_pooled"]) >= thr]
    out.append(f"  {NAME[s]:18s} {len(cells)}/{sum(1 for m,_ in M if get(s,m))}: {', '.join(cells)}")
# HR editions
he = json.load(open(f"{HERE}/results/hr_editions.json"))
out.append("\n# Oracle HR, employees table (107 rows), copy rate against three fixture editions (see hr_editions.py):")
out.append(f"{'model':18s} {'v23 exact_text':>15s} {'19c exact_text':>15s} {'19c exact_all':>14s} {'19c near90':>11s}")
for m, n in M:
    c = f"hr_{m}_r1"
    out.append(f"{n:18s} {100*he[c+'|v23 (current)']['exact_text_rate']:15.1f} {100*he[c+'|19c (2015-2019)']['exact_text_rate']:15.1f} {100*he[c+'|19c (2015-2019)']['exact_all_rate']:14.1f} {100*he[c+'|19c (2015-2019)']['near90_rate']:11.1f}")
# LaTeX
out.append("\n% ---- LaTeX: copy rate, 8 schemas x 5 models (exact_text %, near90 % in parentheses) ----")
out.append("\\begin{tabular}{l" + "r" * len(M) + "}\n\\toprule\nSchema & " + " & ".join(n for _, n in M) + " \\\\\n\\midrule")
for s in S:
    out.append(NAME[s] + " & " + " & ".join(f"{pct(get(s,m),'exact_text_pooled')} ({pct(get(s,m),'near90_pooled')})" for m, _ in M) + " \\\\")
out.append("\\bottomrule\n\\end{tabular}")
open(f"{HERE}/results/E1c_stats.txt", "w").write("\n".join(out) + "\n"); print("\n".join(out))
