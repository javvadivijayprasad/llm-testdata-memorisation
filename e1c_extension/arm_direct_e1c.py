#!/usr/bin/env python3
"""E1c — DIRECT-EMISSION arm for the copy-rate extension (Paper H, EMSE revision, Oct 2026).

Same prompt, chunking, parent-key context and resume logic as e1_datastudy/arm_direct.py (the
original is left untouched so that the E1 cells stay reproducible). Differences:
  * the model is an explicit argument (not a per-provider default), and a third provider "compat"
    talks to any OpenAI-compatible chat endpoint (Together, OpenRouter, Groq, a local server) so that
    an open-weight model can be run with the same code;
  * the output folder is named <subject>_<tag>_r<run>, where <tag> is a short model label chosen in
    models_e1c.json, so that cells from different models of the same provider do not collide;
  * DDL, business case and row targets are read from ../e1_datastudy/ (single source of truth).

usage: arm_direct_e1c.py <subject> <provider: anthropic|openai|compat> <model-id> <run> <out_dir>
Env (from ../.env): ANTHROPIC_API_KEY, OPENAI_API_KEY, and for compat: OPENAI_COMPAT_BASE_URL
(e.g. https://api.together.xyz/v1), OPENAI_COMPAT_API_KEY. Optional DIRECT_CHUNK (default 200)."""
import csv, io, json, os, re, sys, time, random
import requests

subject, provider, model, run, out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
HERE = os.path.dirname(os.path.abspath(__file__))
E1 = os.path.join(HERE, "..", "e1_datastudy")

def _load_env():
    for name in (".env", ".env.example"):
        p = os.path.join(HERE, "..", name)
        if os.path.exists(p):
            for line in open(p, encoding="utf-8-sig"):
                m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    v = m.group(2).strip().strip('"').strip("'")
                    if v: os.environ[m.group(1)] = v
            return
_load_env()
CHUNK = int(os.environ.get("DIRECT_CHUNK", "200"))
ddl = open(f"{E1}/ddl/{subject}.canonical.sql", encoding="utf-8").read()
case = open(f"{E1}/cases/{subject}.txt", encoding="utf-8").read()
targets = json.load(open(f"{E1}/row_targets.json"))[subject]
tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
os.makedirs(out_dir, exist_ok=True)

def table_block(t):
    return re.search(rf"^CREATE TABLE {t} \((.*?)^\);", ddl, re.M | re.S).group(1)
def columns_of(t):
    cols = []
    for line in table_block(t).splitlines():
        line = line.strip().rstrip(",")
        if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
        cols.append(line.split()[0])
    return cols
def fks_of(t):
    return re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", table_block(t))

# identical to e1_datastudy/arm_direct.py
SYSTEM = ("You are a test-data generator. You will be given a PostgreSQL schema (DDL), a business case, "
          "and one table to fill. Output ONLY CSV: a header line with the table's column names in DDL order, "
          "then exactly the requested number of data rows. No prose, no markdown fences, no comments. "
          "Every row must satisfy every constraint in the DDL (types, lengths, NOT NULL, PRIMARY KEY/UNIQUE "
          "uniqueness across ALL rows of the table including rows from earlier chunks, CHECK constraints, and "
          "FOREIGN KEY values that exist in the parent table). Quote values containing commas or quotes per RFC 4180. "
          "Use empty field for NULL. Dates as YYYY-MM-DD, timestamps as YYYY-MM-DD HH:MM:SS.")

def _chat_completions(base, key, prompt, max_tokens):
    body = {"model": model, "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
    # newer OpenAI chat models take max_completion_tokens and reject max_tokens; OpenAI-compatible hosts take max_tokens
    body["max_completion_tokens" if provider == "openai" else "max_tokens"] = max_tokens
    if provider == "compat" and os.environ.get("OPENROUTER_PROVIDER"):      # optional: pin one serving host for reproducibility
        body["provider"] = {"order": [os.environ["OPENROUTER_PROVIDER"]], "allow_fallbacks": False}
    hdr = {"Authorization": "Bearer " + key, "content-type": "application/json"}
    r = requests.post(base.rstrip("/") + "/chat/completions", headers=hdr, json=body, timeout=600)
    dropped = False
    if r.status_code == 400 and "temperature" in r.text:                     # some models accept only the default temperature
        body.pop("temperature"); dropped = r.text[:200]; r = requests.post(base.rstrip("/") + "/chat/completions", headers=hdr, json=body, timeout=600)
    if r.status_code >= 400: raise requests.HTTPError(f"{r.status_code} {r.text[:300]}", response=r)
    d = r.json()
    text = d["choices"][0]["message"]["content"]
    u = d.get("usage", {})
    usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}
    if d.get("provider"): usage["provider"] = d["provider"]          # OpenRouter reports which host served the call
    if d.get("model"): usage["served_model"] = d["model"]
    if dropped: usage["temperature_dropped"] = dropped
    return text, usage

