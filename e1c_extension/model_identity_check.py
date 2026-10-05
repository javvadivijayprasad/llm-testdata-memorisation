#!/usr/bin/env python3
"""Model-identity check for the E1c manuscript identifiers.
For each identifier the paper names, record (a) whether the provider's /models listing contains it,
(b) the `model` field the provider returns on a one-token completion (what was actually served), and
(c) the per-call identifiers found in the E1c run logs. Writes results/model_identity_check.json.
Keys are read from the environment / ../.env and never printed. OpenRouter's listing is public (no key needed)."""
import os, json, glob, collections, datetime, requests

HERE = os.path.dirname(os.path.abspath(__file__))
import re
def env(k):
    """Same precedence as arm_direct_e1c.py: ../.env overrides the process environment (a stale machine-wide
    variable must not shadow the file the runs used); quotes, spaces, BOM and 'export' tolerated."""
    v = None
    p = os.path.join(HERE, "..", ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and m.group(1) == k and not line.lstrip().startswith("#"):
                v = m.group(2).strip().strip('"').strip("'")
    return v or os.environ.get(k)

def _src(k):
    p = os.path.join(HERE, "..", ".env")
    return os.path.exists(p) and any(re.match(r"\s*(?:export\s+)?" + k + r"\s*=", l) for l in open(p, encoding="utf-8-sig"))

PAPER = {"anthropic": ["claude-sonnet-4-6", "claude-sonnet-5-5"],
         "openai": ["gpt-4o", "gpt-5.6-terra"],
         "openrouter": ["qwen/qwen3-235b-a22b-2507"]}
out = {"key_sources": {k: ("env_file" if _src(k) else "process_env") for k in ("ANTHROPIC_API_KEY","OPENAI_API_KEY","OPENAI_COMPAT_API_KEY")}, "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "providers": {}, "run_logs": {}}

# (c) what the run logs say
seen = collections.defaultdict(lambda: collections.defaultdict(set))
for f in glob.glob(os.path.join(HERE, "arms", "direct", "*", "log.json")):
    cell = os.path.basename(os.path.dirname(f)); d = json.load(open(f))
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("model", "served_model", "provider"): seen[d["model"]][k].add(str(v))
                walk(v)
        elif isinstance(o, list):
            for x in o: walk(x)
    walk(d)
out["run_logs"] = {m: {k: sorted(v) for k, v in kv.items()} for m, kv in seen.items()}

# (a)+(b) Anthropic
def safe(fn, name):
    try: return fn()
    except Exception as e: return {"error": type(e).__name__ + ": " + str(e)[:160]}

ak = env("ANTHROPIC_API_KEY"); res = {}
def _anthropic():
  if not ak: return {"error": "no key"}
  res = {}
  h = {"x-api-key": ak, "anthropic-version": "2023-06-01", "content-type": "application/json"}
  listing = requests.get("https://api.anthropic.com/v1/models?limit=1000", headers=h, timeout=60).json()
  ids = {m["id"]: m.get("display_name") for m in listing.get("data", [])}
  for mid in PAPER["anthropic"]:
    r = requests.post("https://api.anthropic.com/v1/messages", headers=h, timeout=120,
                      json={"model": mid, "max_tokens": 16, "messages": [{"role": "user", "content": "hi"}]})
    res[mid] = {"in_models_listing": mid in ids, "display_name": ids.get(mid), "http_status": r.status_code,
                "served_model_in_response": r.json().get("model") if r.status_code == 200 else r.text[:200]}
  return res
out["providers"]["anthropic"] = safe(_anthropic, "anthropic")

# OpenAI
ok = env("OPENAI_API_KEY")
def _openai():
  if not ok: return {"error": "no key"}
  res = {}
  h = {"Authorization": "Bearer " + ok, "content-type": "application/json"}
  listing = requests.get("https://api.openai.com/v1/models", headers=h, timeout=60).json()
  ids = {m["id"] for m in listing.get("data", [])}
  for mid in PAPER["openai"]:
    r = requests.post("https://api.openai.com/v1/chat/completions", headers=h, timeout=120,
                      json={"model": mid, "max_completion_tokens": 64, "messages": [{"role": "user", "content": "hi"}]})
    res[mid] = {"in_models_listing": mid in ids, "http_status": r.status_code,
                "served_model_in_response": r.json().get("model") if r.status_code == 200 else r.text[:200]}
  return res
out["providers"]["openai"] = safe(_openai, "openai")

# OpenRouter (public listing)
def _openrouter():
  listing = requests.get("https://openrouter.ai/api/v1/models", timeout=60).json()
  ids = {m["id"]: m.get("name") for m in listing.get("data", [])}
  res = {mid: {"in_models_listing": mid in ids, "display_name": ids.get(mid)} for mid in PAPER["openrouter"]}
  rk = env("OPENAI_COMPAT_API_KEY") or env("OPENROUTER_API_KEY")
  if rk:
    for mid in PAPER["openrouter"]:
      r = requests.post("https://openrouter.ai/api/v1/chat/completions", timeout=120,
                        headers={"Authorization": "Bearer " + rk, "content-type": "application/json"},
                        json={"model": mid, "max_tokens": 16, "messages": [{"role": "user", "content": "hi"}]})
      res[mid].update({"http_status": r.status_code, "served_model_in_response": r.json().get("model") if r.status_code == 200 else r.text[:200],
                       "serving_host": r.json().get("provider") if r.status_code == 200 else None})
  return res
out["providers"]["openrouter"] = safe(_openrouter, "openrouter")

os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "results", "model_identity_check.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
