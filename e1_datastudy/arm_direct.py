#!/usr/bin/env python3
"""Arm 1 — DIRECT EMISSION: ask the LLM to write the rows itself.

Table by table in FK-dependency order (the most favourable form of the naive approach: the model
sees the full canonical DDL, the frozen business case, the exact row target for the table, and a
sample of the parent-key values that were actually emitted for every FK column). Rows are
requested in chunks of CHUNK per call; the model must answer with CSV only (header + rows).
Every call's token counts and latency are logged. Output: <out_dir>/<table>.csv, <out_dir>/log.json.

usage: arm_direct.py <subject> <provider: anthropic|openai> <run: 1|2> <out_dir>
Env: ANTHROPIC_API_KEY / OPENAI_API_KEY (from ../.env), optional DIRECT_CHUNK (default 200)."""
import csv, io, json, os, re, sys, time, random
import requests

subject, provider, run, out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
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
CHUNK = int(os.environ.get("DIRECT_CHUNK", "200"))
MODELS = {"anthropic": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
          "openai": os.environ.get("OPENAI_MODEL", "gpt-4o")}
ddl = open(f"{HERE}/ddl/{subject}.canonical.sql", encoding="utf-8").read()
case = open(f"{HERE}/cases/{subject}.txt", encoding="utf-8").read()
targets = json.load(open(f"{HERE}/row_targets.json"))[subject]
tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
os.makedirs(out_dir, exist_ok=True)

def table_block(t):
    m = re.search(rf"^CREATE TABLE {t} \((.*?)^\);", ddl, re.M | re.S)
    return m.group(1)

def columns_of(t):
    cols = []
    for line in table_block(t).splitlines():
        line = line.strip().rstrip(",")
        if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
        cols.append(line.split()[0])
    return cols

def fks_of(t):
    return re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", table_block(t))

SYSTEM = ("You are a test-data generator. You will be given a PostgreSQL schema (DDL), a business case, "
          "and one table to fill. Output ONLY CSV: a header line with the table's column names in DDL order, "
          "then exactly the requested number of data rows. No prose, no markdown fences, no comments. "
          "Every row must satisfy every constraint in the DDL (types, lengths, NOT NULL, PRIMARY KEY/UNIQUE "
          "uniqueness across ALL rows of the table including rows from earlier chunks, CHECK constraints, and "
          "FOREIGN KEY values that exist in the parent table). Quote values containing commas or quotes per RFC 4180. "
          "Use empty field for NULL. Dates as YYYY-MM-DD, timestamps as YYYY-MM-DD HH:MM:SS.")

def call_llm(prompt, max_tokens=16000):
    t0 = time.time()
    if provider == "anthropic":
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": MODELS[provider], "max_tokens": max_tokens, "temperature": 0, "system": SYSTEM,
                  "messages": [{"role": "user", "content": prompt}]}, timeout=600)
        r.raise_for_status(); d = r.json()
        text = "".join(b.get("text", "") for b in d["content"])
        usage = {"input_tokens": d["usage"]["input_tokens"], "output_tokens": d["usage"]["output_tokens"]}
    else:
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "content-type": "application/json"},
            json={"model": MODELS[provider], "max_tokens": max_tokens, "temperature": 0,
                  "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}, timeout=600)
        r.raise_for_status(); d = r.json()
        text = d["choices"][0]["message"]["content"]
        usage = {"input_tokens": d["usage"]["prompt_tokens"], "output_tokens": d["usage"]["completion_tokens"]}
    return text, usage, int((time.time() - t0) * 1000)

def parse_csv(text, cols):
    text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text.strip(), flags=re.M)
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows: return [], "empty"
    header = [h.strip() for h in rows[0]]
    if [h.lower() for h in header] != [c.lower() for c in cols]:
        # accept if same set in any order; otherwise keep model's header (scorer reports unknown/missing cols)
        if sorted(h.lower() for h in header) == sorted(c.lower() for c in cols):
            idx = [header.index(next(h for h in header if h.lower() == c.lower())) for c in cols]
            body = [[r[i] if i < len(r) else "" for i in idx] for r in rows[1:]]
            return body, "reordered"
        return [r + [""] * (len(cols) - len(r)) for r in rows[1:]], "header_mismatch:" + ",".join(header)
    body = [r + [""] * (len(cols) - len(r)) for r in rows[1:]]
    return [r[:len(cols)] for r in body], "ok"

