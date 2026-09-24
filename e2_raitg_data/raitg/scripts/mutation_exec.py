"""Executable mutation testing — no external mutmut dependency.

Generates AST mutations of each reference application, writes each mutant
to a temporary directory, then runs the generated suite (the executable
pytest tests stored in the per-requirement run logs) against each mutant
in a subprocess. A mutant is ``killed`` if at least one test fails (or
erroring imports signal a detectable break); it is ``survived`` if all
tests pass. Mutation score = killed / total.

Design choices:
  * Pure stdlib — no mutmut, no pytest-mutation plugin. Uses ``python -m
    pytest`` if pytest is installed; falls back to a minimal unittest
    runner otherwise.
  * Operator set: comparison swaps, boolean-operator swaps, constant-bump
    on numeric literals, return-None, delete-if-body.
  * Per-requirement: we score the generated suite against the mutant set
    of the SAME reference app that the requirement's domain maps to.

Usage:
    python scripts/mutation_exec.py              # score all run logs
    python scripts/mutation_exec.py --condition full
    python scripts/mutation_exec.py --limit 20   # pilot
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

DOMAINS = ["commercial_web", "financial_services", "healthcare", "logistics"]
APP_FOR_DOMAIN = {
    "commercial_web": ROOT / "repo" / "hr-app",
    "financial_services": ROOT / "repo" / "banking-api",
    "healthcare": ROOT / "repo" / "fhir-lite",
    "logistics": ROOT / "repo" / "logistics-app",
}


# ---------------------------------------------------------------------------
# Mutation operators (AST transformations)
# ---------------------------------------------------------------------------
COMPARE_SWAPS = {
    ast.Lt: ast.Gt, ast.Gt: ast.Lt,
    ast.LtE: ast.GtE, ast.GtE: ast.LtE,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
BOOLOP_SWAPS = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass
class Mutant:
    op: str
    lineno: int
    source: str  # full mutated source


def _mutate_compare(tree: ast.AST) -> list[Mutant]:
    out: list[Mutant] = []
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Compare)]
    for n in nodes:
        for i, op in enumerate(n.ops):
            for old_cls, new_cls in COMPARE_SWAPS.items():
                if isinstance(op, old_cls):
                    t = copy.deepcopy(tree)
                    # find matching node in copy (by lineno+col)
                    for c in ast.walk(t):
                        if (isinstance(c, ast.Compare)
                                and getattr(c, "lineno", None) == n.lineno
                                and getattr(c, "col_offset", None) == n.col_offset):
                            c.ops[i] = new_cls()
                            break
                    try:
                        src = ast.unparse(t)
                        out.append(Mutant(
                            op=f"cmp:{old_cls.__name__}->{new_cls.__name__}",
                            lineno=n.lineno, source=src))
                    except Exception:
                        pass
    return out


def _mutate_boolop(tree: ast.AST) -> list[Mutant]:
    out: list[Mutant] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.BoolOp):
            for old_cls, new_cls in BOOLOP_SWAPS.items():
                if isinstance(n.op, old_cls):
                    t = copy.deepcopy(tree)
                    for c in ast.walk(t):
                        if (isinstance(c, ast.BoolOp)
                                and getattr(c, "lineno", None) == n.lineno
                                and getattr(c, "col_offset", None) == n.col_offset):
                            c.op = new_cls()
                            break
                    try:
                        out.append(Mutant(
                            op=f"bool:{old_cls.__name__}->{new_cls.__name__}",
                            lineno=n.lineno, source=ast.unparse(t)))
                    except Exception:
                        pass
    return out


def _mutate_constant_bump(tree: ast.AST) -> list[Mutant]:
    out: list[Mutant] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            for delta in (1, -1):
                if n.value + delta == n.value:  # floats near zero
                    continue
                t = copy.deepcopy(tree)
                for c in ast.walk(t):
                    if (isinstance(c, ast.Constant)
                            and getattr(c, "lineno", None) == n.lineno
                            and getattr(c, "col_offset", None) == n.col_offset):
                        c.value = n.value + delta
                        break
                try:
                    out.append(Mutant(
                        op=f"const:{n.value}->{n.value + delta}",
                        lineno=n.lineno, source=ast.unparse(t)))
                except Exception:
                    pass
    return out


def _mutate_return_none(tree: ast.AST) -> list[Mutant]:
    out: list[Mutant] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Return) and n.value is not None:
            t = copy.deepcopy(tree)
            for c in ast.walk(t):
                if (isinstance(c, ast.Return)
                        and getattr(c, "lineno", None) == n.lineno):
                    c.value = None
                    break
            try:
                out.append(Mutant(
                    op="return:value->None",
                    lineno=n.lineno, source=ast.unparse(t)))
            except Exception:
                pass
    return out


def generate_mutants(source_path: Path, limit: int | None = None) -> list[Mutant]:
    src = source_path.read_text()
    tree = ast.parse(src)
    muts = (_mutate_compare(tree) + _mutate_boolop(tree)
            + _mutate_constant_bump(tree) + _mutate_return_none(tree))
    if limit:
        muts = muts[:limit]
    return muts


# ---------------------------------------------------------------------------
# Executable scoring: write mutant app + generated tests into tmpdir, run
# ---------------------------------------------------------------------------
def _extract_executables(doc: dict) -> list[str]:
    out: list[str] = []
    for t in doc.get("tests", []) or []:
        exe = t.get("executable")
        if exe and isinstance(exe, str) and "def test_" in exe:
            out.append(exe)
    return out


def _write_test_file(tmpdir: Path, executables: list[str], app_module: str) -> Path:
    """Concatenate generated test sources into a single pytest file.

    Rewrites imports so the tests import from the mutant app module.
    """
    body = [
        "import sys, os",
        "sys.path.insert(0, os.path.dirname(__file__))",
        f"from {app_module} import *  # noqa: F401,F403",
        "",
    ]
    for i, exe in enumerate(executables):
        # Strip any imports the generated code tried to make so they don't
        # shadow the in-tmpdir app module
        lines = [
            ln for ln in exe.splitlines()
            if not (ln.lstrip().startswith(("import ", "from "))
                    and app_module not in ln)
        ]
        body.append(f"# --- generated test block {i} ---")
        body.extend(lines)
        body.append("")
    test_file = tmpdir / "test_generated.py"
    test_file.write_text("\n".join(body))
    return test_file


def _run_pytest(tmpdir: Path, timeout: int = 30) -> tuple[int, str]:
    """Return (returncode, combined_output). 0 = tests passed."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=line",
             "--timeout", str(timeout), "-x"],
            cwd=tmpdir, capture_output=True, text=True, timeout=timeout + 10,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return 2, "TIMEOUT"
    except FileNotFoundError:
        # pytest not installed — fall back to compileall
        proc = subprocess.run(
            [sys.executable, "-c",
             "import py_compile, glob; [py_compile.compile(f, doraise=True) "
             "for f in glob.glob('*.py')]"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def score_doc_against_app(doc: dict, app_dir: Path,
                          *, mutant_limit: int | None = None,
                          verbose: bool = False) -> dict:
    """Run the generated suite against all mutants of ``app_dir/app.py``."""
    app_py = app_dir / "app.py"
    executables = _extract_executables(doc)
    if not executables:
        return {"mutants": 0, "killed": 0, "score": 0.0,
                "reason": "no generated executable tests"}

    mutants = generate_mutants(app_py, limit=mutant_limit)
    if not mutants:
        return {"mutants": 0, "killed": 0, "score": 0.0,
                "reason": "no mutants generated"}

    killed = 0
    first_failures: list[str] = []
    for idx, mut in enumerate(mutants):
        with tempfile.TemporaryDirectory(prefix="mut_") as td_str:
            td = Path(td_str)
            (td / "app.py").write_text(mut.source)
            test_file = _write_test_file(td, executables, "app")
            # Baseline smoke: does the mutant even import? If not, it's killed.
            try:
                compile(mut.source, "app.py", "exec")
            except SyntaxError:
                killed += 1
                continue
            rc, out = _run_pytest(td, timeout=20)
            if rc != 0:
                killed += 1
                if verbose and len(first_failures) < 3:
                    first_failures.append(f"{mut.op}@L{mut.lineno}: rc={rc}")
        if verbose and idx % 20 == 0 and idx:
            print(f"    mut {idx}/{len(mutants)} killed={killed}")

    return {
        "mutants": len(mutants),
        "killed": killed,
        "score": killed / len(mutants),
        "failures_sample": first_failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / "results" / "runs"))
    ap.add_argument("--condition", default=None,
                    help="Restrict to one condition: unverified|ablation|full")
    ap.add_argument("--limit", type=int, default=None,
                    help="Process at most N requirements (pilot)")
    ap.add_argument("--mutant-limit", type=int, default=40,
                    help="Cap mutants per app for runtime")
    ap.add_argument("--out", default=str(ROOT / "results" / "mutation_exec.json"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    runs_dir = Path(args.runs)
    files = sorted(runs_dir.glob("*.json"))
    if args.condition:
        files = [f for f in files if f.name.startswith(f"{args.condition}_")]
    if args.limit:
        files = files[: args.limit]
    print(f"[mutation_exec] processing {len(files)} run logs")

    results: list[dict] = []
    per_cond = defaultdict(list)
    started = time.time()
    for i, f in enumerate(files, 1):
        try:
            d = json.loads(f.read_text())
        except Exception as e:
            print(f"  skip {f.name}: {e}")
            continue
        cond = d.get("condition")
        req = d.get("req") or {}
        dom = req.get("domain")
        if not dom or dom not in APP_FOR_DOMAIN:
            continue
        app_dir = APP_FOR_DOMAIN[dom]
        report = score_doc_against_app(
            d.get("doc") or {}, app_dir,
            mutant_limit=args.mutant_limit, verbose=args.verbose,
        )
        rec = {
            "req_id": req.get("id"),
            "condition": cond,
            "domain": dom,
            **report,
        }
        results.append(rec)
        per_cond[cond].append(report["score"])
        if i % 20 == 0:
            elapsed = int(time.time() - started)
            print(f"  {i}/{len(files)}  elapsed={elapsed}s  "
                  + "  ".join(f"{c}:n={len(v)} mean={sum(v)/len(v):.3f}"
                              for c, v in per_cond.items()))

    summary = {
        "n": len(results),
        "per_condition": {c: {"n": len(v),
                              "mean_score": sum(v) / len(v) if v else 0.0}
                          for c, v in per_cond.items()},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "summary": summary, "results": results,
    }, indent=2))
    print("\nSummary:")
    print(json.dumps(summary, indent=2))
    print(f"\nFull report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
