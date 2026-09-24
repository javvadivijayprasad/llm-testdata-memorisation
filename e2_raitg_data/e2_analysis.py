"""Paper H / E2 analysis: per-arm kill rates, paired McNemar vs G, bootstrap CIs (seed 42), usable yield,
tokens. Every number from scores_v2/<label>/<cond>__<sut>.csv, kg_v2/<label>/kg_stats.json and the run logs."""
import csv, json, glob, os, sys
from math import comb
from pathlib import Path
import numpy as np
W = Path("/home/claude/work/paperE/W"); RUNS = Path("/home/claude/work/paperH/exp/e2/runs_pc")
SUTS = ["sut1_httpbin", "sut2_fastapi_restful", "sut3_flaskr", "sut4_fastapi_task_manager"]
APP = {"sut1_httpbin": "httpbin", "sut2_fastapi_restful": "fastapi-restful", "sut3_flaskr": "flaskr", "sut4_fastapi_task_manager": "fastapi-task-manager"}
ARMS = ["g", "dfunc", "dall", "dhuman"]; COND = {"g": "full", "dfunc": "full_dfunc", "dall": "full_dall", "dhuman": "full_dhuman", "dstate": "full_dstate"}
# E2c (23 Sep 2026): the state-contract arm exists for Claude run 1 only
def arms_for(prov, run):
    return ARMS + (["dstate"] if (prov, run) == ("sonnet", 1) else [])
PROV = {"sonnet": "anthropic", "gpt4o": "openai"}
def label(arm, prov, run):
    return f"e2_{arm}_{prov}_r{run}"
def load(p):
    rows = list(csv.DictReader(open(p))); return [r["mutant_id"] for r in rows], np.array([r["killed"] == "1" for r in rows], dtype=int)
def mcnemar(a, b):
    b_only = int(((a == 0) & (b == 1)).sum()); c_only = int(((a == 1) & (b == 0)).sum()); n = b_only + c_only
    if n == 0: return b_only, c_only, 1.0
    k = min(b_only, c_only); return b_only, c_only, min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
vec, kg, ids_ref = {}, {}, {}
for prov in PROV:
    for run in (1, 2):
        for arm in arms_for(prov, run):
            lab = label(arm, prov, run); parts = []
            for s in SUTS:
                ids, k = load(W / "scores_v2" / lab / f"{COND[arm]}__{s}.csv")
                if s in ids_ref: assert ids == ids_ref[s]
                ids_ref[s] = ids; parts.append(k); vec[(prov, run, arm, s)] = k
            vec[(prov, run, arm, "all")] = np.concatenate(parts)
            for st in json.loads((W / "kg_v2" / lab / "kg_stats.json").read_text()):
                kg[(prov, run, arm, st["sut"])] = st
# tokens per arm from run logs
tok = {}
for prov in PROV:
    for run in (1, 2):
        d = RUNS / f"{PROV[prov]}_r{run}" / "runs"
        for arm in arms_for(prov, run):
            i = o = n = rep = 0
            for f in glob.glob(str(d / f"{COND[arm]}_R-*.json")):
                x = json.load(open(f)); t = x["telemetry"]; i += t["input_tokens"]; o += t["output_tokens"]; n += 1; rep += x["repair_attempts"]
            tok[(prov, run, arm)] = (i, o, n, rep)
for run in (1, 2):   # Claude G from Paper E v5 logs (generation), re-scored under the E2 harness
    d = Path(f"/home/claude/work/paperE/runs_v2/seed{run}/c_full/runs"); i = o = n = rep = 0
    for f in glob.glob(str(d / "full_R-*.json")):
        x = json.load(open(f)); t = x["telemetry"]; i += t["input_tokens"]; o += t["output_tokens"]; n += 1; rep += x["repair_attempts"]
    tok[("sonnet", run, "g")] = (i, o, n, rep)
