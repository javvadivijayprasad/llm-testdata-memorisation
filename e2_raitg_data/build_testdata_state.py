#!/usr/bin/env python3
"""E2c (Paper H, 17 Sep 2026): build the `state` [TEST DATA] blocks = the frozen `func` block, byte for
byte, followed by an explicit DATABASE STATE CONTRACT. The database state at scoring is identical to
the func arm (the same functional fixture is pre-loaded); only the information given to the model
changes. This isolates the question E2 left open: does telling the generator which ids are taken and
that counts start at N remove the empty-database assumption that lowered usable yield?

usage: build_testdata_state.py    -> testdata/state/<app>.txt + testdata/TESTDATA_MD5.txt updated"""
import hashlib, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
TD = os.path.join(HERE, "testdata")
os.makedirs(os.path.join(TD, "state"), exist_ok=True)

CONTRACT = {
    "fastapi-task-manager": """
[DATABASE STATE CONTRACT — read before writing any assertion]
- Before EVERY test the `tasks` table contains exactly the 20 rows above (ids 1-20) and nothing else. The table is never empty.
- A task your test creates receives the next free id: the FIRST task created in a test gets id 21, the second 22, and so on. Never assume a task you created has id 1; capture the id from the create response.
- Count assertions must be relative to the pre-loaded rows: after creating one task, GET /tasks returns 21 items, not 1. Prefer `len(after) == len(before) + 1`, or filter the list by the id you created.
- Ids 1-20 are pre-loaded rows: use them for GET/PUT/DELETE tests of an EXISTING task (their field values are listed above); do not expect them to be absent.
- A test that needs an empty table must delete all 20 rows through the API first; do not assume emptiness.
- Do not rely on the order of the pre-loaded rows unless the API documents an ordering.
""",
    "flaskr": """
[DATABASE STATE CONTRACT — read before writing any assertion]
- Before EVERY test the database contains exactly the 5 users (ids 1-5) and 20 posts (ids 1-20) above, and nothing else. The tables are never empty.
- A post your test creates receives id 21 (the next free id), a user your test registers receives id 6. Never assume a row you created has id 1.
- The index page already lists the 20 pre-loaded posts; assert the presence of YOUR post's title, not that the page has one post. Count assertions must be relative to the pre-loaded rows.
- Log in with one of the listed username/password pairs; registering a listed username fails because it already exists.
- Posts 1-20 belong to the authors shown: only the author can edit or delete a post (author_id must match the logged-in user), so choose a post whose author you logged in as for update/delete tests, and a different author's post for the 403 tests.
- A test that needs an empty database must delete the rows through the application first; do not assume emptiness.
""",
    "fastapi-restful": """
[DATABASE STATE CONTRACT — read before writing any assertion]
- Before EVERY test the players collection contains exactly the 26 rows above (squad numbers 1-26) and nothing else. It is never empty.
- Squad numbers 1-26 are TAKEN: creating a player with one of them is a duplicate (expect the documented conflict response). Use squad numbers 27 and above for players your test creates.
- Count assertions must be relative to the pre-loaded rows: after creating one player, GET /players returns 27 items, not 1. Prefer `len(after) == len(before) + 1`, or look up the player you created by its squad number.
- Use the listed rows for GET/PUT/DELETE tests of an EXISTING player (by squad number); do not expect them to be absent.
- A test that needs an empty collection must delete the pre-loaded players through the API first; do not assume emptiness.
- Note: the service caches list responses for ten minutes; a test must not depend on state created by an earlier test.
""",
}

md5 = {}
for app, contract in CONTRACT.items():
    src = os.path.join(TD, "func", f"{app}.txt")
    func = open(src, encoding="utf-8").read()
    n_rows = re.findall(r"table (\w+) \((\d+) rows\)", func)
    assert n_rows, app
    out = func.rstrip("\n") + "\n" + contract.rstrip("\n") + "\n"
    dst = os.path.join(TD, "state", f"{app}.txt")
    open(dst, "w", encoding="utf-8", newline="\n").write(out)
    md5[f"state/{app}.txt"] = hashlib.md5(out.encode("utf-8")).hexdigest()
    print(app, n_rows, md5[f"state/{app}.txt"])

# extend TESTDATA_MD5.txt (keep existing lines)
p = os.path.join(TD, "TESTDATA_MD5.txt")
lines = [l for l in open(p, encoding="utf-8").read().splitlines() if l.strip() and not l.split()[-1].startswith("state/")]
for k, v in sorted(md5.items()):
    lines.append(f"{v}  {k}")
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("TESTDATA_MD5.txt updated")
