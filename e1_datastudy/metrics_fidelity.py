#!/usr/bin/env python3
"""Fidelity / coverage metrics of one arm's output against the human fixtures of the same schema
(RQ2, RQ3). Works on the emitted CSVs (validity is score_load.py's job).

Per table: emitted/target ratio.
Per column (using the canonical DDL types):
  - categorical columns = enum/CHECK-IN columns, booleans, and text columns whose HUMAN data has
    <= 30 distinct values (e.g. rating, order_status, country_code): Jensen-Shannon distance (base 2,
    0 = identical distribution, 1 = disjoint supports) between human and arm value frequencies;
    plus enum coverage = |arm values ∩ human values| / |human values|.
  - numeric (int/numeric/real) and date/timestamp columns: two-sample Kolmogorov-Smirnov statistic
    (0 = same distribution, 1 = disjoint), dates as ordinal days; plus range coverage = fraction of
    the human [min,max] span covered by the arm's [min,max].
  - nullable columns: null rate in arm vs human (abs difference).
  - FK columns: fan-out Gini (concentration of child rows over parent keys) arm vs human (abs diff).
Aggregates: medians per metric class over all columns/tables of the schema.
usage: metrics_fidelity.py <subject> <csv_dir> <out.json>   (human data read from <subject>_canon)"""
import csv, json, os, re, subprocess, sys, datetime, math
from collections import Counter
import numpy as np
from scipy.stats import ks_2samp
from scipy.spatial.distance import jensenshannon

subject, csv_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
HERE = os.path.dirname(os.path.abspath(__file__))
ddl = open(f"{HERE}/ddl/{subject}.canonical.sql").read()
targets = json.load(open(f"{HERE}/row_targets.json"))[subject]
tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
HUMAN_DB = f"{subject}_canon"
CACHE = f"{HERE}/human_cache/{subject}"
os.makedirs(CACHE, exist_ok=True)

