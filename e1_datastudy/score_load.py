#!/usr/bin/env python3
"""Load one arm's output (a directory of <table>.csv files) into a fresh PostgreSQL database
created from the subject's canonical DDL, row by row in FK-dependency order, and record every
constraint violation by SQLSTATE class. Rows that violate anything are rejected (not loaded), so
a rejected parent row makes its children fail their FK — the real cost of an invalid row.

usage: score_load.py <subject> <csv_dir> <out.json> [--db name]
Violation classes (SQLSTATE): 23503 FK, 23505 UNIQUE/PK, 23514 CHECK, 23502 NOT NULL,
22xxx type/length/format ('22001' string too long, '22P02' invalid text, '22003' out of range,
'22007'/'22008' bad date), other -> 'other'. Missing table CSV -> table counted as absent."""
import csv, json, os, re, subprocess, sys, time

subject, csv_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else f"score_{subject}_{int(time.time())}"
ddl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ddl", f"{subject}.canonical.sql")
ddl = open(ddl_path).read()
tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
_tp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "row_targets.json")
TARGETS = json.load(open(_tp)).get(subject, {}) if os.path.exists(_tp) else {}

def psql(sql, database=db, check=True):
    r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", database, "-At", "-F", "\t", "-c", sql],
                       capture_output=True, text=True)
    if check and r.returncode: raise SystemExit(f"psql error: {r.stderr}\n{sql[:300]}")
    return r.stdout

psql(f'DROP DATABASE IF EXISTS "{db}"', "postgres"); psql(f'CREATE DATABASE "{db}"', "postgres")
subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db, "-f", ddl_path], check=True, capture_output=True)
psql("CREATE TABLE _viol (tbl text, rid int, sqlstate text, msg text)")
psql("CREATE TABLE _load (tbl text, emitted int, loaded int)")

def classify(state):
    if state == "23503": return "fk"
    if state == "23505": return "unique"
    if state == "23514": return "check"
    if state == "23502": return "not_null"
    if state.startswith("22"): return "type"
    return "other"

report = {"subject": subject, "db": db, "csv_dir": csv_dir, "tables": {}}
for t in tables:
    f = os.path.join(csv_dir, f"{t}.csv")
    if not os.path.exists(f):
        # a table whose row target is 0 legitimately has no CSV: not counted as absent
        tgt = TARGETS.get(t, {}).get("target", None)
        report["tables"][t] = {"absent": tgt not in (0,), "emitted": 0, "loaded": 0, "target": tgt}
        continue
    with open(f, newline="", encoding="utf-8", errors="replace") as fh:
        header = next(csv.reader(fh))
    header = [h.strip().strip('"') for h in header]
    real_cols = psql(f"select column_name from information_schema.columns where table_name='{t}' and table_schema='public' order by ordinal_position").split()
    unknown = [h for h in header if h.lower() not in [c.lower() for c in real_cols]]
    cols = [h for h in header if h.lower() in [c.lower() for c in real_cols]]
    if not cols:
        report["tables"][t] = {"absent": False, "emitted": 0, "loaded": 0, "error": "no matching columns", "unknown_columns": unknown}
        continue
    stg = f"_stg_{t}"
    psql(f'CREATE TABLE {stg} (_rid serial, ' + ", ".join(f'"{h}" text' for h in header) + ")")
    # copy CSV into staging (all text; empty string -> NULL)
    r = subprocess.run(["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db,
                        "-c", f"\\copy {stg}(" + ",".join(f'"{h}"' for h in header) + f") from '{os.path.abspath(f)}' with (format csv, header true, null '')"],
                       capture_output=True, text=True)
    if r.returncode:
        report["tables"][t] = {"absent": False, "emitted": 0, "loaded": 0, "error": "csv unreadable: " + r.stderr.strip()[:200]}
        continue
    emitted = int(psql(f"select count(*) from {stg}"))
    collist = ", ".join(cols)
    # typed select: cast each text column to the target column type
    types = dict(l.split("\t") for l in psql(f"select column_name, format_type(a.atttypid, NULL) from information_schema.columns c join pg_attribute a on a.attname=c.column_name join pg_class r on r.oid=a.attrelid and r.relname=c.table_name where c.table_name='{t}' and c.table_schema='public'").strip().splitlines())
    # base-type casts only (no typmod) so INSERT assignment enforces varchar(n)/char(n)/numeric(p,s);
    # 'character' without typmod would mean char(1) and silently truncate, so cast char/varchar to text
    def base(tn):
        return "text" if tn in ("character", "character varying", "bpchar") else tn
    sel = ", ".join(f'"{c}"::{base(types[c.lower()]) if c.lower() in types else "text"}' for c in cols)
    do = f"""
DO $$
DECLARE r record; n int := 0;
BEGIN
  FOR r IN SELECT _rid FROM {stg} ORDER BY _rid LOOP
    BEGIN
      EXECUTE format('INSERT INTO {t} ({collist}) SELECT {sel.replace("'", "''")} FROM {stg} WHERE _rid = %s', r._rid);
      n := n + 1;
    EXCEPTION WHEN OTHERS THEN
      INSERT INTO _viol VALUES ('{t}', r._rid, SQLSTATE, left(SQLERRM, 200));
    END;
  END LOOP;
  -- retry rows rejected only for FK until no progress: within-table row order (self-referencing
  -- FKs such as employees.reports_to) must not count as a violation for any arm
  LOOP
    DECLARE prog int := 0; rr record;
    BEGIN
      FOR rr IN SELECT rid FROM _viol WHERE tbl='{t}' AND sqlstate='23503' ORDER BY rid LOOP
        BEGIN
          EXECUTE format('INSERT INTO {t} ({collist}) SELECT {sel.replace("'", "''")} FROM {stg} WHERE _rid = %s', rr.rid);
          DELETE FROM _viol WHERE tbl='{t}' AND rid=rr.rid; n := n + 1; prog := prog + 1;
        EXCEPTION WHEN OTHERS THEN NULL;
        END;
      END LOOP;
      EXIT WHEN prog = 0;
    END;
  END LOOP;
  INSERT INTO _load VALUES ('{t}', (SELECT count(*) FROM {stg}), n);
END $$;"""
    psql(do)
    loaded = int(psql(f"select loaded from _load where tbl='{t}'"))
    viol = {}
    for line in psql(f"select sqlstate, count(*) from _viol where tbl='{t}' group by 1").strip().splitlines():
        st, c = line.split("\t"); viol[classify(st)] = viol.get(classify(st), 0) + int(c)
    report["tables"][t] = {"absent": False, "emitted": emitted, "loaded": loaded, "rejected": emitted - loaded,
                           "violations": viol, "unknown_columns": unknown, "missing_columns": [c for c in real_cols if c.lower() not in [h.lower() for h in header]]}
    psql(f"DROP TABLE {stg}")

tot_e = sum(v.get("emitted", 0) for v in report["tables"].values())
tot_l = sum(v.get("loaded", 0) for v in report["tables"].values())
agg = {}
for v in report["tables"].values():
    for k, c in v.get("violations", {}).items(): agg[k] = agg.get(k, 0) + c
report["aggregate"] = {"emitted": tot_e, "loaded": tot_l, "load_rate": round(tot_l / tot_e, 4) if tot_e else 0.0,
                       "violations": agg, "tables_absent": sum(1 for v in report["tables"].values() if v.get("absent"))}
json.dump(report, open(out_path, "w"), indent=1)
print(json.dumps(report["aggregate"]))
