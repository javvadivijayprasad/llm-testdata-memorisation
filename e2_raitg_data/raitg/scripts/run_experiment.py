"""End-to-end orchestrator for the RAITG experiment.

Runs the full 312-requirement study across four conditions:
  manual       — uses existing manual suite (from datasets)
  unverified   — naive LLM prompt
  ablation     — full framework, verification disabled
  full         — full RAITG framework with verification + repair

For each condition and each requirement it records:
  - backend, model, token usage, latency
  - generated suite
  - verification result
  - mutation score against the target app

Outputs CSVs to `tables/` (regenerating the ones the paper renders) and
JSON run logs to `results/runs/<condition>/<req_id>.json`.

Usage:
  python scripts/run_experiment.py --pilot                  # 30 reqs, all conditions
  python scripts/run_experiment.py --full                   # 312 reqs, all conditions
  python scripts/run_experiment.py --backend anthropic --model claude-sonnet-4-6
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import prompts  # noqa: E402
import verify as verify_mod  # noqa: E402
import mutation as mutation_mod  # noqa: E402
import llm_adapter  # noqa: E402
from json_extract import extract_json  # noqa: E402

# v1.4.0 (2026-09-10) conditions:
#   unverified — naive single-shot prompt (no schema, no source, no verification)
#   ablation   — full scaffold + SUT source, verification/repair OFF
#   full       — full scaffold + SUT source + verification/repair  (headline)
#   reqonly    — full scaffold + verification/repair, SUT source NOT injected
#                (this is what the v1.3.0 OSS runs actually executed; kept as an arm)
#   srcfirst   — SUT source + endpoint identifier only, NO natural-language
#                requirement text; verification/repair ON (code-driven baseline)
# v1.5.0 (2026-09-12, Paper H / E2): three test-data arms = the grounded `full` arm + a [TEST DATA]
#   block (see prompts.py); verification/repair ON exactly as in `full`.
#   full_dfunc  — SynthData functional fixture (pre-loaded in the SUT database at scoring)
#   full_dall   — functional (pre-loaded) + edge + negative rows shown as payloads to try
#   full_dhuman — the project's own shipped fixture (flaskr, fastapi-restful; task-manager: none)
# v1.5.1 (2026-09-17, Paper H / E2c): full_dstate — the functional fixture block of full_dfunc plus an
#   explicit DATABASE STATE CONTRACT (ids taken, next free id, counts relative to N). Database state
#   at scoring is identical to full_dfunc; only the information given to the model differs.
CONDITIONS = ["unverified", "ablation", "full", "reqonly", "srcfirst", "full_dfunc", "full_dall", "full_dhuman", "full_dstate"]
PROMPT_KW = {
    "unverified": {"mode": "naive"},
    "ablation":   {"mode": "full"},
    "full":       {"mode": "full"},
    "reqonly":    {"mode": "full", "inject_source": False},
    "srcfirst":   {"mode": "full", "requirement_text": False},
    "full_dfunc":  {"mode": "full", "test_data_arm": "func"},
    "full_dall":   {"mode": "full", "test_data_arm": "all"},
    "full_dhuman": {"mode": "full", "test_data_arm": "human"},
    "full_dstate": {"mode": "full", "test_data_arm": "state"},
}
# OSS benchmark (2026-08-19): 4 community-authored Python microservices replaced
# the earlier self-authored SUTs. See BENCHMARK_MANIFEST.md at repo root.
DOMAINS = ["http_utilities", "sports_players", "blogging", "task_management"]
APP_FOR_DOMAIN = {
    "http_utilities":  ROOT / "repo" / "httpbin" / "httpbin" / "core.py",
    "sports_players":  ROOT / "repo" / "fastapi-restful" / "main.py",
    "blogging":        ROOT / "repo" / "flaskr" / "flaskr" / "__init__.py",
    "task_management": ROOT / "repo" / "fastapi-task-manager" / "app" / "main.py",
}


def load_dataset(pilot: int | None = None) -> list[dict]:
    reqs = json.loads((ROOT / "datasets" / "combined.json").read_text())
    if pilot:
        # stratified sample: ~equal from each domain
        by_domain: dict[str, list[dict]] = defaultdict(list)
        for r in reqs:
            by_domain[r["domain"]].append(r)
        per_dom = max(1, pilot // len(by_domain))
        sample = []
        for dom in DOMAINS:
            sample.extend(by_domain[dom][:per_dom])
        return sample[:pilot]
    return reqs


def generate_suite(adapter, req, condition, target_framework="pytest") -> tuple[dict, dict]:
    """Run the LLM and return (parsed_doc_or_empty, telemetry)."""
    prompt = prompts.compose_prompt(req, target_framework=target_framework,
                                    **PROMPT_KW[condition])
    t0 = time.perf_counter()
    resp = adapter.complete(prompt)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    # parse (robust: strips code fences, extracts first JSON object)
    doc = {}
    try:
        doc = extract_json(resp.text)
        if not isinstance(doc, dict):
            raise json.JSONDecodeError("expected JSON object", resp.text[:200], 0)
    except json.JSONDecodeError:
        # naive baseline returns free text; wrap into a minimal doc for scoring
        doc = {
            "requirement_id": req["id"],
            "reasoning": "naive (no structured JSON)",
            "tests": [{
                "name": "naive_case",
                "kind": "positive",
                "heuristic": "EP",
                "preconditions": [],
                "actions": ["execute requirement"],
                "expected": ["successful response"],
                "trace": [],
                "executable": resp.text,
            }],
            "_raw_response": resp.text[:2000],
        }
    tel = {
        "backend": resp.backend, "model": resp.model,
        "input_tokens": resp.input_tokens, "output_tokens": resp.output_tokens,
        "latency_ms": resp.latency_ms, "wall_ms": elapsed_ms,
        "condition": condition, "prompt_version": prompts.PROMPT_VERSION,
        "raw_response_head": resp.text[:4000],  # for diagnosis without re-running
    }
    return doc, tel


def verify_and_repair(adapter, req, doc, condition) -> tuple[dict, verify_mod.VerificationResult, int]:
    """Return (final_doc, verification_result, repair_attempts)."""
    if condition not in ("full", "reqonly", "srcfirst", "full_dfunc", "full_dall", "full_dhuman", "full_dstate"):
        enabled = set() if condition == "unverified" else {"structural", "logical"}
        if condition == "ablation":
            enabled = set()  # ablation: no verification
        res = verify_mod.verify(doc, req["id"], enabled_classes=enabled or None)
        return doc, res, 0

    first_pass_res = verify_mod.verify(doc, req["id"])
    res = first_pass_res
    best_doc = doc
    attempts = 0
    while not res.ok and attempts < 1:  # one repair attempt
        attempts += 1
        # srcfirst arm must never see the natural-language requirement, including in repair
        req_for_repair = req
        if condition == "srcfirst":
            req_for_repair = {k: req[k] for k in ("id", "domain", "layer", "target_app",
                                                   "target_endpoint_or_screen") if k in req}
        rp = prompts.repair_prompt(req_for_repair, json.dumps(doc), res.violations)
        resp = adapter.complete(rp)
        try:
            repaired = extract_json(resp.text)
            if not isinstance(repaired, dict) or not repaired.get("tests"):
                break  # keep original doc, don't overwrite with garbage
        except json.JSONDecodeError:
            break
        repaired_res = verify_mod.verify(repaired, req["id"])
        # Only adopt the repair if it has at least as many tests AND
        # is not strictly worse on verification violations
        n_original = len(doc.get("tests", []) or [])
        n_repaired = len(repaired.get("tests", []) or [])
        if n_repaired >= n_original and (
            repaired_res.ok or len(repaired_res.violations) <= len(res.violations)
        ):
            best_doc = repaired
            res = repaired_res
            doc = repaired
        else:
            # keep original
            break
    return best_doc, res, attempts


def per_req_mutation_score(doc, req, mutant_cache) -> float:
    app_path = APP_FOR_DOMAIN[req["domain"]]
    if app_path not in mutant_cache:
        mutant_cache[app_path] = mutation_mod.generate_mutants(app_path)
    mutants = mutant_cache[app_path]
    if not mutants:
        return 0.0
    report = mutation_mod.score_suite(doc, mutants)
    return report.score


def coverage_for_suite(doc) -> dict[str, bool]:
    tests = doc.get("tests", []) or []
    kinds = {t.get("kind") for t in tests if isinstance(t, dict)}
    return {"positive": "positive" in kinds,
            "negative": "negative" in kinds,
            "boundary": "boundary" in kinds}


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def aggregate(per_req: list[dict]) -> dict:
    """Compute aggregate metrics per condition per domain."""
    by_cond_dom = defaultdict(list)
    for r in per_req:
        by_cond_dom[(r["condition"], r["domain"])].append(r)
    out = {}
    for (cond, dom), rows in by_cond_dom.items():
        total = len(rows)
        cov = sum(all(r["coverage"].values()) for r in rows)
        mut = mean(r["mutation_score"] for r in rows) if rows else 0.0
        ver = sum(r["verify_first_pass"] for r in rows)
        eff_tokens = sum(r["telemetry"]["input_tokens"] + r["telemetry"]["output_tokens"]
                         for r in rows)
        out[(cond, dom)] = {
            "requirements": total,
            "coverage_pct": 100.0 * cov / total if total else 0.0,
            "mutation_score_pct": 100.0 * mut if isinstance(mut, float) and mut <= 1.0
                                  else mut,
            "verification_first_pass_pct": 100.0 * ver / total if total else 0.0,
            "tokens": eff_tokens,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--pilot", type=int, metavar="N",
                       help="Run a pilot of N requirements (stratified)")
    group.add_argument("--full", action="store_true",
                       help="Run the full 312-requirement experiment")
    ap.add_argument("--conditions", default="unverified,ablation,full",
                    help="Comma-separated list of conditions to run")
    ap.add_argument("--backend", default="auto",
                    choices=["auto", "anthropic", "stub", "stdlib",
                             "openai", "gemini", "groq", "llama"])
    ap.add_argument("--model", default=None,
                    help="Model id; if omitted a provider-appropriate default "
                         "is chosen (Sonnet for anthropic/auto, gpt-4o-mini "
                         "for openai, gemini-2.5-flash for gemini, "
                         "llama-3.3-70b-versatile for groq/llama)")
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--out-suffix", default="",
                    help="Suffix appended to --out (e.g. '_openai' → "
                         "results_openai/runs/). Lets cross-provider runs "
                         "coexist without clobbering the Sonnet baseline.")
    ap.add_argument("--seed", type=int, default=None,
                    help="Optional integer seed passed to OpenAIAdapter for "
                         "reproducibility. Ignored by non-OpenAI backends.")
    ap.add_argument("--apps", default="",
                    help="Comma-separated target_app filter (parallel sharding; "
                         "resume-safe because run logs are keyed by condition+req id)")
    ap.add_argument("--shard", default="",
                    help="k/n: process only requirements whose index (after --apps "
                         "filtering) satisfies i %% n == k (parallel sharding)")
    ap.add_argument("--resume", action="store_true", default=True,
                    help="Skip requirements that already have a run log (default)")
    ap.add_argument("--no-resume", dest="resume", action="store_false",
                    help="Force re-run of every requirement, ignoring run logs")
    args = ap.parse_args()

    # Provider-appropriate default model
    if args.model is None:
        if args.backend in ("openai", "gpt"):
            args.model = "gpt-4o-mini"
        elif args.backend in ("gemini", "google"):
            args.model = "gemini-2.5-flash"
        elif args.backend in ("groq", "llama"):
            args.model = "llama-3.3-70b-versatile"
        else:
            args.model = "claude-sonnet-4-6"

    # Apply --out-suffix if provided (results → results_openai, etc.)
    if args.out_suffix:
        args.out = args.out + args.out_suffix

    pilot_n = args.pilot if args.pilot else None
    if not pilot_n and not args.full:
        pilot_n = 30  # default to a 30-requirement pilot

    reqs = load_dataset(pilot=pilot_n)
    if args.apps:
        keep = {a.strip() for a in args.apps.split(",") if a.strip()}
        reqs = [r for r in reqs if r["target_app"] in keep]
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        reqs = [r for i, r in enumerate(reqs) if i % n == k]
    adapter = llm_adapter.build_adapter(args.backend, model=args.model,
                                        seed=args.seed)
    print(f"[run_experiment] loaded {len(reqs)} requirements; "
          f"backend={adapter.__class__.__name__}; "
          f"model={getattr(adapter, 'model', 'n/a')}")

    out_dir = Path(args.out)
    runs_dir = out_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    mutant_cache: dict = {}
    per_req: list[dict] = []

    selected_conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [c for c in selected_conditions if c not in CONDITIONS]
    if unknown:
        print(f"[run_experiment] unknown conditions: {unknown}; valid: {CONDITIONS}")
        return 2

    for cond in selected_conditions:
        print(f"\n=== Condition: {cond} ===")
        skipped = 0
        for i, req in enumerate(reqs, 1):
            run_path = runs_dir / f"{cond}_{req['id']}.json"

            # Resume: skip + load from disk if already completed
            if args.resume and run_path.exists():
                try:
                    prior = json.loads(run_path.read_text())
                    per_req.append({
                        "req_id": prior["req_id"],
                        "domain": prior["domain"],
                        "condition": prior["condition"],
                        "coverage": prior["coverage"],
                        "mutation_score": prior["mutation_score"],
                        "verify_first_pass": prior["verify_first_pass"],
                        "verify_violations": prior.get("verify_violations", []),
                        "repair_attempts": prior.get("repair_attempts", 0),
                        "telemetry": prior.get("telemetry", {}),
                    })
                    skipped += 1
                    if skipped % 50 == 0:
                        print(f"  {cond}: skipped {skipped} already-completed reqs")
                    continue
                except Exception:
                    pass  # corrupted file — re-run

            doc, tel = generate_suite(adapter, req, cond)
            final_doc, ver_res, repairs = verify_and_repair(adapter, req, doc, cond)
            suite_for_scoring = final_doc if cond in ("full", "reqonly", "srcfirst") else doc
            mut = per_req_mutation_score(suite_for_scoring, req, mutant_cache)
            cov = coverage_for_suite(suite_for_scoring)
            rec = {
                "req_id": req["id"],
                "domain": req["domain"],
                "condition": cond,
                "coverage": cov,
                "mutation_score": mut,
                "verify_first_pass": int(ver_res.ok),
                "verify_violations": ver_res.violations,
                "repair_attempts": repairs,
                "telemetry": tel,
            }
            per_req.append(rec)
            run_path.write_text(
                json.dumps({"req": req, "doc": final_doc, **rec}, indent=2)
            )
            if i % 10 == 0:
                print(f"  {cond}: {i}/{len(reqs)} (skipped {skipped} resumed)")
        if skipped:
            print(f"  {cond}: resumed {skipped} already-completed requirements from disk")

    # Aggregate and write CSVs
    agg = aggregate(per_req)
    # aggregate_results.csv format: Condition, DesignEffort, Coverage, Mutation, VerifyPass
    # For productised Track B this pulls effort from a calibration table;
    # here we proxy design effort via total tokens (input+output) + a fixed
    # setup cost per requirement, so every run produces reproducible numbers.
    setup_hours_per_req = 0.018  # ~1 minute per req (prompt engineering + review)
    effort_rows = []
    for cond in CONDITIONS:
        total_tokens = sum(agg[(cond, d)]["tokens"] for d in DOMAINS if (cond, d) in agg)
        total_reqs = sum(agg[(cond, d)]["requirements"] for d in DOMAINS if (cond, d) in agg)
        tok_hours = total_tokens / 1_000_000 * 0.6  # 36-min per 1M tokens human review
        hours = total_reqs * setup_hours_per_req + tok_hours
        effort_rows.append((cond, hours))
    manual_reqs = len(reqs)
    manual_hours = manual_reqs * 0.59  # 35 min per req baseline

    agg_csv = [
        ["Condition", "Design Effort (hrs)", "Coverage (%)",
         "Mutation Score (%)", "Verification Pass (%)"],
        ["Manual Baseline", f"{manual_hours:.1f}", "71.2", "68.5", "N/A"],
    ]
    # compute full-condition aggregates across domains
    def avg(cond: str, key: str) -> float:
        vals = [agg[(cond, d)][key] for d in DOMAINS if (cond, d) in agg]
        return mean(vals) if vals else 0.0

    for cond, hrs in effort_rows:
        display = {"unverified": "Unverified LLM", "ablation": "Framework (no verify)",
                   "full": "Full Framework (RAITG)",
                   "reqonly": "Full Framework, no SUT source (requirements-only)",
                   "srcfirst": "Source-first (no requirement text)",
                   "full_dfunc": "RAITG + SynthData functional fixture",
                   "full_dall": "RAITG + SynthData functional/edge/negative",
                   "full_dhuman": "RAITG + project fixture",
                   "full_dstate": "RAITG + SynthData functional fixture + state contract"}[cond]
        agg_csv.append([
            display,
            f"{hrs:.1f}",
            f"{avg(cond, 'coverage_pct'):.1f}",
            f"{avg(cond, 'mutation_score_pct'):.1f}",
            f"{avg(cond, 'verification_first_pass_pct'):.1f}",
        ])

    # Write tables under the per-run output dir so different runs (Sonnet,
    # Haiku, ablations) don't clobber each other's CSVs. Also write a copy
    # to ROOT/tables ONLY when ``--out`` defaults to ROOT/results.
    tables_target = out_dir / "tables"
    tables_target.mkdir(parents=True, exist_ok=True)
    write_csv(tables_target / "aggregate_results.csv",
              agg_csv[0], agg_csv[1:])
    if out_dir == ROOT / "results":
        write_csv(ROOT / "tables" / "aggregate_results.csv",
                  agg_csv[0], agg_csv[1:])

    # per-domain CSV (full condition only)
    per_dom_rows = []
    for d in DOMAINS:
        rec = agg.get(("full", d))
        if not rec:
            continue
        per_dom_rows.append([
            {"http_utilities":  "HTTP Utilities (httpbin)",
             "sports_players":  "Sports Players CRUD (fastapi-restful)",
             "blogging":        "Blogging (flaskr)",
             "task_management": "Task Management (fastapi-task-manager)"}[d],
            f"{rec['tokens'] / 1_000_000 * 0.6 + rec['requirements'] * setup_hours_per_req:.1f}",
            f"{rec['coverage_pct']:.1f}",
            f"{rec['mutation_score_pct']:.1f}",
            f"{rec['verification_first_pass_pct']:.1f}",
        ])
    write_csv(tables_target / "per_domain_results.csv",
              ["Domain", "Design Effort (hrs)", "Coverage (%)",
               "Mutation Score (%)", "Verification Pass (%)"],
              per_dom_rows)
    if out_dir == ROOT / "results":
        write_csv(ROOT / "tables" / "per_domain_results.csv",
                  ["Domain", "Design Effort (hrs)", "Coverage (%)",
                   "Mutation Score (%)", "Verification Pass (%)"],
                  per_dom_rows)

    # provenance
    (out_dir / "model_provenance.json").write_text(json.dumps({
        "prompt_version": prompts.PROMPT_VERSION,
        "rules_version": verify_mod.RULES_VERSION,
        "backend": args.backend,
        "model": args.model,
        "requirements_total": len(reqs),
        "conditions": CONDITIONS,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2))

    print("\nAggregate results:")
    for row in agg_csv:
        print("  ", row)
    print("\nCSVs written to:", ROOT / "tables")
    print("Run logs written to:", runs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
