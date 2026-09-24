"""Resumable executable-mutation scorer with per-mutant checkpointing.

Splits work into (condition, app) chunks. Within each chunk, tracks which
mutants have been scored (results appended to a JSONL file). Also caches
the known-good test filter to disk so repeated invocations don't redo it.

Layout under <output_file>.parent / <output_file>.stem + "_chunks":
    <cond>__<app>__known_good.json      # cached known-good tests
    <cond>__<app>__mutants.json         # cached mutant list (op, lineno, src)
    <cond>__<app>__scored.jsonl         # one line per scored mutant
    <cond>__<app>__done.json            # written when all mutants scored

Every 5 seconds, checks time budget; exits cleanly at boundary if exceeded.
Once all (cond, app) __done files exist, --finalize aggregates to
mutation_v3_raitg.json + CSVs.
"""
from __future__ import annotations

import argparse
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
from mutation_v3_raitg import (  # noqa: E402
    APPS, load_runs, extract_tests_for_app, run_test_in_isolation,
)


def chunks_dir_for(output_file: Path) -> Path:
    return output_file.parent / (output_file.stem + "_chunks")


def paths_for(cdir: Path, cond: str, app: str) -> dict[str, Path]:
    base = cdir / f"{cond}__{app}"
    return {
        "known_good": Path(str(base) + "__known_good.json"),
        "mutants": Path(str(base) + "__mutants.json"),
        "scored": Path(str(base) + "__scored.jsonl"),
        "done": Path(str(base) + "__done.json"),
    }


def build_known_good(cond: str, app: str, runs: list[dict],
                      time_left_fn) -> tuple[list[dict], int] | None:
    """Filter raw tests to known-good. Returns (list, raw_count) or None if
    time budget exhausted."""
    app_src = (ROOT / "repo" / app / "app.py").read_text()
    raw = extract_tests_for_app(runs, app)
    known_good = []
    for i, t in enumerate(raw):
        if i % 20 == 0 and time_left_fn() <= 0:
            print(f"    [time up during known-good filter at {i}/{len(raw)}]",
                  flush=True)
            return None
        if run_test_in_isolation(app_src, t["code"]):
            known_good.append(t)
    return known_good, len(raw)


def score_app_condition(cond: str, app: str, runs: list[dict],
                        cdir: Path, time_left_fn) -> bool:
    """Returns True if this (cond, app) is fully done after this call."""
    p = paths_for(cdir, cond, app)
    if p["done"].exists():
        return True

    # ---- Step 1: known-good tests (cached) ----
    if p["known_good"].exists():
        payload = json.loads(p["known_good"].read_text())
        known_good = payload["known_good"]
        raw_count = payload["raw_count"]
    else:
        if time_left_fn() <= 0:
            return False
        print(f"  [{cond}/{app}] building known-good filter...", flush=True)
        t0 = time.time()
        result = build_known_good(cond, app, runs, time_left_fn)
        if result is None:
            return False
        known_good, raw_count = result
        p["known_good"].write_text(json.dumps({
            "known_good": known_good,
            "raw_count": raw_count,
        }))
        print(f"  [{cond}/{app}] known-good: {len(known_good)}/{raw_count} "
              f"[{time.time()-t0:.1f}s]", flush=True)

    # ---- Step 2: mutants (cached) ----
    if p["mutants"].exists():
        mutants = json.loads(p["mutants"].read_text())
    else:
        app_src = (ROOT / "repo" / app / "app.py").read_text()
        muts_raw = generate_mutants(app_src)
        mutants = [{"idx": i, "op": op, "lineno": lineno, "src": src}
                   for i, (op, lineno, src) in enumerate(muts_raw)]
        p["mutants"].write_text(json.dumps(mutants))
        print(f"  [{cond}/{app}] generated {len(mutants)} mutants",
              flush=True)

    # ---- Step 3: score mutants (resumable via JSONL append) ----
    scored_indices: set[int] = set()
    if p["scored"].exists():
        with p["scored"].open() as f:
            for line in f:
                if line.strip():
                    scored_indices.add(json.loads(line)["idx"])

    remaining = [m for m in mutants if m["idx"] not in scored_indices]
    if remaining and time_left_fn() > 0:
        print(f"  [{cond}/{app}] scoring {len(remaining)} remaining mutants "
              f"(of {len(mutants)})...", flush=True)
        with p["scored"].open("a") as fout:
            for m in remaining:
                if time_left_fn() <= 0:
                    print(f"    [time up after {len(scored_indices)}/"
                          f"{len(mutants)} mutants]", flush=True)
                    break
                killed = False
                for t in known_good:
                    if not run_test_in_isolation(m["src"], t["code"]):
                        killed = True
                        break
                fout.write(json.dumps({
                    "idx": m["idx"],
                    "op": m["op"],
                    "killed": killed,
                }) + "\n")
                fout.flush()
                scored_indices.add(m["idx"])

    if len(scored_indices) < len(mutants):
        return False

    # ---- Step 4: aggregate into done.json ----
    scored: list[dict] = []
    with p["scored"].open() as f:
        for line in f:
            if line.strip():
                scored.append(json.loads(line))
    scored.sort(key=lambda x: x["idx"])

    killed = sum(1 for s in scored if s["killed"])
    by_op: dict[str, dict[str, int]] = defaultdict(
        lambda: {"killed": 0, "survived": 0})
    for s in scored:
        op_group = s["op"].split(":")[0]
        by_op[op_group]["killed" if s["killed"] else "survived"] += 1

    result = {
        "condition": cond,
        "app": app,
        "raw_tests": json.loads(p["known_good"].read_text())["raw_count"],
        "known_good_tests": len(known_good),
        "usable_fraction": round(len(known_good) / max(1, json.loads(
            p["known_good"].read_text())["raw_count"]), 4),
        "mutants": len(scored),
        "killed": killed,
        "survived": len(scored) - killed,
        "mutation_score": round(killed / max(1, len(scored)), 4),
        "by_op": {k: dict(v) for k, v in by_op.items()},
    }
    p["done"].write_text(json.dumps(result, indent=2))
    print(f"  [{cond}/{app}] DONE: {killed}/{len(scored)} = "
          f"{100*result['mutation_score']:.2f}%", flush=True)
    return True


