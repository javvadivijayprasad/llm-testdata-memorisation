#!/usr/bin/env python3
"""E1b — RENAMED-SCHEMA CONTROL for the memorisation threat.

Produces, for each subject S, a subject "S_r" whose canonical DDL, business case and row targets are
identical to S's except that every table and column identifier is replaced by a semantics-preserving
synonym (customer -> client, order -> purchase, film -> movie, ...), the dataset's name and its
documentation sources are removed from the case text, and the same word map is applied to the prose so
that the case and the DDL stay consistent. Types, constraints, CHECK value lists, row targets, seeds
and prompts are unchanged, so a difference between S and S_r isolates what the LLM knows about the
*published* dataset (Northwind, Sakila/Pagila, Chinook, ...) from what it can do with a schema + case.

Outputs: ddl/<S>_r.canonical.sql, cases/<S>_r.txt (+ MD5 in cases_MD5.txt), row_targets.json entries,
human_cache/<S>_r/<renamed table>.csv (human fixtures with renamed headers, for metrics_fidelity),
rename_maps/<S>.json (old -> new for tables and columns; the reverse map is implied).
usage: rename_schema.py            (all five subjects)"""
import json, os, re, hashlib, csv, glob

HERE = os.path.dirname(os.path.abspath(__file__))
SUBJECTS = ["chinook", "northwind", "dellstore2", "pagila", "employees"]

# word-level synonym map (applied to '_'-separated identifier words and, case-insensitively, to prose)
WORDS = {
    "customer": "client", "customers": "clients", "cust": "cli",
    "order": "purchase", "orders": "purchases", "orderline": "purchase_line", "orderlines": "purchase_lines",
    "product": "item", "products": "items", "prod": "itm",
    "employee": "worker", "employees": "workers", "emp": "wkr",
    "supplier": "vendor", "suppliers": "vendors",
    "shipper": "carrier", "shippers": "carriers",
    "category": "section", "categories": "sections",
    "region": "zone", "regions": "zones",
    "territory": "area", "territories": "areas",
    "invoice": "bill", "invoices": "bills",
    "track": "song", "tracks": "songs",
    "album": "record", "albums": "records",
    "artist": "performer", "artists": "performers",
    "playlist": "collection", "playlists": "collections",
    "genre": "style", "genres": "styles",
    "media": "format",
    "film": "movie", "films": "movies",
    "actor": "cast_member", "actors": "cast_members",
    "rental": "loan", "rentals": "loans",
    "inventory": "stock",
    "payment": "receipt", "payments": "receipts",
    "staff": "clerk",
    "store": "branch", "stores": "branches",
    "language": "locale", "languages": "locales",
    "address": "location", "addresses": "locations",
    "city": "town", "cities": "towns",
    "country": "nation", "countries": "nations",
    "department": "division", "departments": "divisions", "dept": "div",
    "salary": "pay_amount", "salaries": "pay_history",
    "title": "designation", "titles": "designations",
    "manager": "lead", "managers": "leads",
    "demographics": "profiles", "demo": "profile",
    "hist": "history",
    "first": "given", "last": "family",
    "birth": "born", "hire": "joined",
    "unit": "each", "price": "cost",
    "quantity": "qty", "discount": "rebate", "freight": "shipping_fee",
    "phone": "tel", "fax": "fax_no", "email": "mail_addr",
    "postal": "zip", "zip": "postcode",
    "ship": "deliver", "shipped": "dispatched", "required": "due",
    "reports": "answers",
    "state": "province", "states": "provinces",
    "reorder": "restock", "reordered": "restocked",
    "discontinued": "retired",
    "notes": "remarks", "photo": "image", "picture": "graphic", "homepage": "website",
    "description": "summary", "desc": "summ",
    "billing": "charge", "bytes": "size_bytes", "composer": "writer", "milliseconds": "duration_ms",
    "support": "agent", "rep": "person", "total": "sum_total", "company": "firm",
    "active": "enabled", "activebool": "enabled_flag", "amount": "value_paid",
    "create": "created", "district": "county", "length": "runtime",
    "original": "source", "rating": "certificate", "release": "issued",
    "duration": "period", "rate": "fee", "replacement": "replace",
    "return": "returned", "special": "extra", "features": "options",
    "update": "modified", "name": "label", "username": "login", "password": "secret",
    "gender": "sex_code", "from": "start", "to": "end",
    "age": "years_old", "income": "earnings", "creditcard": "card", "creditcardtype": "card_type",
    "creditcardexpiration": "card_expiry", "netamount": "net_value", "totalamount": "gross_value",
    "tax": "levy", "sales": "sold_count", "common": "related", "quan": "qty", "low": "minimum",
    "expected": "anticipated", "extension": "ext_no", "courtesy": "honorific", "via": "by",
    "us": "na", "abbr": "code", "level": "threshold", "units": "pieces", "on": "on", "in": "in",
    "id": "id", "date": "date", "no": "no", "line": "line", "details": "lines", "type": "type",
    "path": "path", "per": "per", "year": "year", "cost": "cost", "contact": "contact",
    "home": "home", "expiration": "expiry", "reorder_level": "restock_threshold",
}
# glued (no underscore) identifiers that the word map cannot split
GLUED = {"orderid": "purchase_id", "customerid": "client_id", "orderlineid": "purchase_line_id",
         "categoryname": "section_label", "firstname": "given_name", "lastname": "family_name",
         "netamount": "net_value", "totalamount": "gross_value", "orderdate": "purchase_date",
         "creditcard": "card_no", "creditcardtype": "card_type", "creditcardexpiration": "card_expiry",
         "address1": "location1", "address2": "location2", "activebool": "enabled_flag",
         "prod_id": "item_id", "common_prod_id": "related_item_id",
         "first_name": "given_name", "last_name": "family_name", "last_update": "modified_on",
         "reports_to": "manager_ref", "support_rep_id": "agent_id", "title_of_courtesy": "honorific",
         "us_states": "state_codes", "company_name": "firm_name", "contact_name": "contact_person",
         "product_name": "item_name", "category_name": "section_name", "dept_name": "div_name",
         "ship_name": "deliver_name", "state_name": "province_name", "region_description": "zone_text",
         "territory_description": "area_text", "customer_desc": "client_text"}