rng = np.random.default_rng(42)
out = Path("/home/claude/work/paperH/exp/e2/results"); out.mkdir(exist_ok=True)
rows = []
with open(out / "E2_cells.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["provider", "run", "arm", "sut", "raw_units", "kg_units", "usable_fraction", "prescreen_excluded", "mutants", "killed", "kill_rate", "input_tokens", "output_tokens", "repairs"])
    for prov in PROV:
        for run in (1, 2):
            for arm in arms_for(prov, run):
                for s in SUTS + ["all"]:
                    k = vec[(prov, run, arm, s)]
                    if s == "all":
                        st = {"raw_units": sum(kg[(prov, run, arm, x)]["raw_units"] for x in SUTS), "kg_units": sum(kg[(prov, run, arm, x)]["kg_units"] for x in SUTS), "prescreen_excluded": sum(kg[(prov, run, arm, x)].get("prescreen_excluded", 0) for x in SUTS)}
                        st["usable_fraction"] = round(st["kg_units"] / st["raw_units"], 4); t = tok[(prov, run, arm)]
                    else:
                        st = kg[(prov, run, arm, s)]; t = ("", "", "", "")
                    w.writerow([prov, run, arm, APP.get(s, "ALL"), st["raw_units"], st["kg_units"], st["usable_fraction"], st.get("prescreen_excluded", ""), len(k), int(k.sum()), round(k.mean(), 4), t[0], t[1], t[3]])
print("=== aggregate killed/293 (usable yield = known-good/raw units) ===")
print(f"{'arm':7}" + "".join(f"{p}_r{r:<11}" for p in PROV for r in (1, 2)))
for arm in ARMS:
    print(f"{arm:7}" + "".join(f"{int(vec[(p, r, arm, 'all')].sum()):>4} ({kg_[(p,r,arm)]:.0%})   " for p in PROV for r in (1, 2) for kg_ in [{(p, r, arm): sum(kg[(p, r, arm, x)]['kg_units'] for x in SUTS) / sum(kg[(p, r, arm, x)]['raw_units'] for x in SUTS)}]))
print("\n=== paired vs G (same provider, same run): delta, McNemar exact p, bootstrap 95% CI of delta (1000 resamples of the 293 mutants) ===")
with open(out / "E2_pairwise_vs_G.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["provider", "run", "arm", "sut", "killed_G", "killed_arm", "delta", "arm_only", "G_only", "mcnemar_p", "boot_ci_lo", "boot_ci_hi"])
    for prov in PROV:
        for run in (1, 2):
            for arm in arms_for(prov, run)[1:]:
                if arm == "dstate":
                    continue                      # E2c is bootstrapped below with its own seeded generator, so the original arms' CIs are unchanged
                for s in SUTS + ["all"]:
                    g = vec[(prov, run, "g", s)]; a = vec[(prov, run, arm, s)]
                    bo, co, p = mcnemar(g, a)
                    if s == "all":
                        d = a - g; bs = [d[rng.integers(0, len(d), len(d))].sum() for _ in range(1000)]; lo, hi = np.percentile(bs, [2.5, 97.5])
                        print(f"{prov} r{run} {arm:6} G={g.sum():3d} arm={a.sum():3d} delta={int(a.sum()-g.sum()):+3d}  arm-only {bo:2d} / G-only {co:2d}  p={p:.3f}  CI[{lo:+.0f},{hi:+.0f}]")
                    else: lo = hi = ""
                    w.writerow([prov, run, arm, APP.get(s, "ALL"), int(g.sum()), int(a.sum()), int(a.sum() - g.sum()), bo, co, round(p, 4), lo, hi])
    # E2c state-contract arm (Claude run 1): same test, own generator (seed 42)
    rng_c = np.random.default_rng(42)
    for s in SUTS + ["all"]:
        g = vec[("sonnet", 1, "g", s)]; a = vec[("sonnet", 1, "dstate", s)]
        bo, co, p = mcnemar(g, a)
        if s == "all":
            d = a - g; bs = [d[rng_c.integers(0, len(d), len(d))].sum() for _ in range(1000)]; lo, hi = np.percentile(bs, [2.5, 97.5])
            print(f"sonnet r1 dstate G={g.sum():3d} arm={a.sum():3d} delta={int(a.sum()-g.sum()):+3d}  arm-only {bo:2d} / G-only {co:2d}  p={p:.3f}  CI[{lo:+.0f},{hi:+.0f}]")
        else: lo = hi = ""
        w.writerow(["sonnet", 1, "dstate", APP.get(s, "ALL"), int(g.sum()), int(a.sum()), int(a.sum() - g.sum()), bo, co, round(p, 4), lo, hi])
print("\n=== per-SUT killed (G / dfunc / dall / dhuman), both runs ===")
for prov in PROV:
    for s in SUTS:
        print(f"{prov:7} {APP[s]:22}" + "  ".join(f"r{r}: " + "/".join(f"{int(vec[(prov, r, a, s)].sum()):2d}" for a in ARMS) for r in (1, 2)) + f"   (n={len(vec[(prov,1,'g',s)])})")
print("\n=== usable yield per SUT (kg/raw) G vs dfunc ===")
for prov in PROV:
    for s in SUTS:
        print(f"{prov:7} {APP[s]:22}" + "  ".join(f"r{r}: " + "/".join(f"{kg[(prov, r, a, s)]['kg_units']}of{kg[(prov, r, a, s)]['raw_units']}" for a in ARMS) for r in (1, 2)))
print("\n=== tokens (in/out) and repairs per condition-run ===")
for prov in PROV:
    for run in (1, 2):
        for arm in arms_for(prov, run):
            i, o, n, rep = tok[(prov, run, arm)]; print(f"{prov} r{run} {arm:6} in {i:>9,} out {o:>9,} repairs {rep}")

print("\n=== E2c: state-contract arm (Claude run 1) per SUT: G / dfunc / dstate killed; kg/raw ===")
for s in SUTS:
    print(f"{APP[s]:22} killed " + "/".join(f"{int(vec[('sonnet',1,a,s)].sum()):2d}" for a in ("g","dfunc","dstate")) + "   usable " + "/".join(f"{kg[('sonnet',1,a,s)]['kg_units']}of{kg[('sonnet',1,a,s)]['raw_units']}" for a in ("g","dfunc","dstate")))
