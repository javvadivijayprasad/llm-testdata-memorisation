#!/usr/bin/env python3
"""Statistics quoted in the manuscript beyond the raw cell tables (draft 2, 17 Sep 2026).
Reads e1_datastudy/results/E1_cells.csv, E1b_renamed_vs_original.csv and e2_raitg_data/results/E2_pairwise_vs_G.csv.
Prints every number with the label used in NUMBER_TRACE.md. No randomness except the seeded bootstrap.
usage: stats_paper.py [path-to-exp-root]   (default: ../exp; or the artifact root, which holds e1_datastudy/ and e2_raitg_data/)"""
import csv, sys, os, statistics as st
import numpy as np
from scipy.stats import wilcoxon
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "exp")
# working tree uses exp/e1, exp/e2; the Zenodo artifact uses e1_datastudy, e2_raitg_data
D1 = f"{ROOT}/e1" if os.path.isdir(f"{ROOT}/e1") else f"{ROOT}/e1_datastudy"
D2 = f"{ROOT}/e2" if os.path.isdir(f"{ROOT}/e2") else f"{ROOT}/e2_raitg_data"
E1 = list(csv.DictReader(open(f"{D1}/results/E1_cells.csv")))
E1B = list(csv.DictReader(open(f"{D1}/results/E1b_renamed_vs_original.csv")))
E2 = list(csv.DictReader(open(f"{D2}/results/E2_pairwise_vs_G.csv")))
rng = np.random.default_rng(42)


def f(x):
    return None if x in ("", None) else float(x)


def boot_median_diff(d, n=10000):
    d = np.array(d, dtype=float)
    meds = [np.median(rng.choice(d, len(d), replace=True)) for _ in range(n)]
    return np.median(d), np.percentile(meds, 2.5), np.percentile(meds, 97.5)


def cliffs_delta(a, b):
    a, b = np.array(a), np.array(b)
    more = sum((x > y) for x in a for y in b); less = sum((x < y) for x in a for y in b)
    return (more - less) / (len(a) * len(b))


def wil(a, b):
    a, b = np.array(a), np.array(b)
    d = a - b
    if np.all(d == 0):
        return 1.0
    return wilcoxon(a, b, zero_method="wilcox").pvalue


print("=== E1 validity (RQ1): plan vs direct, paired over (schema, provider, run) cells ===")
cells = {}
for r in E1:
    if r["arm"] in ("plan", "direct") and r["provider"] != "-":
        cells.setdefault((r["subject"], r["provider"], r["run"]), {})[r["arm"]] = r
keys = sorted(cells)
plan = [f(cells[k]["plan"]["load_rate"]) for k in keys]; direct = [f(cells[k]["direct"]["load_rate"]) for k in keys]
print(f"E1-N: n = {len(keys)} paired cells")
print(f"E1-MEAN-ALL: plan mean {np.mean(plan):.3f} median {np.median(plan):.3f} | direct mean {np.mean(direct):.3f} median {np.median(direct):.3f} | Wilcoxon p = {wil(plan, direct):.2f}")
d = np.array(plan) - np.array(direct)
m, lo, hi = boot_median_diff(d)
print(f"E1-DIFF-ALL: paired median difference plan-direct {m:+.3f} [95% CI {lo:+.3f}, {hi:+.3f}]; mean difference {np.mean(d):+.3f}; Cliff's delta {cliffs_delta(plan, direct):+.2f}")
ex = [k for k in keys if cells[k]["plan"]["status"] == "ok"]
p2 = [f(cells[k]["plan"]["load_rate"]) for k in ex]; d2 = [f(cells[k]["direct"]["load_rate"]) for k in ex]
dd = np.array(p2) - np.array(d2); m, lo, hi = boot_median_diff(dd)
print(f"E1-MEAN-EXEC: excluding {len(keys)-len(ex)} engine aborts (n = {len(ex)}): plan mean {np.mean(p2):.3f} | direct mean {np.mean(d2):.3f} | Wilcoxon p = {wil(p2, d2):.2f}; paired median diff {m:+.3f} [{lo:+.3f}, {hi:+.3f}]; Cliff's delta {cliffs_delta(p2, d2):+.2f}")
# schema-level sensitivity: average the four cells (2 providers x 2 runs) per schema first
sch = {}
for k in keys:
    sch.setdefault(k[0], []).append((f(cells[k]["plan"]["load_rate"]), f(cells[k]["direct"]["load_rate"])))