SQL_RESERVED = {"order", "group", "user", "table", "column", "index", "key", "primary", "references", "check",
                "default", "limit", "offset", "from", "to", "select", "where", "and", "or", "not", "null",
                "in", "is", "as", "on", "by", "end", "start", "level", "type", "date", "time", "name",
                "value", "values", "year", "month", "day", "position", "action", "language", "role",
                "format", "sum", "count", "min", "max", "text", "integer", "boolean", "numeric", "int"}

def rename_ident(ident):
    if ident in GLUED: return GLUED[ident]
    words = ident.split("_")
    out = [WORDS.get(w, w) for w in words]
    new = "_".join(out)
    return new

def main():
    ddl_dir, case_dir = f"{HERE}/ddl", f"{HERE}/cases"
    os.makedirs(f"{HERE}/rename_maps", exist_ok=True)
    targets = json.load(open(f"{HERE}/row_targets.json"))
    md5 = dict(l.split()[::-1] for l in open(f"{HERE}/cases_MD5.txt") if l.strip()) if os.path.exists(f"{HERE}/cases_MD5.txt") else {}
    for S in SUBJECTS:
        ddl = open(f"{ddl_dir}/{S}.canonical.sql").read()
        tables = re.findall(r"^CREATE TABLE (\w+) \(", ddl, re.M)
        cols = set()
        for t in tables:
            blk = re.search(rf"^CREATE TABLE {t} \((.*?)^\);", ddl, re.M | re.S).group(1)
            for line in blk.splitlines():
                line = line.strip().rstrip(",")
                if not line or re.match(r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CHECK)\b", line): continue
                cols.add(line.split()[0])
        idents = set(tables) | cols
        m = {i: rename_ident(i) for i in sorted(idents)}
        # sanity: every identifier changed, no collisions, no reserved words, no ident maps onto another old ident
        unchanged = [i for i, n in m.items() if i == n]
        assert not unchanged, (S, "unchanged", unchanged)
        assert len(set(m.values())) == len(m), (S, "collision", [v for v in m.values() if list(m.values()).count(v) > 1])
        bad = [n for n in m.values() if n in SQL_RESERVED]; assert not bad, (S, "reserved", bad)
        tmap = {t: m[t] for t in tables}
        # rewrite DDL: replace identifier tokens (word-boundary) everywhere — the canonical DDL only uses
        # these words as identifiers (types/keywords never collide with a mapped identifier by construction)
        ddl_r = rewrite_ddl(ddl, m)
        Sr = f"{S}_r"
        open(f"{ddl_dir}/{Sr}.canonical.sql", "w").write(ddl_r)
        # case text: drop the dataset name / source sentences, then apply word map to prose
        case = open(f"{case_dir}/{S}.txt", encoding="utf-8").read()
        case = strip_identity(S, case)
        case = rename_prose(case, idents, m, set(tables))
        open(f"{case_dir}/{Sr}.txt", "w", encoding="utf-8").write(case)
        md5[f"{Sr}.txt"] = hashlib.md5(case.encode("utf-8")).hexdigest()
        # row targets
        targets[Sr] = {tmap[t]: v for t, v in targets[S].items()}
        # human cache with renamed headers
        os.makedirs(f"{HERE}/human_cache/{Sr}", exist_ok=True)
        for t in tables:
            src = f"{HERE}/human_cache/{S}/{t}.csv"
            if not os.path.exists(src):
                fetch_human(S, t, src)
            raw = open(src, "rb").read()
            head, _, body = raw.partition(b"\n")
            hdr = [m.get(h, h) for h in head.decode("utf-8").strip().split(",")]
            with open(f"{HERE}/human_cache/{Sr}/{tmap[t]}.csv", "wb") as f:      # header renamed, rows byte-identical
                f.write(",".join(hdr).encode("utf-8") + b"\n" + body)
        json.dump({"subject": S, "renamed_subject": Sr, "tables": tmap, "columns": {c: m[c] for c in sorted(cols)}},
                  open(f"{HERE}/rename_maps/{S}.json", "w"), indent=1)
        print(f"{S}: {len(tables)} tables, {len(cols)} columns renamed -> {Sr}")
    json.dump(targets, open(f"{HERE}/row_targets.json", "w"), indent=1)
    with open(f"{HERE}/cases_MD5.txt", "w") as f:
        for k in sorted(md5): f.write(f"{md5[k]}  {k}\n")

