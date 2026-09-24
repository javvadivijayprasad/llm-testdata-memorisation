"""Score RAITG-generated test suites using executable mutation.

FIXED v2 (2026-08-04):
  - Runs each generated test INDIVIDUALLY against the correct app source first
  - Filters to "known good" tests (those that actually pass on correct code)
  - Only "known good" tests are scored against mutants
  - Reports both raw-tests-count and known-good-count for transparency
  - Filters run logs by --pilot-only flag (uses only fresh pilot output)

Usage:
    python scripts/mutation_v3_raitg.py
    python scripts/mutation_v3_raitg.py --recent-only  # only files modified in last N hours
    python scripts/mutation_v3_raitg.py --condition full
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from mutation_v3 import generate_mutants  # noqa: E402

APPS = ["banking-api", "fhir-lite", "hr-app", "logistics-app"]

DOMAIN_TO_APP = {
    "financial-services": "banking-api",
    "healthcare": "fhir-lite",
    "commercial-web": "hr-app",
    "logistics": "logistics-app",
    "financial": "banking-api",
    "health": "fhir-lite",
    "hr": "hr-app",
    "commerce": "hr-app",
}


def sanitize_executable(code: str) -> str:
    """Strip placeholders, unwrap def test_xxx() wrappers, return runnable module-level code."""
    if not code or not isinstance(code, str):
        return ""
    if any(marker in code for marker in ("<helper_fn>", "<fixture>", "<TODO>",
                                          "<mock>", "<placeholder>", "<MOCK>")):
        return ""

    stripped = code.strip()

    if not stripped.startswith("def "):
        return stripped

    try:
        tree = ast.parse(stripped)
        if (len(tree.body) == 1
                and isinstance(tree.body[0], ast.FunctionDef)):
            body_nodes = tree.body[0].body
            module_body = ast.Module(body=body_nodes, type_ignores=[])
            return ast.unparse(module_body)
    except SyntaxError:
        return ""
    return stripped


TEST_TIMEOUT_SECONDS = 2


def run_test_in_isolation(app_src: str, test_code: str) -> bool:
    """Execute ONE test against the given app source (correct or mutated).

    Creates a real `app` module in sys.modules BEFORE exec'ing the source
    (so @dataclass and other decorators can look up cls.__module__).
    Returns True if test passed, False if any exception raised.

    A per-test SIGALRM watchdog aborts tests that run longer than
    TEST_TIMEOUT_SECONDS — such a test is treated as a failure (mutant
    killed / known-good filter rejects it). Only active on POSIX.
    """
    import types
    try:
        compile(app_src, "app.py", "exec")
    except SyntaxError:
        return False

    # Create module and register it FIRST (before exec, so @dataclass works)
    app_module = types.ModuleType("app")
    app_module.__file__ = "app.py"
    sys.modules["app"] = app_module

    # POSIX-only per-test timeout via SIGALRM. Distinct exception class so
    # the outer BaseException handler can distinguish it (still counted as
    # test failure, but recorded for diagnostics).
    class _TestTimeout(BaseException):
        pass

    have_alarm = hasattr(__import__("signal"), "SIGALRM")
    if have_alarm:
        import signal
        def _handler(signum, frame):
            raise _TestTimeout()
        old_handler = signal.signal(signal.SIGALRM, _handler)
    try:
        try:
            exec(compile(app_src, "app.py", "exec"), app_module.__dict__)
        except Exception:
            return False

        try:
            namespace: dict = {
                "__name__": "__main__",
                "__file__": str(ROOT / "scripts" / "_raitg_test_runner.py"),
            }
            if have_alarm:
                signal.setitimer(signal.ITIMER_REAL, TEST_TIMEOUT_SECONDS)
            exec(test_code, namespace)
            return True
        except BaseException:
            # Catch BaseException to include pytest.Failed, KeyboardInterrupt,
            # _TestTimeout, etc. — any exception means the test raised =
            # mutant killed / known-good rejected.
            return False
        finally:
            if have_alarm:
                signal.setitimer(signal.ITIMER_REAL, 0)
    finally:
        if have_alarm:
            signal.signal(signal.SIGALRM, old_handler)
        # Clean up so next mutant's app_src can be freshly registered
        sys.modules.pop("app", None)


def load_runs(condition: str, recent_only_hours: float = None,
              runs_dir: Path = None) -> list[dict]:
    """Load run logs for a given condition, optionally filtered by recency."""
    runs = []
    cutoff = time.time() - recent_only_hours * 3600 if recent_only_hours else 0
    if runs_dir is None:
        runs_dir = ROOT / "results" / "runs"
    for f in runs_dir.glob(f"{condition}_*.json"):
        if recent_only_hours and f.stat().st_mtime < cutoff:
            continue
        try:
            d = json.loads(f.read_text())
            runs.append(d)
        except Exception as e:
            print(f"  [WARN] skipping {f.name}: {e}", flush=True)
    return runs


def extract_tests_for_app(runs: list[dict], app: str) -> list[dict]:
    """Return list of {req_id, test_name, code} for all tests targeting `app`."""
    out = []
    for run in runs:
        req = run.get("req", {})
        target = req.get("target_app") or DOMAIN_TO_APP.get(req.get("domain", ""))
        if target != app:
            continue
        doc = run.get("doc", {})
        for t in doc.get("tests", []) or []:
            code = sanitize_executable(t.get("executable", ""))
            if code:
                out.append({
                    "req_id": run.get("req_id"),
                    "test_name": t.get("name", ""),
                    "kind": t.get("kind", ""),
                    "code": code,
                })
    return out


def score_condition_for_app(condition: str, app: str, runs: list[dict],
                              mutant_cache: dict) -> dict:
    app_src = (ROOT / "repo" / app / "app.py").read_text()
    raw_tests = extract_tests_for_app(runs, app)
    total_raw = len(raw_tests)

    # STEP 1: Filter to "known good" tests — those that pass on correct source
    known_good = []
    for t in raw_tests:
        if run_test_in_isolation(app_src, t["code"]):
            known_good.append(t)
    total_good = len(known_good)

    # STEP 2: Generate mutants (cached per app)
    if app not in mutant_cache:
        mutant_cache[app] = generate_mutants(app_src)
    mutants = mutant_cache[app]

    # STEP 3: For each mutant, check if ANY known-good test FAILS
    killed = 0
    by_op = defaultdict(lambda: {"killed": 0, "survived": 0})
    for op, lineno, mut_src in mutants:
        mutant_killed = False
        for t in known_good:
            passed_on_mutant = run_test_in_isolation(mut_src, t["code"])
            if not passed_on_mutant:
                mutant_killed = True
                break
        op_group = op.split(":")[0]
        if mutant_killed:
            killed += 1
            by_op[op_group]["killed"] += 1
        else:
            by_op[op_group]["survived"] += 1

    return {
        "condition": condition,
        "app": app,
        "raw_tests": total_raw,
        "known_good_tests": total_good,
        "usable_fraction": round(total_good / max(1, total_raw), 4),
        "mutants": len(mutants),
        "killed": killed,
        "survived": len(mutants) - killed,
        "mutation_score": round(killed / max(1, len(mutants)), 4),
        "by_op": {k: dict(v) for k, v in by_op.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", action="append", default=None)
    ap.add_argument("--apps", default=",".join(APPS))
    ap.add_argument("--recent-only-hours", type=float, default=None,
                    help="Only score runs modified within N hours ago (default: all)")
    ap.add_argument("--runs-dir", type=Path, default=None,
                    help="Directory containing run log JSONs (default: ROOT/results/runs)")
    ap.add_argument("--output-file", type=Path, default=None,
                    help="Output JSON file (default: ROOT/results/mutation_v3_raitg.json)")
    ap.add_argument("--output-csv-suffix", type=str, default="",
                    help="Suffix appended to per-condition CSV filenames in tables/ (default: empty)")
    args = ap.parse_args()

    runs_dir = args.runs_dir if args.runs_dir is not None else (ROOT / "results" / "runs")
    output_file = args.output_file if args.output_file is not None else (ROOT / "results" / "mutation_v3_raitg.json")
    csv_suffix = args.output_csv_suffix or ""

    conditions = args.condition or ["unverified", "ablation", "full"]
    apps = args.apps.split(",")

    t0 = time.time()
    print(f"=== mutation_v3_raitg v2 (per-test isolation, baseline filtering) ===", flush=True)
    print(f"conditions: {conditions}, apps: {apps}", flush=True)
    if args.recent_only_hours:
        print(f"filtering to runs modified within {args.recent_only_hours} hours", flush=True)

    mutant_cache: dict = {}
    all_results: list[dict] = []

    print(f"runs_dir: {runs_dir}", flush=True)
    print(f"output_file: {output_file}", flush=True)
    if csv_suffix:
        print(f"csv_suffix: {csv_suffix}", flush=True)

    for cond in conditions:
        print(f"\n[{time.strftime('%H:%M:%S')}] Loading runs for condition={cond}", flush=True)
        runs = load_runs(cond, args.recent_only_hours, runs_dir=runs_dir)
        print(f"  loaded {len(runs)} run logs", flush=True)
        if not runs:
            continue
        for app in apps:
            print(f"\n[{time.strftime('%H:%M:%S')}] Scoring {app} / {cond}", flush=True)
            r = score_condition_for_app(cond, app, runs, mutant_cache)
            all_results.append(r)
            print(f"  raw={r['raw_tests']}  known-good={r['known_good_tests']} "
                  f"({100*r['usable_fraction']:.0f}%)  "
                  f"score={100*r['mutation_score']:.2f}%  "
                  f"({r['killed']}/{r['mutants']} killed)",
                  flush=True)

    # ------------------- Output -------------------
    out_dir = ROOT / "tables"
    out_dir.mkdir(exist_ok=True)

    with (out_dir / f"executable_mutation_per_condition_by_app{csv_suffix}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "app", "raw_tests", "known_good_tests",
                    "usable_fraction", "mutants", "killed", "survived",
                    "mutation_score"])
        for r in all_results:
            w.writerow([r["condition"], r["app"], r["raw_tests"],
                        r["known_good_tests"], r["usable_fraction"],
                        r["mutants"], r["killed"], r["survived"],
                        r["mutation_score"]])

    agg_by_cond: dict[str, dict] = defaultdict(
        lambda: {"raw": 0, "good": 0, "mutants": 0, "killed": 0})
    for r in all_results:
        agg_by_cond[r["condition"]]["raw"] += r["raw_tests"]
        agg_by_cond[r["condition"]]["good"] += r["known_good_tests"]
        agg_by_cond[r["condition"]]["mutants"] += r["mutants"]
        agg_by_cond[r["condition"]]["killed"] += r["killed"]

    with (out_dir / f"executable_mutation_per_condition{csv_suffix}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "raw_tests", "known_good_tests",
                    "total_mutants", "total_killed", "aggregate_mutation_score"])
        for cond, agg in agg_by_cond.items():
            score = round(agg["killed"] / max(1, agg["mutants"]), 4)
            w.writerow([cond, agg["raw"], agg["good"], agg["mutants"],
                        agg["killed"], score])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps({
        "per_app_per_condition": all_results,
        "aggregate_per_condition": {c: {**a, "score": round(a["killed"]/max(1,a["mutants"]),4)}
                                     for c, a in agg_by_cond.items()},
        "runtime_seconds": round(time.time() - t0, 1),
    }, indent=2))

    print(f"\n=== Summary (aggregate per condition) ===", flush=True)
    print(f"  Manual baseline (from mutation_v3.py):  161/194 = 82.99%", flush=True)
    for cond, agg in agg_by_cond.items():
        score = agg["killed"] / max(1, agg["mutants"])
        usable = 100 * agg["good"] / max(1, agg["raw"])
        print(f"  {cond:15s}: {agg['killed']:>4}/{agg['mutants']:>4} = {100*score:5.2f}% "
              f"(usable tests: {agg['good']}/{agg['raw']} = {usable:.0f}%)",
              flush=True)

    print(f"\n[{time.time()-t0:.1f}s] DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
