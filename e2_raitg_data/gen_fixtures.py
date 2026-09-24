#!/usr/bin/env python3
"""E2 fixture generation: SynthData 1.2.2 plan (Claude Sonnet 4.6, temperature 0, SynthData's own
system prompt) + engine execution (seed 42) for the three DB-backed Paper E SUTs, profiles
functional / edge / negative. Frozen inputs: ddl/*.sql, cases/*.txt (FROZEN_INPUTS_MD5.txt).
Output: fixtures/<sut>/plan.yaml, plan_raw.txt, log.json, <profile>/<table>.csv"""
import json, os, subprocess, sys, time, requests
HERE = os.path.dirname(os.path.abspath(__file__))
import re as _re
for line in open(os.path.join(HERE, "..", ".env"), encoding="utf-8-sig"):
    m = _re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
    if m and not line.lstrip().startswith("#"):
        v = m.group(2).strip().strip('"').strip("'")
        if v: os.environ[m.group(1)] = v   # file wins over a stale environment variable
SD = os.path.join(HERE, "..", "synthdata_v122", "node_modules", "@vijaypjavvadi", "synthdata")
MODEL = "claude-sonnet-4-6"
system_prompt = subprocess.run(["node", "-e", f"import(require('url').pathToFileURL('{SD}/src/llm.js').href).then(m=>process.stdout.write(m.SYSTEM_PROMPT))"],
                               capture_output=True, text=True, check=True).stdout
SUTS = sys.argv[1:] or ["flaskr", "fastapi_restful", "fastapi_task_manager"]
for sut in SUTS:
    out = f"{HERE}/fixtures/{sut}"; os.makedirs(out, exist_ok=True)
    ddl = open(f"{HERE}/ddl/{sut}.sql").read(); case = open(f"{HERE}/cases/{sut}.txt").read()
    user_msg = f"SQL DDL:\n\n{ddl}\n\nBUSINESS CASE:\n\n{case}\n\nWrite the generation plan YAML."
    t0 = time.time()
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 8000, "temperature": 0, "system": system_prompt,
              "messages": [{"role": "user", "content": user_msg}]}, timeout=600)
    r.raise_for_status(); d = r.json(); text = "".join(b.get("text", "") for b in d["content"])
    if os.path.exists(f"{out}/plan_raw.txt"):
        n = 1
        while os.path.exists(f"{out}/plan_raw.attempt{n}.txt"): n += 1
        os.rename(f"{out}/plan_raw.txt", f"{out}/plan_raw.attempt{n}.txt")
        if os.path.exists(f"{out}/log.json"): os.rename(f"{out}/log.json", f"{out}/log.attempt{n}.json")
    open(f"{out}/plan_raw.txt", "w").write(text)
    parsed = subprocess.run(["node", "-e", f"import(require('url').pathToFileURL('{SD}/src/llm.js').href).then(m=>{{const fs=require('fs');const p=m.parsePlanOutput(fs.readFileSync('{out}/plan_raw.txt','utf8'));fs.writeFileSync('{out}/plan.yaml',p.text);process.stdout.write('ok')}}).catch(e=>process.stdout.write('ERR '+e.message))"],
                            capture_output=True, text=True).stdout
    log = {"sut": sut, "model": MODEL, "temperature": 0, "plan_parse": parsed, "latency_ms": int((time.time()-t0)*1000),
           "input_tokens": d["usage"]["input_tokens"], "output_tokens": d["usage"]["output_tokens"], "synthdata": "1.2.2", "seed": 42, "profiles": {}}
    for prof in ["functional", "edge", "negative"]:
        pd = f"{out}/{prof}"; os.makedirs(pd, exist_ok=True)
        g = subprocess.run(["node", f"{SD}/bin/cli.js", "generate", "-s", f"{HERE}/ddl/{sut}.sql", "-P", f"{out}/plan.yaml",
                            "--csv", pd, "--seed", "42", "--profile", prof], capture_output=True, text=True)
        log["profiles"][prof] = {"rc": g.returncode, "msg": (g.stderr or g.stdout).strip()[-300:]}
        print(sut, prof, g.returncode, (g.stderr or g.stdout).strip()[-120:])
    json.dump(log, open(f"{out}/log.json", "w"), indent=1)