def run_chunks(runs_dir: Path, output_file: Path, conditions: list[str],
               apps: list[str], time_budget: float,
               recent_only_hours: float | None) -> int:
    cdir = chunks_dir_for(output_file)
    cdir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()
    def time_left():
        return time_budget - (time.time() - t_start)

    runs_cache: dict[str, list[dict]] = {}
    all_done = True
    processed = 0

    for cond in conditions:
        for app in apps:
            if time_left() <= 0:
                all_done = False
                break
            p = paths_for(cdir, cond, app)
            if p["done"].exists():
                continue

            if cond not in runs_cache:
                if time_left() <= 0:
                    all_done = False
                    break
                t_load = time.time()
                runs_cache[cond] = load_runs(cond, recent_only_hours,
                                              runs_dir=runs_dir)
                print(f"[{time.strftime('%H:%M:%S')}] loaded "
                      f"{len(runs_cache[cond])} runs for {cond} in "
                      f"{time.time()-t_load:.1f}s", flush=True)

            done = score_app_condition(cond, app, runs_cache[cond], cdir,
                                        time_left)
            if not done:
                all_done = False
            else:
                processed += 1
        if not all_done:
            break

    elapsed = time.time() - t_start
    if all_done:
        # Check whether ALL (cond, app) are done, not just those we visited
        totally_done = all(
            paths_for(cdir, c, a)["done"].exists()
            for c in conditions for a in apps
        )
        if totally_done:
            print(f"[resumable] ALL DONE in {elapsed:.1f}s "
                  f"(processed {processed} chunks this call)", flush=True)
        else:
            print(f"[resumable] partial: {processed} chunks this call, "
                  f"{elapsed:.1f}s", flush=True)
    else:
        print(f"[resumable] time budget exhausted; processed {processed} "
              f"chunks this call in {elapsed:.1f}s", flush=True)
    return 0


def finalize(output_file: Path, csv_suffix: str, conditions: list[str],
              apps: list[str]) -> int:
    cdir = chunks_dir_for(output_file)
    all_results: list[dict] = []
    missing: list[str] = []
    for cond in conditions:
        for app in apps:
            p = paths_for(cdir, cond, app)["done"]
            if not p.exists():
                missing.append(f"{cond}/{app}")
                continue
            all_results.append(json.loads(p.read_text()))

    if missing:
        print(f"[finalize] MISSING chunks: {missing}", flush=True)
        return 2

    out_dir = ROOT / "tables"
    out_dir.mkdir(exist_ok=True)

    with (out_dir / f"executable_mutation_per_condition_by_app{csv_suffix}.csv").open(
            "w", newline="") as f:
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

    with (out_dir / f"executable_mutation_per_condition{csv_suffix}.csv").open(
            "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "raw_tests", "known_good_tests",
                    "total_mutants", "total_killed",
                    "aggregate_mutation_score"])
        for cond, agg in agg_by_cond.items():
            score = round(agg["killed"] / max(1, agg["mutants"]), 4)
            w.writerow([cond, agg["raw"], agg["good"], agg["mutants"],
                        agg["killed"], score])

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps({
        "per_app_per_condition": all_results,
        "aggregate_per_condition": {c: {**a, "score": round(a["killed"]/max(1,a["mutants"]),4)}
                                     for c, a in agg_by_cond.items()},
        "runtime_seconds": 0.0,
    }, indent=2))

    print(f"[finalize] wrote {output_file}", flush=True)
    print(f"=== Summary (aggregate per condition) ===", flush=True)
    for cond, agg in agg_by_cond.items():
        score = agg["killed"] / max(1, agg["mutants"])
        print(f"  {cond:15s}: {agg['killed']:>4}/{agg['mutants']:>4} = "
              f"{100*score:5.2f}%", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=None)
    ap.add_argument("--output-file", type=Path, required=True)
    ap.add_argument("--output-csv-suffix", type=str, default="")
    ap.add_argument("--condition", action="append", default=None)
    ap.add_argument("--apps", default=",".join(APPS))
    ap.add_argument("--recent-only-hours", type=float, default=None)
    ap.add_argument("--time-budget", type=float, default=30.0)
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()

    conditions = args.condition or ["unverified", "ablation", "full"]
    apps = args.apps.split(",")

    if args.finalize:
        return finalize(args.output_file, args.output_csv_suffix,
                        conditions, apps)

    if args.runs_dir is None:
        print("--runs-dir is required (unless --finalize)", flush=True)
        return 2

    return run_chunks(args.runs_dir, args.output_file, conditions, apps,
                      args.time_budget, args.recent_only_hours)


if __name__ == "__main__":
    raise SystemExit(main())
