"""Paper H / E2 scoring wrapper around pipeline_v2 (protocol unchanged) that makes the harness
conftests pre-load the arm's fixture into the SUT database, exactly as the [TEST DATA] block told
the model. Arm is taken from the label: labels contain 'dfunc' | 'dall' | 'dhuman'; any other label
(e.g. the G baseline) is scored with the unmodified v2 shims.

  func / all : SynthData functional rows replace the project's fixture (flaskr data.sql,
               fastapi-restful pristine players.db) or fill the empty tasks table (task-manager).
  human      : identical to the v2 shims (the project's own fixture is what v2 already loads).

usage: pipeline_e2.py <extract|kg|score|summarize> <label> [...]   (same as pipeline_v2)
"""
import os, sys, shutil, sqlite3
from pathlib import Path
W = Path("/home/claude/work/paperE/W")
sys.path.insert(0, str(W))
E2 = "/home/claude/work/paperH/exp/e2"
import extract_and_build as eb  # noqa: E402
import pipeline_v2 as p2         # noqa: E402

FIX_IMPORT = f'''
# ---- Paper H / E2 fixture provisioning (arm = {{arm!r}}) ----
_E2 = {E2!r}
if _E2 not in sys.path:
    sys.path.insert(0, _E2)
import fixture_loader as _fl
_E2_ARM = {{arm!r}}
'''

SUT3_E2 = eb.SUT3_EXTRA.replace(
    "    con.executescript(_SCHEMA_SQL)\n    con.executescript(_DATA_SQL)\n",
    "    con.executescript(_SCHEMA_SQL)\n    _fl.load_flaskr_rows(con, _E2_ARM)\n"
).replace(
    "        _init_db()\n        _get_db().executescript(_DATA_SQL)\n",
    "        _init_db()\n"
).replace(
    "from flaskr.db import get_db as _get_db, init_db as _init_db\n",
    "from flaskr.db import get_db as _get_db, init_db as _init_db\n"
    "import flaskr.db as _fdb\n"
    "_orig_init_db = _fdb.init_db\n"
    "def _init_db_provisioned():\n"
    "    # E2: whatever database a test initialises (init_db() / `flask init-db`) receives the fixture rows\n"
    "    _orig_init_db()\n"
    "    _fl.load_flaskr_rows(_fdb.get_db(), _E2_ARM)\n"
    "_fdb.init_db = _init_db_provisioned\n"
    "_init_db = _init_db_provisioned\n"
)
assert SUT3_E2.count("_init_db_provisioned") == 3
assert SUT3_E2 != eb.SUT3_EXTRA

SUT4_E2 = eb.SUT4_EXTRA.replace(
    "from app.database import Base as _Base, get_db as _get_db\n",
    "from app.database import Base as _Base, get_db as _get_db\n"
    "_orig_create_all = _Base.metadata.create_all\n"
    "def _create_all_provisioned(bind=None, **kw):\n"
    "    # E2: whatever engine a test creates the schema on (Base.metadata.create_all) receives the fixture rows\n"
    "    _orig_create_all(bind=bind, **kw)\n"
    "    if bind is not None:\n"
    "        try:\n"
    "            _fl.load_tasks(bind, _E2_ARM)\n"
    "        except Exception:\n"
    "            pass\n"
    "_Base.metadata.create_all = _create_all_provisioned\n"
)
assert SUT4_E2 != eb.SUT4_EXTRA


def cmd_extract_e2(label, runs_dirs):
    """pipeline_v2.cmd_extract with the condition/req-id split fixed for condition names that
    contain '_' (full_dfunc_R-FLASKR-001 -> cond full_dfunc, req R-FLASKR-001)."""
    import glob, json
    manifest, counts = [], {}
    for rd in runs_dirs:
        for f in sorted(glob.glob(str(Path(rd) / "*.json"))):
            name = os.path.basename(f)[:-5]
            if "_R-" not in name:
                continue
            cond, rest = name.split("_R-", 1)
            reqid = "R-" + rest
            d = json.load(open(f))
            sut = p2.SUT_OF_APP[d["req"]["target_app"]]
            hd = p2.harness_dir(label, cond, sut)
            if not (hd / "conftest.py").exists():
                eb.O = p2.suts_for(label)
                eb.build_harness_dir(hd, sut)
            tests = (d.get("doc") or {}).get("tests") or []
            for n, t in enumerate(tests):
                code = t.get("executable") or ""
                if not code.strip():
                    continue
                cleaned = eb.strip_toplevel_calls(eb.unfence(code))
                fn = f"test_gen_{reqid.replace('-', '_').lower()}_{n}.py"
                (hd / fn).write_text(cleaned)
                manifest.append({"label": label, "condition": cond, "sut": sut, "req_id": reqid,
                                 "test_index": n, "test_name": t.get("name"), "file": str(hd / fn)})
                counts[(cond, sut)] = counts.get((cond, sut), 0) + 1
    mf = p2.W / "harness" / label / "extraction_manifest.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(manifest, indent=1))
    for k in sorted(counts):
        print(label, k, counts[k])
    print("total units:", len(manifest))


_orig_kg_one = p2.kg_one


