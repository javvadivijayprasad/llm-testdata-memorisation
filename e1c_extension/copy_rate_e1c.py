#!/usr/bin/env python3
"""Copy-rate metrics for the E1c cells (arms/direct/<subject>_<tag>_r<run>) with the SAME metric code as
e1_datastudy/copy_rate.py (imported, not copied), plus the E1 direct cells of the original five schemas so that
one table holds every model x schema. Writes results/E1c_copy_rate.csv and results/copy_rate/<cell>.json.
usage: copy_rate_e1c.py"""
import csv, glob, json, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); E1 = os.path.abspath(os.path.join(HERE, "..", "e1_datastudy")) if os.path.isdir(os.path.join(HERE, "..", "e1_datastudy")) else os.path.abspath(os.path.join(HERE, "..", "e1"))
sys.path.insert(0, E1); sys.argv = [sys.argv[0]]            # copy_rate parses argv at import
import copy_rate as cr
M = {m["tag"]: m for m in json.load(open(f"{HERE}/models_e1c.json"))["models"]}
S = [s["name"] for s in json.load(open(f"{HERE}/schemas_e1c.json"))["schemas"]]
OUT = f"{HERE}/results"; os.makedirs(f"{OUT}/copy_rate", exist_ok=True)

def cells():
    for d in sorted(glob.glob(f"{HERE}/arms/direct/*")):
        m = re.match(r"(\w+?)_(" + "|".join(map(re.escape, M)) + r")_r(\d)$", os.path.basename(d))
        if m: yield m.group(1), m.group(2), int(m.group(3)), d
    for d in sorted(glob.glob(f"{E1}/arms/pc/direct/*")) + sorted(glob.glob(f"{E1}/arms/direct/*")):   # E1 cells (either layout)
        m = re.match(r"(\w+?)_(anthropic|openai)_r(\d)$", os.path.basename(d))
        if m: yield m.group(1), {"anthropic": "sonnet46", "openai": "gpt4o"}[m.group(2)], int(m.group(3)), d

seen = set(); rows = []
for schema, tag, run, d in cells():
    if schema not in S or (schema, tag, run) in seen: continue
    seen.add((schema, tag, run))
    ddl = cr.parse_ddl(schema); per_table = {}
    for t, ti in ddl.items():
        f = os.path.join(d, f"{t}.csv"); hf = f"{E1}/human_cache/{schema}/{t}.csv"
        if not (os.path.exists(f) and os.path.exists(hf)): continue
        r = cr.table_metrics(cr.read_rows(hf), cr.read_rows(f), ti["cols"], ti["surrogate"], ti["fks"])
        if r: per_table[t] = r
    if not per_table: continue
    tot = sum(v["rows"] for v in per_table.values()); tt = {t: v for t, v in per_table.items() if v["text_cols"]}
    tot_t = sum(v["rows"] for v in tt.values())
    pooled = lambda k, dd, n: round(sum(v[k] for v in dd.values()) / n, 4) if n else ""
    med = lambda k, dd: round(float(np.median([v[k] for v in dd.values()])), 4) if dd else ""
    ovl = [v["text_overlap"] for v in tt.values() if v["text_overlap"] is not None]
    label = f"{schema}_{tag}_r{run}"; json.dump(per_table, open(f"{OUT}/copy_rate/{label}.json", "w"), indent=1)
    rows.append({"schema": schema, "model_tag": tag, "model": M[tag]["model"], "provider": M[tag]["provider"], "run": run,
                 "tables": len(per_table), "rows": tot, "text_tables": len(tt), "text_rows": tot_t,
                 "exact_all_pooled": pooled("exact_all", per_table, tot), "exact_text_pooled": pooled("exact_text", tt, tot_t),
                 "near90_pooled": pooled("near90", tt, tot_t), "near80_pooled": pooled("near80", tt, tot_t),
                 "exact_text_median": med("exact_text_rate", tt), "near90_median": med("near90_rate", tt),
                 "text_overlap_median": round(float(np.median(ovl)), 4) if ovl else ""})
    r = rows[-1]; print(f"{label:32s} rows={tot:5d} exact_text={r['exact_text_pooled']} near90={r['near90_pooled']} ovl={r['text_overlap_median']}", flush=True)
rows.sort(key=lambda r: (r["schema"], r["model_tag"], r["run"]))
with open(f"{OUT}/E1c_copy_rate.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("wrote", f"{OUT}/E1c_copy_rate.csv", len(rows), "cells")