ps = [np.mean([x[0] for x in v]) for s, v in sorted(sch.items())]; ds = [np.mean([x[1] for x in v]) for s, v in sorted(sch.items())]
print(f"E1-SCHEMA: schema-level (n = {len(ps)}): plan {[round(x,3) for x in ps]} direct {[round(x,3) for x in ds]}; Wilcoxon p = {wil(ps, ds):.2f}")
print(f"E1-PLAN-100: plan cells at exactly 100%: {sum(1 for x in p2 if x == 1.0)} of {len(p2)} executed")
print(f"E1-DIRECT-100: direct cells at 100%: {sum(1 for x in direct if x == 1.0)} of {len(direct)} (schemas: {[k[0] for k in keys if f(cells[k]['direct']['load_rate']) == 1.0]})")
viol = {a: {v: sum(int(cells[k][a][v]) for k in keys) for v in ("fk", "unique", "check", "not_null", "type")} for a in ("plan", "direct")}
print(f"E1-VIOL: plan {viol['plan']} | direct {viol['direct']}")
tok = {a: [int(cells[k][a]["input_tokens"]) + int(cells[k][a]["output_tokens"]) for k in keys] for a in ("plan", "direct")}
calls = sorted(int(cells[k]["direct"]["llm_calls"]) for k in keys)
lat = {a: [int(cells[k][a]["latency_ms"]) / 1000 for k in keys] for a in ("plan", "direct")}
print(f"E1-TOKENS: plan median {np.median(tok['plan']):.0f} | direct median {np.median(tok['direct']):.0f} | ratio {np.median(tok['direct'])/np.median(tok['plan']):.1f}x; direct calls {calls[0]}-{calls[-1]}; wall median plan {np.median(lat['plan']):.0f}s direct {np.median(lat['direct']):.0f}s (max direct {max(lat['direct'])/60:.0f} min)")
print(f"E1-TOKENS-TOTAL: plan in {sum(int(cells[k]['plan']['input_tokens']) for k in keys)/1e3:.0f}k out {sum(int(cells[k]['plan']['output_tokens']) for k in keys)/1e3:.0f}k | direct in {sum(int(cells[k]['direct']['input_tokens']) for k in keys)/1e3:.0f}k out {sum(int(cells[k]['direct']['output_tokens']) for k in keys)/1e3:.0f}k")

print("\n=== E1 fidelity (RQ2) before the control, paired over executed cells ===")
for met, label in (("js_median", "JS categorical"), ("value_cov_median", "value coverage"), ("ks_median", "KS numeric/date"), ("range_cov_median", "range coverage"), ("fk_gini_absdiff_median", "FK Gini |diff|"), ("js_declared_median", "JS declared-domain cols"), ("js_freetext_median", "JS free-text cols (<=30 human values)")):
    pa, da = [], []
    for k in ex:
        x, y = f(cells[k]["plan"][met]), f(cells[k]["direct"][met])
        if x is not None and y is not None:
            pa.append(x); da.append(y)
    if pa:
        print(f"E1-FID {label}: plan median {np.median(pa):.3f} | direct median {np.median(da):.3f} | n = {len(pa)} | Wilcoxon p = {wil(pa, da):.3f} | Cliff's delta {cliffs_delta(pa, da):+.2f}")

print("\n=== E1 run-to-run noise floor of the direct arm's categorical JS (original schemas) ===")
noise = []
for s in sorted(set(k[0] for k in keys)):
    for p in ("anthropic", "openai"):
        a, b = cells.get((s, p, "1")), cells.get((s, p, "2"))
        if a and b and f(a["direct"]["js_median"]) is not None and f(b["direct"]["js_median"]) is not None:
            noise.append(abs(f(a["direct"]["js_median"]) - f(b["direct"]["js_median"])))
print(f"E1-NOISE: |JS run1 - run2| over {len(noise)} (schema, provider) pairs: median {np.median(noise):.3f}, max {max(noise):.3f}")

print("\n=== E1b renamed-schema control (direct arm) ===")
D = [r for r in E1B if r["arm"] == "direct"]
for met, label in (("load", "load rate"), ("js", "JS categorical"), ("valcov", "value coverage"), ("ks", "KS"), ("rangecov", "range coverage"), ("jsdecl", "JS declared-domain"), ("jsfree", "JS free-text")):
    o = [f(r[f"{met}_orig"]) for r in D]; n = [f(r[f"{met}_renamed"]) for r in D]
    pairs = [(x, y) for x, y in zip(o, n) if x is not None and y is not None]
    if not pairs:
        continue
    o, n = zip(*pairs)
    dd = np.array(n) - np.array(o); m, lo, hi = boot_median_diff(dd)
    print(f"E1B {label}: orig median {np.median(o):.3f} mean {np.mean(o):.3f} | renamed median {np.median(n):.3f} mean {np.mean(n):.3f} | n = {len(o)} | Wilcoxon p = {wil(list(n), list(o)):.3f} | median delta {m:+.3f} [{lo:+.3f}, {hi:+.3f}]")