def kg_one_e2(label, cond, sut):
    """v2 kg_one preceded by a per-unit pre-screen: every unit is run alone in its own pytest process
    (same flags, and a 30 s wall cap on the whole process — the same limit v2 applies per test function, which pytest-timeout cannot apply to module-level code of script-style units) and is excluded — renamed *.py.excluded, with
    the reason recorded in kg_v2/<label>/prescreen_<cond>__<sut>.json — when the process exits with
    anything but 0 (tests passed) or 5 (no test functions collected, i.e. a script-style unit whose
    module-level assertions passed). Motivation (E2, 12 Sep 2026): a GPT-4o flaskr unit called
    `init_db_command()` at module level; the resulting SystemExit at collection aborted every pytest
    process of that SUT (INTERNALERROR, exit 3), the group-level filter could not attribute it and kept
    all 130 units, and the scorer then saw exit 3 on the baseline and on every mutant (0 kills). A unit
    that cannot pass on its own is not known-good under the v2 definition; the group run follows as before."""
    import json, subprocess
    hd = p2.harness_dir(label, cond, sut)
    excluded = {}
    kgd0 = p2.W / "kg_v2" / label
    kgd0.mkdir(parents=True, exist_ok=True)
    ckpt = kgd0 / f"prescreen_ok_{cond}__{sut}.json"      # units already known to pass alone (resumable pre-screen)
    ok_seen = set(json.loads(ckpt.read_text())) if ckpt.exists() else set()
    for f in sorted(hd.glob("test_gen_*.py")):
        if f.name in ok_seen:
            continue
        try:
            r = subprocess.run(p2.BASE_ARGS + [str(f)], cwd=str(p2.suts_for(label) / sut), capture_output=True,
                               text=True, timeout=30, env=p2.env_for(sut))
            rc = r.returncode
            reason = None if rc in (0, 5) else f"rc={rc}: " + (r.stdout.strip().splitlines() or ["?"])[-1][:160]
        except subprocess.TimeoutExpired:
            reason = "process timeout 30s"
        if reason:
            f.rename(str(f) + ".excluded")
            excluded[f.name] = reason
        else:
            ok_seen.add(f.name)
            ckpt.write_text(json.dumps(sorted(ok_seen)))
    # excluded units from earlier (interrupted) passes are already renamed; count them too
    for f in sorted(hd.glob("test_gen_*.py.excluded")):
        excluded.setdefault(f.name[:-len(".excluded")], "excluded in an earlier pre-screen pass")
    kgd = p2.W / "kg_v2" / label
    kgd.mkdir(parents=True, exist_ok=True)
    (kgd / f"prescreen_{cond}__{sut}.json").write_text(json.dumps(excluded, indent=1))
    print(f"  prescreen {label}/{cond}/{sut}: excluded {len(excluded)} unit(s)")
    st = _orig_kg_one(label, cond, sut)
    st["prescreen_excluded"] = len(excluded)
    st["raw_units"] += len(excluded)          # raw = every emitted unit, as in v2
    st["usable_fraction"] = round(st["kg_units"] / st["raw_units"], 4) if st["raw_units"] else 0.0
    return st


def arm_of(label):
    """Fixture arm from the label. E2c (17 Sep 2026): 'dstate' labels are scored with the SAME database
    state as 'dfunc' (the functional fixture); only the prompt block differs."""
    if "dstate" in label:
        return "func"
    for a in ("dfunc", "dall", "dhuman"):
        if a in label:
            return a[1:]
    return None


_orig_build_harness_dir = eb.build_harness_dir


def build_harness_dir_e2(d, sut_name, arm):
    """Same as eb.build_harness_dir, with the fixture shims for func/all arms."""
    if arm in (None, "human"):
        return _orig_build_harness_dir(d, sut_name)
    sut_path = str(eb.O / sut_name)
    d.mkdir(parents=True, exist_ok=True)
    extra = eb.EXTRAS[sut_name]
    if sut_name == "sut3_flaskr":
        extra = SUT3_E2
    elif sut_name == "sut4_fastapi_task_manager":
        extra = SUT4_E2
    head = eb.HEAD.format(sut=sut_path)
    fix = FIX_IMPORT.format(arm=arm) if sut_name != "sut1_httpbin" else ""
    (d / "conftest.py").write_text(head + fix + extra + eb.KG_BLOCK)
    for rel, content in eb.SHIMS[sut_name].items():
        fp = d / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content.format(sut=sut_path) if "{sut!r}" in content else content)
    if sut_name == "sut2_fastapi_restful":
        pr = d / "_pristine_players.db"
        if not pr.exists():
            shutil.copy(eb.O / sut_name / "players-sqlite3.db", pr)
            sys.path.insert(0, E2)
            import fixture_loader as fl
            fl.load_players(str(pr), arm)          # the "pristine" copy now holds the fixture rows
            n = sqlite3.connect(pr).execute("select count(*) from players").fetchone()[0]
            print(f"[e2] {sut_name}: pristine players.db replaced by fixture ({n} rows, arm {arm})")


if __name__ == "__main__":
    label = sys.argv[2]
    arm = arm_of(label)
    print(f"[e2] label {label} -> fixture arm {arm}")
    eb.build_harness_dir = lambda d, s: build_harness_dir_e2(d, s, arm)
    p2.kg_one = kg_one_e2
    cmd = sys.argv[1]
    if cmd == "extract":
        cmd_extract_e2(label, sys.argv[3:])
    elif cmd == "kg":
        p2.cmd_kg(label, sys.argv[3:] or ["full_dfunc", "full_dall", "full_dhuman", "full_dstate", "full"])
    elif cmd == "score":
        p2.cmd_score(label, int(sys.argv[3]) if len(sys.argv) > 3 else 10**9)
    elif cmd == "summarize":
        p2.cmd_summarize(label, sys.argv[3:] or ["full_dfunc", "full_dall", "full_dhuman", "full_dstate", "full"])
