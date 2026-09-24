#!/usr/bin/env python3
"""Rebuild results/E1_cells.csv and results/E1b_renamed_vs_original.csv from the per-cell score
files (scores/), metric files (metrics/) and arm run logs (arms/). No database, no LLM.

E1 cells:  plan|direct  x  5 schemas  x  {anthropic, openai}  x  run {1,2}   (scores/pc, metrics/pc, arms/pc)
           auto (every scored engine version), faker, human                  (scores/*.json, metrics/*.json)
E1b cells: plan_r|direct_r x 5 renamed schemas x provider, run 1              (scores/pc_r, metrics/pc_r)
           paired with the original run-1 cell of the same arm/schema/provider.

usage: build_cells.py            (writes both CSVs; prints a diff summary against the existing files)
"""
import csv, glob, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
SUBJECTS = ["chinook", "dellstore2", "employees", "northwind", "pagila"]
VIOL = ["fk", "unique", "check", "not_null", "type"]
MET = ["js_median", "ks_median", "value_cov_median", "range_cov_median", "fk_gini_absdiff_median", "js_declared_median", "js_freetext_median"]
METKEY = {"js_median": "js_distance_median", "ks_median": "ks_statistic_median", "value_cov_median": "value_coverage_median",
          "range_cov_median": "range_coverage_median", "fk_gini_absdiff_median": "fk_gini_absdiff_median",
          "js_declared_median": "js_declared_median", "js_freetext_median": "js_freetext_median"}
HEADER = ["arm", "subject", "provider", "run", "status", "emitted", "loaded", "load_rate"] + VIOL + \
         ["llm_calls", "input_tokens", "output_tokens", "latency_ms"] + MET


def score(path):
    a = json.load(open(path))["aggregate"]
    v = a.get("violations", {})
    return {"emitted": a["emitted"], "loaded": a["loaded"], "load_rate": a["load_rate"], **{k: v.get(k, 0) for k in VIOL}}


def metrics(path):
    if not os.path.exists(path):
        return {k: "" for k in MET}
    a = json.load(open(path))["aggregate"]
    out = {}
    for k in MET:
        val = a.get(METKEY[k])
        out[k] = "" if val is None or val[0] is None else val[0]
    return out


def tokens(arm, subject, provider, run, renamed=False):
    base = "arms/pc_r" if renamed else "arms/pc"
    sub = subject
    if arm == "plan":
        d = f"{base}/{'plan_r' if renamed else 'plan'}/{sub}_{provider}_r{run}/log.json"
        if not os.path.exists(d):
            return None
        L = json.load(open(d))
        status = "engine_abort" if L.get("generate_rc") not in (0, None) else "ok"
        return {"status": status, "llm_calls": 1, "input_tokens": L["input_tokens"], "output_tokens": L["output_tokens"], "latency_ms": L["latency_ms"]}
    d = f"{base}/direct_utf8/{sub}_{provider}_r{run}/log.json"
    if not os.path.exists(d):
        return None
    L = json.load(open(d)); T = L["totals"]
    ok_calls = sum(1 for c in L["calls"] if not c.get("error"))     # failed HTTP calls (no tokens) are not counted
    return {"status": "ok", "llm_calls": ok_calls, "input_tokens": T["input_tokens"], "output_tokens": T["output_tokens"], "latency_ms": T["latency_ms"]}