def call_llm(prompt, max_tokens=int(os.environ.get("DIRECT_MAX_TOKENS", "16000"))):
    t0 = time.time()
    for attempt in range(4):
        try:
            if provider == "anthropic":
                hdr = {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"}
                if os.environ.get("ANTHROPIC_WORKSPACE_ID"): hdr["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]   # identity-linked keys
                body = {"model": model, "max_tokens": max_tokens, "temperature": 0, "system": SYSTEM,
                        "messages": [{"role": "user", "content": prompt}]}
                # Models that reason by default can spend the whole output budget on reasoning and return no text
                # (seen on Sonnet 5.5: 16,000 output tokens, empty text). E1 ran Sonnet 4.6 without reasoning, so
                # for parity reasoning is switched off; if the API rejects the field, the request is retried without it.
                if os.environ.get("ANTHROPIC_DISABLE_THINKING", "0") == "1": body["thinking"] = {"type": "between_tools"}   # the API's "off" setting for models that reason by default (not used in the E1c runs of 4-5 Oct 2026: those ran at the model default, with reasoning)
                r = requests.post("https://api.anthropic.com/v1/messages", headers=hdr, json=body, timeout=600)
                thinking_reject = None
                if r.status_code == 400 and "thinking" in r.text:
                    thinking_reject = r.text[:300]; body.pop("thinking", None)
                    r = requests.post("https://api.anthropic.com/v1/messages", headers=hdr, json=body, timeout=600)
                dropped = False
                if r.status_code == 400 and "temperature" in r.text:          # model accepts only the default temperature
                    body.pop("temperature"); dropped = r.text[:200]; r = requests.post("https://api.anthropic.com/v1/messages", headers=hdr, json=body, timeout=600)
                if r.status_code >= 400: raise requests.HTTPError(f"{r.status_code} {r.text[:300]}", response=r)
                d = r.json()
                text = "".join(b.get("text", "") for b in d["content"])
                usage = {"input_tokens": d["usage"]["input_tokens"], "output_tokens": d["usage"]["output_tokens"],
                         "stop_reason": d.get("stop_reason"), "thinking_disabled": "thinking" in body,
                         "content_blocks": [(b.get("type"), len(b.get("text", "") or b.get("thinking", "") or "")) for b in d["content"]][:6]}
                if thinking_reject: usage["thinking_reject"] = thinking_reject
                if dropped: usage["temperature_dropped"] = dropped
            elif provider == "openai":
                text, usage = _chat_completions("https://api.openai.com/v1", os.environ["OPENAI_API_KEY"], prompt, max_tokens)
            elif provider == "compat":
                text, usage = _chat_completions(os.environ["OPENAI_COMPAT_BASE_URL"], os.environ["OPENAI_COMPAT_API_KEY"], prompt, max_tokens)
            else:
                raise SystemExit("provider must be anthropic|openai|compat")
            return text, usage, int((time.time() - t0) * 1000)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (429, 500, 502, 503, 529) and attempt < 3:
                time.sleep(15 * (attempt + 1)); continue
            raise
        except requests.RequestException as e:
            if attempt < 3:
                time.sleep(15 * (attempt + 1)); continue
            raise

def parse_csv(text, cols):
    text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text.strip(), flags=re.M)
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows: return [], "empty"
    header = [h.strip() for h in rows[0]]
    if [h.lower() for h in header] != [c.lower() for c in cols]:
        if sorted(h.lower() for h in header) == sorted(c.lower() for c in cols):
            idx = [header.index(next(h for h in header if h.lower() == c.lower())) for c in cols]
            body = [[r[i] if i < len(r) else "" for i in idx] for r in rows[1:]]
            return body, "reordered"
        return [r + [""] * (len(cols) - len(r)) for r in rows[1:]], "header_mismatch:" + ",".join(header)
    body = [r + [""] * (len(cols) - len(r)) for r in rows[1:]]
    return [r[:len(cols)] for r in body], "ok"

log = {"subject": subject, "provider": provider, "model": model, "run": run, "chunk": CHUNK, "arm": "direct", "series": "E1c",
       "calls": [], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
if os.path.exists(f"{out_dir}/log.json"):
    log = json.load(open(f"{out_dir}/log.json", encoding="utf-8")); log.pop("totals", None); log.pop("finished", None)
emitted = {}
rng = random.Random(20260911 + int(run))      # same seed rule as E1 so the parent-key samples are comparable
for t in tables:
    target = targets[t]["target"]
    cols = columns_of(t)
    out_rows = []
    done_f = f"{out_dir}/{t}.csv"
    if os.path.exists(done_f) and os.path.exists(f"{out_dir}/log.json"):
        prev = list(csv.reader(io.StringIO(open(done_f, "rb").read().decode("utf-8"))))[1:]
        if len(prev) >= target:
            emitted[t] = prev; continue
    if target == 0:
        with open(done_f, "w", newline="", encoding="utf-8") as f: csv.writer(f).writerow(cols)
        emitted[t] = []; continue
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
        entry = {"table": t, "requested": n, "returned": len(rows), "parse": status, **usage, "latency_ms": ms}
        if not rows: entry["response_head"] = text[:300]          # keep evidence of what the model said instead of rows
        log["calls"].append(entry)
        if not rows:
            empties = sum(1 for c in log["calls"] if c.get("table") == t and c.get("returned") == 0)
            if empties < 3: continue                              # retry an empty answer up to twice before giving up on the table
            break
        out_rows.extend(rows[:n])
    with open(done_f, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols); w.writerows(out_rows)
    emitted[t] = out_rows
    json.dump(log, open(f"{out_dir}/log.json", "w", encoding="utf-8"), indent=1)
log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
log["totals"] = {"input_tokens": sum(c.get("input_tokens", 0) for c in log["calls"]),
                 "output_tokens": sum(c.get("output_tokens", 0) for c in log["calls"]),
                 "latency_ms": sum(c.get("latency_ms", 0) for c in log["calls"]), "calls": len(log["calls"]),
                 "rows": sum(len(v) for v in emitted.values()), "errors": sum(1 for c in log["calls"] if "error" in c)}
json.dump(log, open(f"{out_dir}/log.json", "w", encoding="utf-8"), indent=1)
print(json.dumps(log["totals"]))
