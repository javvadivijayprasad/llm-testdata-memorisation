#!/usr/bin/env python3
"""Arm 4 — FAKER BASELINE: the ecosystem default. A plain Faker script driven only by the column
types in the canonical DDL: sequential integer PKs, type-appropriate fake values respecting
varchar(n)/char(n)/numeric(p,s), NOT NULL honoured, nullable columns 10 % NULL, **no referential
resolution** (FK columns get random integers in 1..target-of-parent, as a typical hand-written
Faker script does), no CHECK awareness, no composite-key awareness. Seeded (Faker.seed).
usage: arm_faker.py <subject> <out_dir> [seed]"""
import csv, json, os, re, sys, random, datetime
from faker import Faker

subject, out_dir = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42
HERE = os.path.dirname(os.path.abspath(__file__))
ddl = open(f"{HERE}/ddl/{subject}.canonical.sql").read()
targets = json.load(open(f"{HERE}/row_targets.json"))[subject]
tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
Faker.seed(seed); fake = Faker(); rng = random.Random(seed)
os.makedirs(out_dir, exist_ok=True)

def table_block(t):
    return re.search(rf"^CREATE TABLE {t} \((.*?)^\);", ddl, re.M | re.S).group(1)

def columns(t):
    cols = []
    for line in table_block(t).splitlines():
        line = line.strip().rstrip(",")
        if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
        name, typ = line.split()[0], line.split()[1]
        cols.append({"name": name, "type": typ.lower(), "notnull": "NOT NULL" in line})
    pk = re.search(r"PRIMARY KEY \(([^)]*)\)", table_block(t))
    pks = [c.strip() for c in pk.group(1).split(",")] if pk else []
    fks = {c: (p, pc) for c, p, pc in re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", table_block(t))}
    return cols, pks, fks

def value(col, i, pks, fks, t):
    n, typ = col["name"], col["type"]
    if n in fks:
        p = fks[n][0]; return rng.randint(1, max(1, targets[p]["target"]))
    if n in pks and len(pks) == 1 and re.match(r"integer|bigint|smallint", typ): return i
    if not col["notnull"] and rng.random() < 0.10: return ""
    m = re.match(r"(varchar|char)\((\d+)\)", typ)
    if m:
        L = int(m.group(2))
        if "email" in n: s = fake.email()
        elif "name" in n: s = fake.name()
        elif "phone" in n or "fax" in n: s = fake.phone_number()
        elif "city" in n: s = fake.city()
        elif "country" in n: s = fake.country()
        elif "address" in n: s = fake.street_address()
        elif "state" in n: s = fake.state_abbr()
        elif "zip" in n or "postal" in n: s = fake.postcode()
        elif "title" in n: s = fake.catch_phrase()
        else: s = fake.word() if L < 12 else fake.sentence(nb_words=4)
        return s[:L]
    if typ == "text": return fake.sentence(nb_words=8)
    if re.match(r"integer|bigint|smallint", typ):
        if n in pks: return i
        return rng.randint(1, 1000)
    m = re.match(r"numeric\((\d+),(\d+)\)", typ)
    if m:
        p, s = int(m.group(1)), int(m.group(2)); return round(rng.uniform(0, 10 ** (p - s) - 1), s)
    if typ.startswith("numeric") or typ in ("real", "double"): return round(rng.uniform(0, 1000), 2)
    if typ == "boolean": return rng.choice(["true", "false"])
    if typ == "date": return fake.date_between("-3y", "today").isoformat()
    if typ.startswith("timestamp"): return fake.date_time_between("-3y", "now").strftime("%Y-%m-%d %H:%M:%S")
    if typ == "time": return fake.time()
    if typ == "bytea": return ""
    return fake.word()

for t in tables:
    cols, pks, fks = columns(t)
    with open(f"{out_dir}/{t}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow([c["name"] for c in cols])
        for i in range(1, targets[t]["target"] + 1):
            w.writerow([value(c, i, pks, fks, t) for c in cols])
print("faker", subject, sum(v["target"] for v in targets.values()), "rows, seed", seed)