def table_block(t): return re.search(rf"^CREATE TABLE {t} \((.*?)^\);", ddl, re.M | re.S).group(1)
def columns(t):
    cols = {}
    for line in table_block(t).splitlines():
        line = line.strip().rstrip(",")
        if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
        parts = line.split()
        m = re.search(r"CHECK \(\w+ IN \((.*?)\)\)", line)
        cols[parts[0]] = {"type": parts[1].lower(), "notnull": "NOT NULL" in line,
                          "enum": [v.strip().strip("'") for v in m.group(1).split(",")] if m else None}
    fks = {c: (p, pc) for c, p, pc in re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", table_block(t))}
    pk = re.search(r"PRIMARY KEY \(([^)]*)\)", table_block(t)); pks = [c.strip() for c in pk.group(1).split(",")] if pk else []
    return cols, fks, pks

def human_rows(t):
    """Human fixture rows for table t as list of dicts (cached CSV export from <subject>_canon;
    capped at 50,000 rows sampled by primary key order for the large employees tables)."""
    f = f"{CACHE}/{t}.csv"
    if not os.path.exists(f):
        subprocess.run(["psql", "-d", HUMAN_DB, "-Atc", f"\\copy (select * from {t} limit 50000) to '{f}' with (format csv, header true)"],
                       check=True, capture_output=True)
    return list(csv.DictReader(open(f, newline="", encoding="utf-8", errors="replace")))

def arm_rows(t):
    f = os.path.join(csv_dir, f"{t}.csv")
    if not os.path.exists(f): return None
    return list(csv.DictReader(open(f, newline="", encoding="utf-8", errors="replace")))

def to_num(v, typ):
    if v is None or v == "": return None
    try:
        if typ == "date": return datetime.date.fromisoformat(v[:10]).toordinal()
        if typ.startswith("timestamp"): return datetime.datetime.fromisoformat(v[:19].replace("T", " ")).toordinal()
        if typ == "boolean": return 1.0 if v.lower() in ("true", "t", "1") else 0.0
        return float(v)
    except Exception: return None

def gini(counts):
    x = np.sort(np.array(counts, dtype=float))
    if x.sum() == 0 or len(x) < 2: return 0.0
    n = len(x); return float((2 * np.sum((np.arange(1, n + 1)) * x) / (n * x.sum())) - (n + 1) / n)

report = {"subject": subject, "csv_dir": csv_dir, "tables": {}, "columns": []}
for t in tables:
    if targets[t]["target"] == 0: continue
    cols, fks, pks = columns(t)
    H = human_rows(t); A = arm_rows(t)
    rep = {"target": targets[t]["target"], "emitted": len(A) if A is not None else 0}
    rep["emitted_ratio"] = round(rep["emitted"] / rep["target"], 3)
    report["tables"][t] = rep
    if not A: continue
    for c, meta in cols.items():
        if c in pks and len(pks) == 1: continue                      # surrogate keys: skip
        hv = [r.get(c, "") for r in H]; av = [r.get(c, "") for r in A]
        if all(v == "" for v in av) and not all(v == "" for v in hv) and not meta["notnull"]:
            pass
        entry = {"table": t, "column": c, "type": meta["type"]}
        # null rates
        hn = sum(1 for v in hv if v == "") / max(1, len(hv)); an = sum(1 for v in av if v == "") / max(1, len(av))
        entry["null_rate_human"] = round(hn, 3); entry["null_rate_arm"] = round(an, 3)
        hv_nn = [v for v in hv if v != ""]; av_nn = [v for v in av if v != ""]
        if meta["type"] == "boolean":
            # normalise boolean spellings: psql exports 't'/'f', arms emit 'true'/'false'/'1'/'0'
            # (without this the JS distance of every boolean column is 1.0 by representation alone)
            norm = lambda v: "true" if v.strip().lower() in ("t", "true", "1", "yes") else ("false" if v.strip().lower() in ("f", "false", "0", "no") else v)
            hv_nn = [norm(v) for v in hv_nn]; av_nn = [norm(v) for v in av_nn]
        # FK fan-out
        if c in fks:
            entry["metric_class"] = "fk_fanout"
            entry["gini_human"] = round(gini(list(Counter(hv_nn).values())), 3)
            entry["gini_arm"] = round(gini(list(Counter(av_nn).values())), 3)
            entry["gini_absdiff"] = round(abs(entry["gini_human"] - entry["gini_arm"]), 3)
            report["columns"].append(entry); continue
        typ = meta["type"]
        is_num = bool(re.match(r"integer|bigint|smallint|numeric|real|double|date|timestamp|boolean", typ))
        hdist = len(set(hv_nn))
        categorical = meta["enum"] is not None or typ == "boolean" or (not is_num and hdist <= 30 and hdist > 0)
        if categorical:
            entry["metric_class"] = "categorical"
            support = sorted(set(hv_nn) | set(av_nn))
            hc, ac = Counter(hv_nn), Counter(av_nn)
            p = np.array([hc[s] for s in support], dtype=float); q = np.array([ac[s] for s in support], dtype=float)
            if p.sum() and q.sum():
                entry["js_distance"] = round(float(jensenshannon(p / p.sum(), q / q.sum(), base=2)), 3)
            hset = set(hv_nn); entry["value_coverage"] = round(len(hset & set(av_nn)) / len(hset), 3) if hset else None
            if meta["enum"]:
                entry["enum_coverage"] = round(len(set(meta["enum"]) & set(av_nn)) / len(meta["enum"]), 3)
        elif is_num:
            entry["metric_class"] = "numeric"
            hnum = [x for x in (to_num(v, typ) for v in hv_nn) if x is not None]
            anum = [x for x in (to_num(v, typ) for v in av_nn) if x is not None]
            entry["parse_rate_arm"] = round(len(anum) / max(1, len(av_nn)), 3)
            if len(hnum) >= 2 and len(anum) >= 2:
                entry["ks_statistic"] = round(float(ks_2samp(hnum, anum).statistic), 3)
                lo, hi = min(hnum), max(hnum); alo, ahi = min(anum), max(anum)
                span = hi - lo
                entry["range_coverage"] = round(max(0.0, (min(hi, ahi) - max(lo, alo)) / span), 3) if span > 0 else (1.0 if alo <= lo <= ahi else 0.0)
                entry["human_range"] = [lo, hi]; entry["arm_range"] = [alo, ahi]
        else:
            entry["metric_class"] = "free_text"
            entry["distinct_ratio_human"] = round(hdist / max(1, len(hv_nn)), 3)
            entry["distinct_ratio_arm"] = round(len(set(av_nn)) / max(1, len(av_nn)), 3)
            entry["mean_len_human"] = round(float(np.mean([len(v) for v in hv_nn])), 1) if hv_nn else None
            entry["mean_len_arm"] = round(float(np.mean([len(v) for v in av_nn])), 1) if av_nn else None
        report["columns"].append(entry)

def med(key, cls=None):
    vals = [c[key] for c in report["columns"] if key in c and c[key] is not None and (cls is None or c.get("metric_class") == cls)]
    return (round(float(np.median(vals)), 3), len(vals)) if vals else (None, 0)
report["aggregate"] = {
    "emitted_ratio_median": round(float(np.median([v["emitted_ratio"] for v in report["tables"].values()])), 3) if report["tables"] else None,
    "js_distance_median": med("js_distance"), "value_coverage_median": med("value_coverage"),
    "js_declared_median": (lambda v: (round(float(np.median(v)), 3), len(v)) if v else (None, 0))([c["js_distance"] for c in report["columns"] if c.get("metric_class") == "categorical" and c.get("js_distance") is not None and (c.get("enum_coverage") is not None or c["type"] == "boolean")]),
    "js_freetext_median": (lambda v: (round(float(np.median(v)), 3), len(v)) if v else (None, 0))([c["js_distance"] for c in report["columns"] if c.get("metric_class") == "categorical" and c.get("js_distance") is not None and not (c.get("enum_coverage") is not None or c["type"] == "boolean")]),
    "enum_coverage_median": med("enum_coverage"), "ks_statistic_median": med("ks_statistic"),
    "range_coverage_median": med("range_coverage"), "fk_gini_absdiff_median": med("gini_absdiff"),
    "null_rate_absdiff_median": (round(float(np.median([abs(c["null_rate_human"] - c["null_rate_arm"]) for c in report["columns"]])), 3) if report["columns"] else None),
}
json.dump(report, open(out_path, "w"), indent=1)
print(json.dumps(report["aggregate"]))