def row(arm, subject, provider, run, sc, mt, tk):
    r = {"arm": arm, "subject": subject, "provider": provider, "run": run}
    r.update(tk or {"status": "ok", "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0})
    r.update(sc)
    if r["status"] == "engine_abort":
        r.update({"emitted": 0, "loaded": 0, "load_rate": 0.0, **{k: 0 for k in VIOL}})
        mt = {k: "" for k in MET}
    r.update(mt)
    return r


rows = []
for arm in ["plan", "direct"]:
    for s in SUBJECTS:
        for p in ["anthropic", "openai"]:
            for run in ["1", "2"]:
                sp = f"scores/pc/{arm}_{s}_{p}_r{run}.json"
                tk = tokens(arm, s, p, run)
                if not os.path.exists(sp):
                    if tk and tk["status"] == "engine_abort":      # aborted plan run: no CSVs, no score file
                        rows.append(row(arm, s, p, run, {"emitted": 0, "loaded": 0, "load_rate": 0.0, **{k: 0 for k in VIOL}}, {k: "" for k in MET}, tk))
                    continue
                rows.append(row(arm, s, p, run, score(sp), metrics(f"metrics/pc/{arm}_{s}_{p}_r{run}.json"), tk))
for f in sorted(glob.glob("scores/auto*.json")):
    n = os.path.basename(f)[:-5]
    if n.endswith("_r") or n.endswith("_check"):
        continue
    subj = n[len("auto_"):]
    rows.append(row("auto", subj, "-", "-", score(f), metrics(f"metrics/{n}.json"), None))
for f in sorted(glob.glob("scores/faker_*.json")):
    n = os.path.basename(f)[:-5]
    rows.append(row("faker", n[len("faker_"):], "-", "-", score(f), metrics(f"metrics/{n}.json"), None))
for f in sorted(glob.glob("scores/human_*.json")):
    n = os.path.basename(f)[:-5]
    if n.endswith("_r") or n.startswith("human_cache"):
        continue
    rows.append(row("human", n[len("human_"):], "-", "-", score(f), {k: "" for k in MET}, None))

order = {"plan": 0, "direct": 1, "auto": 2, "faker": 3, "human": 4}
rows.sort(key=lambda r: (order[r["arm"]], r["subject"], r["provider"], r["run"]))
old = list(csv.DictReader(open("results/E1_cells.csv"))) if os.path.exists("results/E1_cells.csv") else []
with open("results/E1_cells.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=HEADER)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in HEADER})
print(f"E1_cells.csv: {len(rows)} rows (previous file: {len(old)})")
# diff against the previous file on the columns it had
if old:
    om = {(r["arm"], r["subject"], r["provider"], r["run"]): r for r in old}
    nd = 0
    for r in rows:
        o = om.get((r["arm"], r["subject"], r["provider"], r["run"]))
        if not o:
            print("  new cell:", r["arm"], r["subject"], r["provider"], r["run"]); nd += 1; continue
        for k in old[0].keys():
            if k in HEADER and str(o[k]) != str(r.get(k, "")):
                try:
                    if abs(float(o[k]) - float(r[k])) < 1e-9:
                        continue
                except Exception:
                    pass
                print(f"  DIFF {r['arm']} {r['subject']} {r['provider']} r{r['run']} {k}: {o[k]} -> {r.get(k,'')}"); nd += 1
    print("  differences vs previous E1_cells.csv:", nd)

# ---- E1b
E1B = ["arm", "subject", "provider", "load_orig", "load_renamed", "js_orig", "js_renamed", "valcov_orig", "valcov_renamed",
       "ks_orig", "ks_renamed", "rangecov_orig", "rangecov_renamed", "gini_orig", "gini_renamed", "status_orig", "status_renamed",
       "jsdecl_orig", "jsdecl_renamed", "jsfree_orig", "jsfree_renamed"]
orig = {(r["arm"], r["subject"], r["provider"]): r for r in rows if r["run"] == "1"}
b = []
for arm in ["plan", "direct"]:
    for s in SUBJECTS:
        for p in ["anthropic", "openai"]:
            sp = f"scores/pc_r/{arm}_r_{s}_r_{p}_r1.json"
            tk = tokens(arm, f"{s}_r", p, "1", renamed=True)
            if not os.path.exists(sp):
                if not (tk and tk["status"] == "engine_abort"):
                    continue
                rn = row(arm, s, p, "1", {"emitted": 0, "loaded": 0, "load_rate": 0.0, **{k: 0 for k in VIOL}}, {k: "" for k in MET}, tk)
            else:
                rn = row(arm, s, p, "1", score(sp), metrics(f"metrics/pc_r/{arm}_r_{s}_r_{p}_r1.json"), tk)
            o = orig[(arm, s, p)]
            b.append({"arm": arm, "subject": s, "provider": p,
                      "load_orig": o["load_rate"], "load_renamed": rn["load_rate"],
                      "js_orig": o["js_median"], "js_renamed": rn["js_median"],
                      "valcov_orig": o["value_cov_median"], "valcov_renamed": rn["value_cov_median"],
                      "ks_orig": o["ks_median"], "ks_renamed": rn["ks_median"],
                      "rangecov_orig": o["range_cov_median"], "rangecov_renamed": rn["range_cov_median"],
                      "gini_orig": o["fk_gini_absdiff_median"], "gini_renamed": rn["fk_gini_absdiff_median"],
                      "status_orig": o["status"], "status_renamed": rn["status"],
                      "jsdecl_orig": o["js_declared_median"], "jsdecl_renamed": rn["js_declared_median"],
                      "jsfree_orig": o["js_freetext_median"], "jsfree_renamed": rn["js_freetext_median"]})
oldb = list(csv.DictReader(open("results/E1b_renamed_vs_original.csv"))) if os.path.exists("results/E1b_renamed_vs_original.csv") else []
with open("results/E1b_renamed_vs_original.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=E1B)
    w.writeheader()
    for r in b:
        w.writerow(r)
print(f"E1b_renamed_vs_original.csv: {len(b)} rows (previous file: {len(oldb)})")
if oldb:
    om = {(r["arm"], r["subject"], r["provider"]): r for r in oldb}
    nd = 0
    for r in b:
        o = om.get((r["arm"], r["subject"], r["provider"]))
        if not o:
            print("  new E1b cell:", r["arm"], r["subject"], r["provider"]); nd += 1; continue
        for k in oldb[0].keys():
            if k in E1B and str(o[k]) != str(r[k]):
                try:
                    if abs(float(o[k]) - float(r[k])) < 1e-9:
                        continue
                except Exception:
                    pass
                print(f"  DIFF {r['arm']} {r['subject']} {r['provider']} {k}: {o[k]} -> {r[k]}"); nd += 1
    print("  differences vs previous E1b file:", nd)
