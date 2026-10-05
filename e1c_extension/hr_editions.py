#!/usr/bin/env python3
"""HR edition check (E1c): the Oracle HR fixture was revised in schema version 21 (2021; names, phones, emails
and dates changed again by v23), so a model that memorised the long-published 12c/19c edition (identical data,
2015-2019; itself the 11g edition with every date shifted +16 years) scores zero against the current fixture.
Scores every hr cell against the current edition (human_cache/hr, v23.3) and the 19c edition (human_cache/hr_v19),
and, for the 11g edition which is not in the GitHub history, the same 19c rows with dates shifted back 16 years.
Same metric code as copy_rate.py."""
import csv, glob, json, os, re, sys, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); E1 = os.path.abspath(os.path.join(HERE, "..", "e1"))
sys.path.insert(0, E1); sys.argv = [sys.argv[0]]; import copy_rate as cr
ddl = cr.parse_ddl("hr")
def shift16(rows):
    out = []
    for r in rows:
        r = dict(r)
        for c in ("hire_date", "start_date", "end_date"):
            if r.get(c):
                d = datetime.date.fromisoformat(r[c][:10]); r[c] = d.replace(year=d.year - 16).isoformat()
        out.append(r)
    return out
eds = {"v23 (current)": lambda t: cr.read_rows(f"{E1}/human_cache/hr/{t}.csv"),
       "19c (2015-2019)": lambda t: cr.read_rows(f"{E1}/human_cache/hr_v19/{t}.csv"),
       "11g (19c dates -16y)": lambda t: shift16(cr.read_rows(f"{E1}/human_cache/hr_v19/{t}.csv"))}
print(f"{'cell':22s} {'edition':22s} {'table':12s} {'rows':>5s} {'exact_all':>9s} {'exact_text':>10s} {'near90':>7s} {'overlap':>8s}")
res = {}
for d in sorted(glob.glob(f"{HERE}/arms/direct/hr_*_r1")):
    cell = os.path.basename(d)
    for ed, get in eds.items():
        for t in ("employees",):
            r = cr.table_metrics(get(t), cr.read_rows(f"{d}/{t}.csv"), ddl[t]["cols"], ddl[t]["surrogate"], ddl[t]["fks"])
            res[(cell, ed)] = r
            print(f"{cell:22s} {ed:22s} {t:12s} {r['rows']:5d} {r['exact_all_rate']:9.3f} {r['exact_text_rate']:10.3f} {r['near90_rate']:7.3f} {r['text_overlap']:8.3f}")
json.dump({f"{k[0]}|{k[1]}": v for k, v in res.items()}, open(f"{HERE}/results/hr_editions.json", "w"), indent=1)
