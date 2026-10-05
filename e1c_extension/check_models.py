#!/usr/bin/env python3
"""Pre-flight: keys present for every provider used, no FILL- placeholders left, every schema registered."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); E1 = os.path.join(HERE, "..", "e1_datastudy")
for name in (".env", ".env.example"):
    p = os.path.join(HERE, "..", name)
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if m and not line.lstrip().startswith("#"):
                v = m.group(2).strip().strip('"').strip("'")
                if v: os.environ[m.group(1)] = v
        break
M = json.load(open(f"{HERE}/models_e1c.json"))["models"]; S = json.load(open(f"{HERE}/schemas_e1c.json"))["schemas"]
rt = json.load(open(f"{E1}/row_targets.json")); ok = True
need = {"anthropic": ["ANTHROPIC_API_KEY"], "openai": ["OPENAI_API_KEY"], "compat": ["OPENAI_COMPAT_BASE_URL", "OPENAI_COMPAT_API_KEY"]}
for m in M:
    if m["model"].startswith("FILL-"): print(f"SKIP  {m['tag']}: model id not filled in models_e1c.json"); continue
    missing = [k for k in need[m["provider"]] if not os.environ.get(k)]
    if missing: print(f"ERROR {m['tag']}: missing {missing} in ..\\.env"); ok = False
    else: print(f"ok    {m['tag']} = {m['model']} ({m['provider']})")
for s in S:
    if s["name"] not in rt: print(f"WARN  schema {s['name']} not registered (run make_subject.py {s['name']}); it will be skipped")
    elif not os.path.exists(f"{E1}/human_cache/{s['name']}"): print(f"WARN  schema {s['name']}: no human_cache (copy_rate will skip it)")
sys.exit(0 if ok else 1)
