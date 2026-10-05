#!/usr/bin/env python3
"""Constraint counts per schema from the canonical DDLs (e1_datastudy/ddl/<schema>.canonical.sql)."""
import re, sys, os
D = sys.argv[1] if len(sys.argv) > 1 else "../exp/e1/ddl"
for s in ["pagila", "chinook", "northwind", "employees", "dellstore2"]:
    d = open(f"{D}/{s}.canonical.sql").read()
    tables = re.findall(r"^CREATE TABLE (\w+) \(", d, re.M)
    cols = nn = 0
    for t in tables:
        block = re.search(rf"^CREATE TABLE {t} \((.*?)^\);", d, re.M | re.S).group(1)
        for line in block.splitlines():
            line = line.strip().rstrip(",")
            if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
            cols += 1; nn += "NOT NULL" in line
    print(s, len(tables), cols, len(re.findall(r"PRIMARY KEY", d)), len(re.findall(r"FOREIGN KEY", d)),
          len(re.findall(r"^\s*UNIQUE", d, re.M)), len(re.findall(r"CHECK", d)), nn)
