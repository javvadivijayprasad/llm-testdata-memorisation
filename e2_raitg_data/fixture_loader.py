"""E2 fixture loader — loads a provisioned fixture (CSV files from SynthData, or the project's own
human fixture) into the SUT's SQLite database exactly as the scoring harness sees it.

Used by (a) the harness conftests (per arm) at scoring time and (b) validate_fixtures.py.
Arms: 'func' = functional profile rows loaded; 'all' = the SAME functional rows loaded (identical DB
state to 'func'), while the edge rows (valid boundary payloads) and negative rows (invalid payloads,
each tagged with its violation) are only SHOWN to the model as inputs to try — so 'all' vs 'func'
isolates the effect of the boundary/negative information, not of a different database; 'human' = the
project's shipped fixture (flaskr tests/data.sql; fastapi-restful pristine players.db; task-manager
ships none → empty tables, identical to the G baseline).

flaskr password convention: the fixture's `password` column holds the PLAIN-TEXT credential (the
business case says so); the loader stores generate_password_hash(plain) so that a test can log in
with the plain value shown in the [TEST DATA] block. The human fixture's plain values are 'test' and
'other' (the project's own tests/conftest.py).
"""
import csv, os, sqlite3

FIX = os.environ.get("E2_FIXTURES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))
PROFILES = {"func": ["functional"], "all": ["functional"]}


def rows_of(sut, table, profiles):
    out = []
    for prof in profiles:
        f = os.path.join(FIX, sut, prof, f"{table}.csv")
        if os.path.exists(f):
            out += list(csv.DictReader(open(f, newline="", encoding="utf-8")))
    return out


def _v(x):
    return None if x == "" else x


def _b(x):
    return None if x == "" else (1 if str(x).lower() in ("true", "1", "t") else 0)


# ---------------------------------------------------------------- flaskr (sqlite file)
_HASHES = {}


def _pw_hash(plain):
    """Memoised werkzeug hash with a low PBKDF2 iteration count. The harness re-provisions the
    database before every test and on every init_db() call, and the mutation scorer counts a
    90-second pytest timeout as a kill, so hashing cost must not depend on the arm: with the
    default 260k iterations five users cost ~1 s per reset and pushed the flaskr baseline past
    the timeout. check_password_hash() reads the method from the stored hash, so logins are
    unaffected."""
    if plain not in _HASHES:
        from werkzeug.security import generate_password_hash
        _HASHES[plain] = generate_password_hash(plain, method="pbkdf2:sha256:1000")
    return _HASHES[plain]

def load_flaskr_rows(con, arm):
    """Insert the fixture rows into an OPEN connection whose schema already exists (used by the
    harness wrapper around flaskr.db.init_db, so every database a test initialises gets the rows).
    No-op for 'human' (the project's data.sql is loaded by the v2 shim) and when rows exist."""
    if arm == "human" or con.execute("SELECT count(*) FROM user").fetchone()[0]:
        return
    for r in rows_of("flaskr", "user", PROFILES[arm]):
        con.execute("INSERT INTO user (id, username, password) VALUES (?, ?, ?)",
                    (int(r["id"]), r["username"], _pw_hash(r["password"])))
    for r in rows_of("flaskr", "post", PROFILES[arm]):
        con.execute("INSERT INTO post (id, author_id, created, title, body) VALUES (?, ?, ?, ?, ?)",
                    (int(r["id"]), int(r["author_id"]), r["created"], r["title"], r["body"]))
    con.commit()


def load_flaskr(db_path, arm, schema_sql):
    """Create schema in a file and load users/posts (validation helper / instance db)."""
    con = sqlite3.connect(db_path)
    con.executescript(schema_sql)
    load_flaskr_rows(con, arm)
    con.commit(); con.close()


# ---------------------------------------------------------------- fastapi-restful (players.db)
PLAYER_COLS = ["id", "firstName", "middleName", "lastName", "dateOfBirth", "squadNumber", "position",
               "abbrPosition", "team", "league", "starting11"]


def load_players(db_path, arm):
    """db_path is a copy of the project's pristine players-sqlite3.db; for non-human arms its 26
    shipped rows are replaced by the fixture rows (alembic_version table untouched)."""
    if arm == "human":
        return
    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM players")
    for r in rows_of("fastapi_restful", "players", PROFILES[arm]):
        vals = [_v(r[c]) for c in PLAYER_COLS[:-1]] + [_b(r["starting11"])]
        vals[5] = int(vals[5])
        con.execute("INSERT INTO players (" + ", ".join(f'"{c}"' for c in PLAYER_COLS) + ") VALUES (" + ",".join("?" * len(PLAYER_COLS)) + ")", vals)
    con.commit(); con.close()


# ---------------------------------------------------------------- fastapi-task-manager (SQLAlchemy engine)
def load_tasks(engine, arm):
    """Insert fixture rows through the app's own Task model so column types match."""
    if arm == "human":
        return
    from sqlalchemy.orm import sessionmaker
    from app.models import Task
    with engine.connect() as c:
        if c.exec_driver_sql("SELECT count(*) FROM tasks").scalar():
            return                         # already provisioned on this engine
    from datetime import datetime
    S = sessionmaker(bind=engine)
    s = S()
    for r in rows_of("fastapi_task_manager", "tasks", PROFILES[arm]):
        def dt(x):
            return datetime.fromisoformat(x) if x else None
        s.add(Task(id=int(r["id"]), title=r["title"], description=_v(r["description"]),
                   completed=bool(_b(r["completed"])), created_at=dt(r["created_at"]), updated_at=dt(r["updated_at"])))
    s.commit(); s.close()
