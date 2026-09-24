#!/usr/bin/env python3
"""Arm 2 — PLAN-THEN-EXECUTE (SynthData v1.2.2, frozen study version): the LLM writes the YAML generation plan with
SynthData's own system prompt and user-message format (src/llm.js authorPlan, reproduced here so
that the model, temperature=0 and token usage are controlled and logged identically to the direct
arm); the deterministic engine then executes the plan (`synthdata generate --csv`, seed 42).
The business case is the frozen case text plus the same row-target line every arm receives.
Output: <out_dir>/plan.yaml, <out_dir>/<table>.csv (functional profile), <out_dir>/log.json.
usage: arm_plan.py <subject> <provider> <run> <out_dir> [--profile functional|edge|negative|volume]"""
import json, os, re, subprocess, sys, time
import requests

subject, provider, run, out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
profile = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else "functional"
HERE = os.path.dirname(os.path.abspath(__file__))

def _load_env():
    """Load API keys from ../.env (or ../.env.example) if not already in the environment;
    tolerant of spaces around '=', surrounding quotes, CRLF and 'export ' prefixes."""
    import re as _re
    for name in (".env", ".env.example"):
        p = os.path.join(HERE, "..", name)
        if os.path.exists(p):
            for line in open(p, encoding="utf-8-sig"):
                m = _re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    v = m.group(2).strip().strip('"').strip("'")
                    if v: os.environ[m.group(1)] = v   # file wins over a stale system variable
            return
_load_env()
SD = os.environ.get("SYNTHDATA_DIR") or os.path.join(HERE, "..", "synthdata_v122", "node_modules", "@vijaypjavvadi", "synthdata")
SD = SD.replace("\\", "/")
MODELS = {"anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
          "openai": os.environ.get("OPENAI_MODEL", "gpt-4o")}
ddl = open(f"{HERE}/ddl/{subject}.canonical.sql", encoding="utf-8").read()
targets = json.load(open(f"{HERE}/row_targets.json"))[subject]
case = open(f"{HERE}/cases/{subject}.txt", encoding="utf-8").read() + "\nTarget row counts per table (use exactly these): " + \
       ", ".join(f"{k}={v['target']}" for k, v in targets.items()) + "\n"
out_dir = os.path.abspath(out_dir)
os.makedirs(out_dir, exist_ok=True)
out_js = out_dir.replace("\\", "/")   # for the node snippets (backslashes would be escapes)
system_prompt = subprocess.run(["node", "-e", f"import(require('url').pathToFileURL('{SD}/src/llm.js').href).then(m=>process.stdout.write(m.SYSTEM_PROMPT))"],
                               capture_output=True, text=True, check=True).stdout
user_msg = f"SQL DDL:\n\n{ddl}\n\nBUSINESS CASE:\n\n{case}\n\nWrite the generation plan YAML."

t0 = time.time()
if provider == "anthropic":
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODELS[provider], "max_tokens": 8000, "temperature": 0, "system": system_prompt,
              "messages": [{"role": "user", "content": user_msg}]}, timeout=600)
    r.raise_for_status(); d = r.json()
    text = "".join(b.get("text", "") for b in d["content"])
    usage = {"input_tokens": d["usage"]["input_tokens"], "output_tokens": d["usage"]["output_tokens"]}
else:
    r = requests.post("https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "content-type": "application/json"},
        json={"model": MODELS[provider], "temperature": 0,
              "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}]}, timeout=600)
    r.raise_for_status(); d = r.json()
    text = d["choices"][0]["message"]["content"]
    usage = {"input_tokens": d["usage"]["prompt_tokens"], "output_tokens": d["usage"]["completion_tokens"]}
latency = int((time.time() - t0) * 1000)
open(f"{out_dir}/plan_raw.txt", "w", encoding="utf-8").write(text)
# normalise with SynthData's own parser (fences, trailing commas) and write plan.yaml
parsed = subprocess.run(["node", "-e", f"import(require('url').pathToFileURL('{SD}/src/llm.js').href).then(m=>{{const fs=require('fs');const t=fs.readFileSync('{out_js}/plan_raw.txt','utf8');const p=m.parsePlanOutput(t);fs.writeFileSync('{out_js}/plan.yaml',p.text);process.stdout.write('ok')}}).catch(e=>{{process.stdout.write('ERR '+e.message)}})"],
                        capture_output=True, text=True).stdout
log = {"subject": subject, "provider": provider, "model": MODELS[provider], "run": run, "profile": profile,
       "plan_parse": parsed, "latency_ms": latency, **usage, "synthdata": "1.2.2", "seed": 42}
gen = subprocess.run(["node", f"{SD}/bin/cli.js", "generate", "-s", f"{HERE}/ddl/{subject}.canonical.sql",
                      "-P", f"{out_dir}/plan.yaml", "--csv", out_dir, "--seed", "42", "--profile", profile],
                     capture_output=True, text=True)
log["generate_rc"] = gen.returncode
log["generate_msg"] = (gen.stderr or gen.stdout).strip()[-400:]
json.dump(log, open(f"{out_dir}/log.json", "w", encoding="utf-8"), indent=1)
print(json.dumps({k: log[k] for k in ("subject", "provider", "run", "plan_parse", "input_tokens", "output_tokens", "latency_ms", "generate_rc", "generate_msg")}))