log = {"subject": subject, "provider": provider, "model": MODELS[provider], "run": run, "chunk": CHUNK,
       "calls": [], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
if os.path.exists(f"{out_dir}/log.json"):
    log = json.load(open(f"{out_dir}/log.json", encoding="utf-8")); log.pop("totals", None); log.pop("finished", None)
emitted = {}
rng = random.Random(20260911 + int(run))
for t in tables:
    target = targets[t]["target"]
    cols = columns_of(t)
    out_rows = []
    done_f = f"{out_dir}/{t}.csv"
    if os.path.exists(done_f) and os.path.exists(f"{out_dir}/log.json"):
        _b = open(done_f, "rb").read()          # files written before the UTF-8 fix are cp1252 on Windows
        try: _t = _b.decode("utf-8")
        except UnicodeDecodeError: _t = _b.decode("cp1252")
        prev = list(csv.reader(io.StringIO(_t)))[1:]
        if len(prev) >= target:            # resume: table already complete
            emitted[t] = prev; continue
    if target == 0:
        with open(f"{out_dir}/{t}.csv", "w", newline="", encoding="utf-8") as f: csv.writer(f).writerow(cols)
        emitted[t] = []
        continue
    while len(out_rows) < target:
        n = min(CHUNK, target - len(out_rows))
        parent_ctx = ""
        for col, ptab, pcol in fks_of(t):
            pvals = [r[columns_of(ptab).index(pcol)] for r in emitted.get(ptab, [])] if ptab != t else [r[columns_of(t).index(pcol)] for r in out_rows]
            pvals = [v for v in pvals if v != ""]
            sample = pvals if len(pvals) <= 60 else rng.sample(pvals, 60)
            parent_ctx += f"\nValid values for {t}.{col} (must reference existing {ptab}.{pcol}; {len(pvals)} exist, sample): {', '.join(sample)}"
        already = ""
        if out_rows:
            keys = [", ".join(r[:2]) for r in out_rows[-30:]]
            already = f"\n{len(out_rows)} rows of {t} were already emitted in earlier chunks (last 30 first-two-column values: {' | '.join(keys)}). Do not repeat their primary/unique key values."
        prompt = (f"SCHEMA (PostgreSQL DDL):\n{ddl}\n\nBUSINESS CASE:\n{case}\n\nTABLE TO FILL NOW: {t}\n"
                  f"Columns in order: {', '.join(cols)}\nEmit exactly {n} data rows.{parent_ctx}{already}\n"
                  f"Total rows planned for this table: {target}. Row targets for all tables: "
                  + ", ".join(f"{k}={v['target']}" for k, v in targets.items()) + "\nCSV only.")
        try:
            text, usage, ms = call_llm(prompt)
        except Exception as e:
            log["calls"].append({"table": t, "requested": n, "error": str(e)[:200]}); break
        rows, status = parse_csv(text, cols)
        log["calls"].append({"table": t, "requested": n, "returned": len(rows), "parse": status, **usage, "latency_ms": ms})
        if not rows: break
        out_rows.extend(rows[:n])
    with open(f"{out_dir}/{t}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(out_rows)
    emitted[t] = out_rows
    json.dump(log, open(f"{out_dir}/log.json", "w", encoding="utf-8"), indent=1)
log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
log["totals"] = {"input_tokens": sum(c.get("input_tokens", 0) for c in log["calls"]),
                 "output_tokens": sum(c.get("output_tokens", 0) for c in log["calls"]),
                 "latency_ms": sum(c.get("latency_ms", 0) for c in log["calls"]), "calls": len(log["calls"]),
                 "rows": sum(len(v) for v in emitted.values())}
json.dump(log, open(f"{out_dir}/log.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(log["totals"]))
