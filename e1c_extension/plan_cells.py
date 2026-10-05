#!/usr/bin/env python3
"""Print the E1c cells to run, one per line: subject provider model tag run. Skips (E1 model x E1 schema)
cells, which E1 already holds, and cells whose log.json says every table reached its target."""
import json, os, re, csv, io
HERE = os.path.dirname(os.path.abspath(__file__)); E1 = os.path.join(HERE, "..", "e1_datastudy")
M = json.load(open(f"{HERE}/models_e1c.json"))["models"]; S = json.load(open(f"{HERE}/schemas_e1c.json"))["schemas"]
rt = json.load(open(f"{E1}/row_targets.json"))
def complete(d, subject):
    if not os.path.exists(f"{d}/log.json"): return False
    for t, v in rt[subject].items():
        f = f"{d}/{t}.csv"
        if not os.path.exists(f): return False
        n = sum(1 for _ in csv.reader(io.StringIO(open(f, encoding="utf-8", errors="replace").read()))) - 1
        if n < v["target"]: return False
    return True
order = [s for s in S if not s["e1"]] + [s for s in S if s["e1"]]
for s in order:
    for m in M:
        if m["model"].startswith("FILL-"): continue
        if s["e1"] and m["e1"]: continue
        if s["name"] not in rt: continue          # not registered yet (make_subject.py)
        for run in (1, 2):
            if complete(f"{HERE}/arms/direct/{s['name']}_{m['tag']}_r{run}", s["name"]): continue
            print(s["name"], m["provider"], m["model"], m["tag"], run)
