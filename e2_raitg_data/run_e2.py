#!/usr/bin/env python3
"""Paper H / E2 driver (runs on Vijay's PC). For each provider x run x condition, launches one
run_experiment.py process per target app in parallel (4 apps), waits, then moves on. Resumable:
run_experiment skips requirements whose log exists. Keys are read from ..\\.env (file wins).
Conditions: full_dfunc, full_dall, full_dhuman for both providers; plus `full` (the G baseline)
for openai only (the Claude G runs are the Paper E v5 seed1/seed2 logs).
Output: runs/<provider>_r<run>/runs/<cond>_<req>.json ; logs in logs/.
usage: python run_e2.py [providers=anthropic,openai] [runs=1,2] [conditions=full_dfunc,full_dall,full_dhuman]
E2c (17 Sep 2026): python run_e2.py anthropic 1 full_dstate"""
import os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
for name in (".env", ".env.example"):
    p = os.path.join(HERE, "..", name)
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                v = m.group(2).strip().strip('"').strip("'")
                if v: os.environ[m.group(1)] = v
        break
for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    print(f"{k}: {'ok' if os.environ.get(k) else 'MISSING'} ({len(os.environ.get(k, ''))} chars)")
providers = (sys.argv[1] if len(sys.argv) > 1 else "anthropic,openai").split(",")
runs = (sys.argv[2] if len(sys.argv) > 2 else "1,2").split(",")
CONDS_ARG = sys.argv[3].split(",") if len(sys.argv) > 3 else None
MODEL = {"anthropic": "claude-sonnet-4-6", "openai": "gpt-4o"}
APPS = ["flaskr", "fastapi-restful", "fastapi-task-manager", "httpbin"]
os.environ["RAITG_TESTDATA_DIR"] = os.path.join(HERE, "testdata")
os.makedirs(os.path.join(HERE, "logs"), exist_ok=True)
LOG = open(os.path.join(HERE, "RUN_E2_LOG.txt"), "a", encoding="utf-8")
def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"; print(line); LOG.write(line + "\n"); LOG.flush()
log("=== RUN_E2 start ===")
for prov in providers:
    for run in runs:
        conds = CONDS_ARG or (["full_dfunc", "full_dall", "full_dhuman"] + (["full"] if prov == "openai" else []))
        out = os.path.join(HERE, "runs", f"{prov}_r{run}")
        for cond in conds:
            log(f"{prov} run{run} {cond}: starting 4 app processes")
            procs = []
            for app in APPS:
                lf = open(os.path.join(HERE, "logs", f"{prov}_r{run}_{cond}_{app}.log"), "a", encoding="utf-8")
                cmd = [sys.executable, os.path.join(HERE, "raitg", "scripts", "run_experiment.py"), "--full",
                       "--conditions", cond, "--apps", app, "--backend", prov, "--model", MODEL[prov], "--out", out]
                procs.append((app, subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=os.path.join(HERE, "raitg")), lf))
            for app, pr, lf in procs:
                rc = pr.wait(); lf.close()
                log(f"{prov} run{run} {cond} {app}: rc={rc}")
            n = len([f for f in os.listdir(os.path.join(out, "runs")) if f.startswith(cond + "_R-")]) if os.path.isdir(os.path.join(out, "runs")) else 0
            log(f"{prov} run{run} {cond}: {n}/172 requirement logs present")
log("=== RUN_E2 DONE ===")