IDENTITY = {
    "chinook": [(r"Business case: Chinook models a digital media store \(an iTunes-like online music shop\)", "Business case: the company runs a digital media store (an online music shop)"),
                (r"\nSource: the chinook-database README, not the shipped data\.", "")],
    "northwind": [(r"Business case: Northwind models", "Business case: the company is"),
                  (r"\nSource: the classic Microsoft Northwind documentation and the northwind_psql README, not the\nshipped data\.", "")],
    "dellstore2": [(r"Business case: Dell DVD Store 2 models", "Business case: the company runs"),
                   (r"Source: the Dell DVD Store documentation \(linux\.dell\.com/dvdstore\) and the[^\n]*\n[^\n]*\n?", "")],
    "employees": [(r'Business case: the "employees" sample database models', "Business case: the database models"),
                  (r"Source: the MySQL Employees Sample Database documentation \(dev\.mysql\.com/doc/employee\)\n[^\n]*shipped data\.", "")],
    "pagila": [(r"Business case: Pagila \(PostgreSQL port of the Sakila sample database\) models", "Business case: the company runs"),
               (r"Source: pagila README and the MySQL Sakila documentation \(dev\.mysql\.com/doc/sakila\),[^\n]*\n[^\n]*\n?", "")],
}
def rewrite_ddl(ddl, m):
    """Positional rewrite: table name on CREATE TABLE lines; first token on column lines; identifiers
    inside the parentheses of PRIMARY KEY / FOREIGN KEY / UNIQUE / CHECK lines and after REFERENCES.
    Keywords and type names are never touched even if an identifier happens to equal one ('name')."""
    out = []
    for line in ddl.splitlines():
        mo = re.match(r"^(CREATE TABLE )(\w+)( \()", line)
        if mo: out.append(mo.group(1) + m[mo.group(2)] + mo.group(3)); continue
        st = line.strip()
        if not st or st == ");" or st.startswith("--"): out.append(line); continue
        if re.match(r"(PRIMARY KEY|UNIQUE)\b", st):
            out.append(re.sub(r"\((.*?)\)", lambda g: "(" + ", ".join(m[c.strip()] for c in g.group(1).split(",")) + ")", line, count=1)); continue
        if st.startswith("FOREIGN KEY"):
            def fk(g): return f"FOREIGN KEY ({m[g.group(1)]}) REFERENCES {m[g.group(2)]}({m[g.group(3)]})"
            out.append(re.sub(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\((\w+)\)", fk, line)); continue
        if st.startswith("CHECK"):
            out.append(re.sub(r"CHECK \((\w+) ", lambda g: f"CHECK ({m[g.group(1)]} ", line, count=1)); continue
        ind = line[:len(line) - len(line.lstrip())]
        first, rest = st.split(" ", 1)
        assert first in m, ("column not in map", first)
        rest = re.sub(r"CHECK \((\w+) ", lambda g: f"CHECK ({m.get(g.group(1), g.group(1))} ", rest)
        rest = re.sub(r"REFERENCES (\w+)\((\w+)\)", lambda g: f"REFERENCES {m[g.group(1)]}({m[g.group(2)]})", rest)
        out.append(ind + m[first] + " " + rest)
    return "\n".join(out) + ("\n" if ddl.endswith("\n") else "")

def strip_identity(S, text):
    for pat, rep in IDENTITY[S]:
        text, n = re.subn(pat, rep, text)
        assert n == 1, (S, "identity pattern not found", pat)
    for w in ("Chinook", "Northwind", "Sakila", "Pagila", "Dell", "MySQL", "Microsoft", "iTunes"):
        assert w not in text, (S, "identity word remains", w)
    return text

PAIRS = [("customer","customers"),("order","orders"),("orderline","orderlines"),("product","products"),
         ("employee","employees"),("supplier","suppliers"),("shipper","shippers"),("category","categories"),
         ("region","regions"),("territory","territories"),("invoice","invoices"),("track","tracks"),
         ("album","albums"),("artist","artists"),("playlist","playlists"),("genre","genres"),("film","films"),
         ("actor","actors"),("rental","rentals"),("payment","payments"),("store","stores"),
         ("language","languages"),("department","departments"),("salary","salaries"),("title","titles"),
         ("inventory","inventories")]
PROSE_OVERRIDE = {"salaries": "pay amounts", "salary": "pay amount", "inventory": "stock", "inventories": "stock"}

def rename_prose(text, idents, m, tables):
    """Apply the identifier map to code-like tokens (snake_case identifiers) and, for the entity nouns
    that are TABLE names of this subject, the word map to plain words, case-insensitively, preserving
    capitalisation. Generic column words (name, date, quantity, ...) are left alone in prose."""
    text = text.replace("on the order of", "roughly")
    code = [i for i in idents if "_" in i]
    if code:
        tok = re.compile(r"\b(" + "|".join(sorted(map(re.escape, code), key=len, reverse=True)) + r")\b")
        text = tok.sub(lambda mo: m[mo.group(1)], text)
    nouns = {}
    for sg, pl in PAIRS:
        if sg in tables or pl in tables:
            for w in (sg, pl): nouns[w] = PROSE_OVERRIDE.get(w, WORDS.get(w, w)).replace("_", " ")
    def word(mo):
        w = mo.group(0); lw = w.lower()
        if lw not in nouns: return w
        r = nouns[lw]
        return r[0].upper() + r[1:] if w[0].isupper() else r
    text = re.compile(r"\b[A-Za-z]+\b").sub(word, text)
    text = re.sub(r"\b([Aa])n(\s+)(?=[^aeiouAEIOU\W])", r"\1\2", text)   # "an worker" -> "a worker"
    text = re.sub(r"\b([Aa])(\s+)(?=[aeioAEIO])", r"\1n\2", text)          # "a item" -> "an item" (u-words left alone)
    return text

def fetch_human(S, t, dst):
    import subprocess
    subprocess.run(["psql", "-d", f"{S}_canon", "-Atc", f"\\copy (select * from {t} limit 50000) to '{dst}' with (format csv, header true)"],
                   check=True, capture_output=True)

if __name__ == "__main__":
    main()
