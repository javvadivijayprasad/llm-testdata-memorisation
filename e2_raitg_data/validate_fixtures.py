#!/usr/bin/env python3
"""Load each fixture into a scratch copy of the real SUT database and exercise the SUT through its
own app object (login for flaskr; GET /players for fastapi-restful; GET /tasks for task-manager).
Run under the matching venv: venv_flask for flaskr, venv_fastapi for the two FastAPI SUTs."""
import os, sys, shutil, sqlite3, tempfile, importlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fixture_loader as fl
SUTS = "/home/claude/work/paperE/W/suts"
which, arm = sys.argv[1], sys.argv[2]
if which == "flaskr":
    sut = f"{SUTS}/sut3_flaskr"; sys.path.insert(0, sut)
    from flaskr import create_app
    db = tempfile.mkstemp(suffix=".sqlite")[1]
    schema = open(f"{sut}/flaskr/schema.sql").read()
    if arm == "human":
        con = sqlite3.connect(db); con.executescript(schema); con.executescript(open(f"{sut}/tests/data.sql").read()); con.commit(); con.close()
        creds = [("test", "test"), ("other", "other")]
    else:
        fl.load_flaskr(db, arm, schema)
        creds = [(r["username"], r["password"]) for r in fl.rows_of("flaskr", "user", fl.PROFILES[arm])]
    app = create_app({"TESTING": True, "DATABASE": db}); c = app.test_client()
    con = sqlite3.connect(db); print("users", con.execute("select count(*) from user").fetchone()[0], "posts", con.execute("select count(*) from post").fetchone()[0])
    ok = 0
    for u, p in creds:
        r = c.post("/auth/login", data={"username": u, "password": p}); ok += (r.status_code == 302 and r.headers.get("Location", "").endswith("/"))
        c.get("/auth/logout")
    print("logins ok", ok, "of", len(creds)); r = c.get("/"); print("index", r.status_code, "posts rendered", r.data.count(b'class="post"'))
elif which == "fastapi_restful":
    sut = f"{SUTS}/sut2_fastapi_restful"; sys.path.insert(0, sut)
    db = os.path.join(tempfile.mkdtemp(), "players.db"); shutil.copy(f"{sut}/players-sqlite3.db", db)
    fl.load_players(db, arm); os.environ["STORAGE_PATH"] = db
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        r = c.get("/players/"); print("GET /players", r.status_code, "count", len(r.json()) if r.status_code == 200 else r.text[:200])
        first = r.json()[0] if r.status_code == 200 else None
        if first: rr = c.get(f"/players/squadnumber/{first['squadNumber']}"); print("by squad number", rr.status_code, rr.json().get("firstName"))
elif which == "fastapi_task_manager":
    sut = f"{SUTS}/sut4_fastapi_task_manager"; sys.path.insert(0, sut)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.main as m, app.database as d
    from app.database import Base, get_db
    db = os.path.join(tempfile.mkdtemp(), "t.db"); eng = create_engine("sqlite:///" + db, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng); fl.load_tasks(eng, arm)
    SL = sessionmaker(bind=eng)
    def ovr():
        s = SL()
        try: yield s
        finally: s.close()
    m.app.dependency_overrides[get_db] = ovr
    from fastapi.testclient import TestClient
    c = TestClient(m.app); r = c.get("/tasks/"); print("GET /tasks", r.status_code, "count", len(r.json()) if r.status_code == 200 else r.text[:200])
    r2 = c.get("/tasks/?completed=true"); print("completed filter", r2.status_code, len(r2.json()) if r2.status_code == 200 else r2.text[:100])