print("E1B-PER-CELL JS deltas (renamed - orig):")
for r in D:
    x, y = f(r["js_orig"]), f(r["js_renamed"])
    print(f"   {r['subject']:11}{r['provider']:10} {x:.3f} -> {y:.3f}  delta {y-x:+.3f}")
pub = [r for r in D if r["subject"] in ("chinook", "northwind", "pagila")]
np_ = [r for r in D if r["subject"] == "dellstore2"]
print(f"E1B-PUBLISHED: JS delta on the three widely mirrored schemas, Claude: {[round(f(r['js_renamed'])-f(r['js_orig']),3) for r in pub if r['provider']=='anthropic']}, GPT-4o: {[round(f(r['js_renamed'])-f(r['js_orig']),3) for r in pub if r['provider']=='openai']}")
print(f"E1B-FLOOR: JS delta on Dell DVD Store 2 (renaming cost floor): Claude {[round(f(r['js_renamed'])-f(r['js_orig']),3) for r in np_ if r['provider']=='anthropic']}, GPT-4o {[round(f(r['js_renamed'])-f(r['js_orig']),3) for r in np_ if r['provider']=='openai']}")
P = [r for r in E1B if r["arm"] == "plan"]
print(f"E1B-PLAN-LOAD: plan arm load mean orig {np.mean([f(r['load_orig']) for r in P]):.3f} renamed {np.mean([f(r['load_renamed']) for r in P]):.3f}; renamed aborts {sum(1 for r in P if r['status_renamed']=='engine_abort')}")

print("\n=== E2: Holm correction over the 12 paired McNemar tests (aggregate over 293 mutants) ===")
agg = [r for r in E2 if r["sut"] in ("all", "ALL", "aggregate", "total")]
if not agg:
    # aggregate rows may be absent: recompute delta/discordant from per-SUT rows and use the p from the analysis output
    print("   (no aggregate rows in E2_pairwise_vs_G.csv; per-SUT rows only)")
# the E2c state-contract arm (dstate) is a separate, pre-registered single test (E2c block of e2_analysis.py); it is not part of the 12-test Holm family
rows = [r for r in E2 if r["sut"] not in ("all", "ALL", "aggregate", "total") and r["arm"] != "dstate"]
E2C = [r for r in E2 if r["arm"] == "dstate" and r["sut"] not in ("all", "ALL", "aggregate", "total")]
by = {}
for r in rows:
    by.setdefault((r["provider"], r["run"], r["arm"]), []).append(r)
tests = []
for (prov, run, arm), rs in sorted(by.items()):
    ao = sum(int(r["arm_only"]) for r in rs); go = sum(int(r["G_only"]) for r in rs)
    from scipy.stats import binomtest
    p = binomtest(min(ao, go), ao + go, 0.5).pvalue * 1 if ao + go else 1.0
    p = min(1.0, p)
    tests.append((prov, run, arm, ao - go, ao + go, p))
tests.sort(key=lambda t: t[5])
mtests = len(tests)
print("   provider run arm  delta discordant  p  Holm-adjusted p")
for i, (prov, run, arm, delta, disc, p) in enumerate(tests):
    adj = min(1.0, max((mtests - j) * tests[j][5] for j in range(i + 1)))
    print(f"   {prov:7}{run:4}{arm:7}{delta:+4d}   {disc:3d}   {p:.3f}   {adj:.3f}")
disc = [t[4] for t in tests]
print(f"E2-MDE: discordant pairs per comparison {min(disc)}-{max(disc)}; minimum detectable |delta| at alpha .05 (two-sided exact binomial) ~ 2*sqrt(discordant) = {2*np.sqrt(min(disc)):.0f}-{2*np.sqrt(max(disc)):.0f} mutants")
if E2C:
    from scipy.stats import binomtest
    ao = sum(int(r["arm_only"]) for r in E2C); go = sum(int(r["G_only"]) for r in E2C)
    print(f"E2C: state-contract arm vs G (Claude run 1, single pre-registered test): delta {ao-go:+d}; arm-only {ao} / G-only {go}; McNemar exact p = {min(1.0, binomtest(min(ao,go), ao+go, 0.5).pvalue) if ao+go else 1.0:.3f}  (bootstrap CI in e2_analysis.py output)")
