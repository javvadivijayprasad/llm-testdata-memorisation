#!/usr/bin/env python3
"""Cost table (tokens, calls, wall time) per arm and provider over the E1 cells; medians with min-max.
Source: e1_datastudy/results/E1_cells.csv. usage: cost_table.py <E1_cells.csv>"""
import csv, sys, statistics as st
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["arm"] in ("plan", "direct") and r["input_tokens"] not in ("", None)]
def f(v): return f"{v:,.0f}"
print(r"\begin{tabular}{llrrrrr}"); print(r"\toprule")
print(r"Arm & Provider & Cells & Calls & Input tokens & Output tokens & Wall time (s) \\"); print(r"\midrule")
for arm, an in (("plan", "Plan-then-execute"), ("direct", "Direct emission")):
    for prov, pn in (("anthropic", "Claude"), ("openai", "GPT-4o")):
        rs = [r for r in rows if r["arm"] == arm and r["provider"] == prov]
        c = [int(r["llm_calls"]) for r in rs]; ti = [int(r["input_tokens"]) for r in rs]; to = [int(r["output_tokens"]) for r in rs]; la = [float(r["latency_ms"]) / 1000 for r in rs]
        cell = lambda v: f"{f(st.median(v))} ({f(min(v))}--{f(max(v))})"
        print(f"{an if prov == 'anthropic' else ''} & {pn} & {len(rs)} & {cell(c)} & {cell(ti)} & {cell(to)} & {cell(la)} \\\\")
print(r"\midrule")
for arm, an in (("plan", "Plan, total"), ("direct", "Direct, total")):
    rs = [r for r in rows if r["arm"] == arm]
    print(f"{an} & both & {len(rs)} & {f(sum(int(r['llm_calls']) for r in rs))} & {f(sum(int(r['input_tokens']) for r in rs))} & {f(sum(int(r['output_tokens']) for r in rs))} & {f(sum(float(r['latency_ms'])/1000 for r in rs))} \\\\")
print(r"\bottomrule"); print(r"\end{tabular}")
