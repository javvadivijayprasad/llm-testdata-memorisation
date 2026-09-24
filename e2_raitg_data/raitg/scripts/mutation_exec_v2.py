"""Executable mutation testing for Paper E reference apps.

Self-contained — generates AST mutations of each reference app and runs
the baseline test suite (baseline_tests.py) against each mutant. A mutant
is ``killed`` if the baseline test raises any exception; ``survived``
otherwise.

This script gives a real executable mutation score per reference app
that is comparable to PIT/mutmut numbers in the test-generation
literature (typically 60-75% for hand-authored suites on commodity
codebases).

Usage:
    python scripts/mutation_exec_v2.py
"""
from __future__ import annotations

import ast
import copy
import json
import time
from collections import defaultdict
from pathlib import Path

import sys
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from baseline_tests import run_app

APPS = ["banking-api", "fhir-lite", "hr-app", "logistics-app"]

# AST-level mutation operators
COMPARE_SWAPS = {
    ast.Lt: ast.Gt, ast.Gt: ast.Lt,
    ast.LtE: ast.GtE, ast.GtE: ast.LtE,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
BOOLOP_SWAPS = {ast.And: ast.Or, ast.Or: ast.And}


def generate_mutants(src: str) -> list[tuple[str, int, str]]:
    """Return list of (op_name, lineno, mutated_source)."""
    tree = ast.parse(src)
    mutants = []

    # Compare operator swaps
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                for old, new in COMPARE_SWAPS.items():
                    if isinstance(op, old):
                        t = copy.deepcopy(tree)
                        for c in ast.walk(t):
                            if (isinstance(c, ast.Compare)
                                    and getattr(c, "lineno", None) == node.lineno
                                    and getattr(c, "col_offset", None) == node.col_offset):
                                c.ops[i] = new()
                                break
                        try:
                            mutants.append((f"cmp:{old.__name__}->{new.__name__}",
                                             node.lineno, ast.unparse(t)))
                        except Exception:
                            pass

    # Boolean operator swaps
    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp):
            for old, new in BOOLOP_SWAPS.items():
                if isinstance(node.op, old):
                    t = copy.deepcopy(tree)
                    for c in ast.walk(t):
                        if (isinstance(c, ast.BoolOp)
                                and getattr(c, "lineno", None) == node.lineno):
                            c.op = new()
                            break
                    try:
                        mutants.append((f"bool:{old.__name__}->{new.__name__}",
                                         node.lineno, ast.unparse(t)))
                    except Exception:
                        pass

    # Constant bump on numeric literals (±1)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            for delta in (1, -1):
                if isinstance(node.value, bool):
                    continue
                t = copy.deepcopy(tree)
                for c in ast.walk(t):
                    if (isinstance(c, ast.Constant)
                            and getattr(c, "lineno", None) == node.lineno
                            and getattr(c, "col_offset", None) == node.col_offset
                            and not isinstance(c.value, bool)
                            and isinstance(c.value, (int, float))):
                        c.value = node.value + delta
                        break
                try:
                    mutants.append((f"const:{node.value}->{node.value + delta}",
                                     node.lineno, ast.unparse(t)))
                except Exception:
                    pass

    # Return-None
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            t = copy.deepcopy(tree)
            for c in ast.walk(t):
                if (isinstance(c, ast.Return)
                        and getattr(c, "lineno", None) == node.lineno):
                    c.value = None
                    break
            try:
                mutants.append((f"ret-none",
                                 node.lineno, ast.unparse(t)))
            except Exception:
                pass

    # Negate boolean constants True<->False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            t = copy.deepcopy(tree)
            for c in ast.walk(t):
                if (isinstance(c, ast.Constant)
                        and getattr(c, "lineno", None) == node.lineno
                        and getattr(c, "col_offset", None) == node.col_offset
                        and isinstance(c.value, bool)):
                    c.value = not node.value
                    break
            try:
                mutants.append((f"bool_const:{node.value}->{not node.value}",
                                 node.lineno, ast.unparse(t)))
            except Exception:
                pass

    return mutants


def score_app(app: str) -> dict:
    """Generate mutants, run baseline tests against each, compute score."""
    src = (ROOT / "repo" / app / "app.py").read_text()
    # Baseline must pass first
    if not run_app(app, src):
        return {"app": app, "error": "baseline failed on unmodified source"}
    print(f"  [{app}] baseline passes on unmodified source", flush=True)

    mutants = generate_mutants(src)
    print(f"  [{app}] generated {len(mutants)} mutants", flush=True)

    killed = 0
    survived = 0
    by_op = defaultdict(lambda: {"killed": 0, "survived": 0})
    for i, (op, lineno, mut_src) in enumerate(mutants):
        try:
            passes = run_app(app, mut_src)
        except Exception:
            passes = False
        if passes:
            survived += 1
            by_op[op.split(":")[0]]["survived"] += 1
        else:
            killed += 1
            by_op[op.split(":")[0]]["killed"] += 1
        if i % 50 == 0 and i:
            print(f"    {app}: {i}/{len(mutants)} killed={killed} survived={survived}",
                  flush=True)

    score = killed / max(1, len(mutants))
    return {
        "app": app,
        "mutants": len(mutants),
        "killed": killed,
        "survived": survived,
        "mutation_score": round(score, 4),
        "by_op": {k: dict(v) for k, v in by_op.items()},
    }


def main():
    t0 = time.time()
    print(f"=== Executable mutation testing (baseline suite) ===", flush=True)
    results = []
    for app in APPS:
        print(f"\n[{time.strftime('%H:%M:%S')}] Scoring {app} ...", flush=True)
        r = score_app(app)
        results.append(r)
        print(f"  {app}: mutation_score = {r['mutation_score']:.4f} "
              f"({r['killed']}/{r['mutants']} killed)", flush=True)

    # Aggregate
    total_mut = sum(r["mutants"] for r in results if "mutants" in r)
    total_killed = sum(r["killed"] for r in results if "killed" in r)
    aggregate = round(total_killed / max(1, total_mut), 4)
    out = {
        "aggregate_mutation_score": aggregate,
        "total_mutants": total_mut,
        "total_killed": total_killed,
        "per_app": results,
    }
    Path("results/mutation_exec_v2.json").write_text(json.dumps(out, indent=2))
    print(f"\n[{time.time()-t0:.1f}s] DONE")
    print(f"Aggregate: {total_killed}/{total_mut} = {aggregate*100:.2f}%")
    for r in results:
        if "mutation_score" in r:
            print(f"  {r['app']:14s} {r['killed']:>4}/{r['mutants']:<4} = {r['mutation_score']*100:.2f}%")


if __name__ == "__main__":
    main()
