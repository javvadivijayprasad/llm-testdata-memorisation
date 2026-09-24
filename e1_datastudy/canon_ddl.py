#!/usr/bin/env python3
"""Emit a canonical, self-contained DDL for a subject database: one CREATE TABLE per base
table with INLINE column constraints (NOT NULL, DEFAULT-free), PRIMARY KEY, UNIQUE, CHECK,
and FOREIGN KEY clauses, tables in FK-dependency order, enum types expanded to CHECK IN (...).
Partitioned parents are emitted as plain tables; partitions are dropped. Types are simplified to
portable SQL (integer/bigint/smallint/numeric(p,s)/text/varchar(n)/char(n)/boolean/date/
timestamp/bytea). Views, sequences, triggers, functions, indexes are omitted.
This canonical DDL is the single input every provisioning arm receives (and the human fixtures
are re-loaded into it to prove it is faithful)."""
import subprocess, sys, json, re
from collections import defaultdict

DB = sys.argv[1]
def q(sql):
    r = subprocess.run(["psql", "-d", DB, "-At", "-F", "\t", "-c", sql], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr)
    return [l.split("\t") for l in r.stdout.strip().splitlines() if l]

# base tables (exclude partitions)
tabs = [t for (t,) in q("""select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='public' and c.relkind in ('r','p') and not c.relispartition order by 1""")]
enums = defaultdict(list)
for t, v in q("""select t.typname, e.enumlabel from pg_type t join pg_enum e on e.enumtypid=t.oid
 join pg_namespace n on n.oid=t.typnamespace where n.nspname='public' order by t.typname, e.enumsortorder"""):
    enums[t].append(v)

def simplify(dt, udt, maxlen, prec, scale):
    dt = dt.lower()
    if udt in enums: return "text", enums[udt]
    if dt in ("integer","bigint","smallint","boolean","date","text","bytea","real","double precision"): return dt, None
    if dt == "numeric": return (f"numeric({prec},{scale})" if prec else "numeric"), None
    if dt in ("character varying",): return (f"varchar({maxlen})" if maxlen else "text"), None
    if dt in ("character",): return (f"char({maxlen})" if maxlen else "char(1)"), None
    if dt.startswith("timestamp"): return "timestamp", None
    if dt == "time without time zone": return "time", None
    if dt == "uuid": return "varchar(36)", None
    if dt == "money": return "numeric(12,2)", None
    if dt == "tsvector" or dt == "ARRAY" or dt == "jsonb" or dt == "json" or dt == "xml": return None, None  # dropped
    if dt == "USER-DEFINED": return "text", None
    return "text", None

out, dropped = [], []
for t in tabs:
    cols = q(f"""select column_name, data_type, udt_name, coalesce(character_maximum_length::text,''),
      coalesce(numeric_precision::text,''), coalesce(numeric_scale::text,''), is_nullable
      from information_schema.columns where table_schema='public' and table_name='{t}' order by ordinal_position""")
    lines = []
    for name, dt, udt, ml, pr, sc, nullable in cols:
        typ, enum = simplify(dt, udt, ml, pr, sc)
        if typ is None:
            dropped.append(f"{t}.{name} ({dt})"); continue
        s = f'    {name} {typ}'
        if nullable == "NO": s += " NOT NULL"
        if enum: s += " CHECK (" + name + " IN (" + ", ".join("'"+v+"'" for v in enum) + "))"
        lines.append(s)
    cons = q(f"""select contype, pg_get_constraintdef(c.oid) from pg_constraint c join pg_class r on r.oid=c.conrelid
      join pg_namespace n on n.oid=r.relnamespace where n.nspname='public' and r.relname='{t}' order by contype desc, conname""")
    for ct, cdef in cons:
        if ct in ("p","u","f","c"):
            if ct == "f":
                # keep only REFERENCES to public tables; drop ON DELETE/UPDATE actions
                cdef = re.sub(r"\s+ON (DELETE|UPDATE) [A-Z ]+", "", cdef)
                pass
            if ct == "c" and "= ANY" in cdef:
                # postgres enum-like CHECK array form -> IN list
                m = re.search(r"\(?\(?(\w+)\)?(?:::[\w ]+)?\s*=\s*ANY\s*\(\(?ARRAY\[(.*?)\]", cdef)
                if m:
                    vals = re.findall(r"'([^']*)'", m.group(2))
                    cdef = f"CHECK ({m.group(1)} IN (" + ", ".join("'"+v+"'" for v in vals) + "))"
            lines.append("    " + cdef)
    out.append(f'CREATE TABLE {t} (\n' + ",\n".join(lines) + "\n);")

# FK dependency order
deps = defaultdict(set)
for t in tabs:
    for (ref,) in q(f"""select distinct r2.relname from pg_constraint c join pg_class r on r.oid=c.conrelid
      join pg_class r2 on r2.oid=c.confrelid join pg_namespace n on n.oid=r.relnamespace
      where n.nspname='public' and r.relname='{t}' and c.contype='f'"""):
        if ref != t: deps[t].add(ref)
order, seen = [], set()
def visit(t):
    if t in seen: return
    seen.add(t)
    for d in sorted(deps[t]): visit(d)
    order.append(t)
for t in tabs: visit(t)
ddl = "\n\n".join(out[tabs.index(t)] for t in order) + "\n"
open(f"e1/ddl/{DB}.canonical.sql", "w").write(ddl)
print(DB, "tables", len(tabs), "order", " ".join(order), "| dropped columns:", dropped)
