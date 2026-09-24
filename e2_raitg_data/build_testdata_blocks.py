#!/usr/bin/env python3
"""Build the [TEST DATA] text blocks injected into the RAITG prompt for each (arm, app).
arm func : functional rows (pre-loaded in the DB under test)
arm all  : functional rows (pre-loaded) + edge rows (valid boundary payloads, NOT loaded) + negative
           rows with their _violation tag (invalid payloads the API must reject, NOT loaded)
arm human: the project's own shipped fixture (flaskr tests/data.sql; fastapi-restful players.db);
           fastapi-task-manager ships none → block states the table is empty.
httpbin has no database → no block in any arm (negative control).
Output: testdata/<arm>/<app>.txt + testdata/TESTDATA_MD5.txt"""
import csv, os, sqlite3, hashlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = f"{HERE}/fixtures"; SUTS = "/home/claude/work/paperE/W/suts"
APPS = {"flaskr": ("flaskr", ["user", "post"]), "fastapi-restful": ("fastapi_restful", ["players"]),
        "fastapi-task-manager": ("fastapi_task_manager", ["tasks"])}
NOTES = {
    "flaskr": ("Whenever the application database is initialised — the default instance/flaskr.sqlite before every test, "
               "the harness `app` fixture, or any database a test itself initialises with init_db() / `flask init-db` — it "
               "contains exactly these rows (ids as shown). Passwords are stored hashed; the `password` values shown here "
               "are the PLAIN-TEXT credentials that log these users in via POST /auth/login."),
    "fastapi-restful": ("The players database used by the app (STORAGE_PATH) contains exactly these rows before every test; "
                        "`squadNumber` is the key for GET/PUT/DELETE /players/squadnumber/{n}. Column names are the JSON field names."),
    "fastapi-task-manager": ("Whenever the schema is created — the app's database before every test, or any engine a test "
                             "itself initialises with Base.metadata.create_all() — the tasks table contains exactly these "
                             "rows (ids as shown); `completed` is a boolean, timestamps are ISO strings."),
}

def csv_rows(path):
    return list(csv.DictReader(open(path, newline="", encoding="utf-8"))) if os.path.exists(path) else []

def table_text(name, rows, cols=None):
    if not rows: return f"table {name}: (empty)\n"
    cols = cols or list(rows[0].keys())
    out = [f"table {name} ({len(rows)} rows) columns: " + ", ".join(cols)]
    def cell(v):
        v = "" if v in (None, "") else str(v)
        return v if len(v) <= 60 else v[:30] + f"…[{len(v)} chars total]"
    for r in rows: out.append("  " + " | ".join(cell(r.get(c)) for c in cols))
    return "\n".join(out) + "\n"

def human_rows(app):
    if app == "flaskr":
        return {"user": [{"id": "1", "username": "test", "password": "test"}, {"id": "2", "username": "other", "password": "other"}],
                "post": [{"id": "1", "author_id": "1", "created": "2018-01-01 00:00:00", "title": "test title", "body": "test\\nbody"}]}
    if app == "fastapi-restful":
        con = sqlite3.connect(f"{SUTS}/sut2_fastapi_restful/players-sqlite3.db"); con.row_factory = sqlite3.Row
        return {"players": [dict(r) for r in con.execute('select * from players order by "squadNumber"')]}
    return {"tasks": []}

os.makedirs(f"{HERE}/testdata", exist_ok=True); md5 = {}
for arm in ["func", "all", "human"]:
    os.makedirs(f"{HERE}/testdata/{arm}", exist_ok=True)
    for app, (sut, tables) in APPS.items():
        parts = ["[TEST DATA — provisioned fixture for the database under test]", NOTES[app], ""]
        if arm == "human":
            hr = human_rows(app)
            if app == "fastapi-task-manager":
                parts.append("The project ships no fixture data: the tasks table is EMPTY before every test.")
            else:
                parts.append("Source: the project's own shipped fixture data.")
                for t in tables: parts.append(table_text(t, hr[t]))
        else:
            parts.append("Source: SynthData functional profile (constraint-valid rows generated from the schema + business case).")
            for t in tables: parts.append(table_text(t, csv_rows(f"{FIX}/{sut}/functional/{t}.csv")))
            if arm == "all":
                parts.append("ADDITIONAL INPUTS (NOT in the database — use them as request payloads):")
                parts.append("Boundary-valid rows (edge profile: CHECK endpoints, max-length strings, NULLs in nullable columns) — the API should ACCEPT these:")
                for t in tables: parts.append(table_text(t, csv_rows(f"{FIX}/{sut}/edge/{t}.csv")))
                parts.append("Invalid rows (negative profile; the `_violation` column names the constraint each row breaks) — the API should REJECT these:")
                for t in tables: parts.append(table_text(t, csv_rows(f"{FIX}/{sut}/negative/{t}.csv")))
        text = "\n".join(parts).rstrip() + "\n"
        p = f"{HERE}/testdata/{arm}/{app}.txt"; open(p, "w", encoding="utf-8").write(text)
        md5[f"{arm}/{app}.txt"] = hashlib.md5(text.encode()).hexdigest()
        print(arm, app, len(text), "chars")
with open(f"{HERE}/testdata/TESTDATA_MD5.txt", "w") as f:
    for k in sorted(md5): f.write(f"{md5[k]}  {k}\n")
