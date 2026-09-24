"""Summarize cross-provider (Sonnet vs GPT-4o-mini) and 3-seed variance
executable-mutation results.

Inputs (all produced by scripts/mutation_v3_raitg.py):
  - results/mutation_v3_raitg.json               (Sonnet baseline, all conditions)
  - results_openai/mutation_v3_raitg.json        (OpenAI seed 0, all conditions)
  - results_openai_seed1/mutation_v3_raitg.json  (OpenAI seed 1, ablation only)
  - results_openai_seed2/mutation_v3_raitg.json  (OpenAI seed 2, ablation only)

Outputs:
  - tables/cross_provider_summary.csv
  - tables/seed_variance_summary.csv
Prints both to stdout in a readable format.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
TABLES = ROOT / "tables"
TABLES.mkdir(exist_ok=True)

APPS = ["banking-api", "fhir-lite", "hr-app", "logistics-app"]

SONNET_PATH = ROOT / "results" / "mutation_v3_raitg.json"
OPENAI0_PATH = ROOT / "results_openai" / "mutation_v3_raitg.json"
OPENAI1_PATH = ROOT / "results_openai_seed1" / "mutation_v3_raitg.json"
OPENAI2_PATH = ROOT / "results_openai_seed2" / "mutation_v3_raitg.json"


def load(p: Path) -> dict:
    return json.loads(p.read_text())


def index_by_app(payload: dict, condition: str) -> dict[str, dict]:
    """Return {app: row} for entries with matching condition."""
    return {r["app"]: r for r in payload["per_app_per_condition"]
            if r["condition"] == condition}


def score_pct(row: dict) -> float:
    """Extract mutation score as percentage (0-100)."""
    return 100.0 * row["mutation_score"]


def fmt(x: float) -> str:
    return f"{x:.2f}"


def signed(x: float) -> str:
    if x >= 0:
        return f"+{x:.2f}"
    return f"{x:.2f}"


def build_cross_provider(sonnet: dict, openai0: dict) -> list[dict]:
    """Build cross-provider summary rows."""
    s_ab = index_by_app(sonnet, "ablation")
    s_fu = index_by_app(sonnet, "full")
    o_ab = index_by_app(openai0, "ablation")
    o_fu = index_by_app(openai0, "full")

    rows = []
    agg = {"mutants": 0, "s_ab_k": 0, "o_ab_k": 0, "s_fu_k": 0, "o_fu_k": 0}
    for app in APPS:
        sab = s_ab[app]; ofu = o_fu[app]
        oab = o_ab[app]; sfu = s_fu[app]
        mutants = sab["mutants"]
        s_ab_pct = score_pct(sab)
        o_ab_pct = score_pct(oab)
        s_fu_pct = score_pct(sfu)
        o_fu_pct = score_pct(ofu)
        rows.append({
            "sut": app,
            "mutants": mutants,
            "sonnet_ablation": s_ab_pct,
            "openai_ablation": o_ab_pct,
            "sonnet_full": s_fu_pct,
            "openai_full": o_fu_pct,
            "sonnet_vs_openai_ablation_delta": s_ab_pct - o_ab_pct,
            "sonnet_vs_openai_full_delta": s_fu_pct - o_fu_pct,
        })
        agg["mutants"] += mutants
        agg["s_ab_k"] += sab["killed"]
        agg["o_ab_k"] += oab["killed"]
        agg["s_fu_k"] += sfu["killed"]
        agg["o_fu_k"] += ofu["killed"]

    def _pct(k, m):
        return 100.0 * k / max(1, m)

    s_ab_pct = _pct(agg["s_ab_k"], agg["mutants"])
    o_ab_pct = _pct(agg["o_ab_k"], agg["mutants"])
    s_fu_pct = _pct(agg["s_fu_k"], agg["mutants"])
    o_fu_pct = _pct(agg["o_fu_k"], agg["mutants"])
    rows.append({
        "sut": "AGGREGATE",
        "mutants": agg["mutants"],
        "sonnet_ablation": s_ab_pct,
        "openai_ablation": o_ab_pct,
        "sonnet_full": s_fu_pct,
        "openai_full": o_fu_pct,
        "sonnet_vs_openai_ablation_delta": s_ab_pct - o_ab_pct,
        "sonnet_vs_openai_full_delta": s_fu_pct - o_fu_pct,
    })
    return rows


def build_seed_variance(openai0: dict, openai1: dict, openai2: dict) -> list[dict]:
    """Build 3-seed variance rows (ablation only)."""
    o0 = index_by_app(openai0, "ablation")
    o1 = index_by_app(openai1, "ablation")
    o2 = index_by_app(openai2, "ablation")

    rows = []
    tot_m = 0; tot_k = [0, 0, 0]
    for app in APPS:
        r0 = o0[app]; r1 = o1[app]; r2 = o2[app]
        mutants = r0["mutants"]
        s0, s1, s2 = score_pct(r0), score_pct(r1), score_pct(r2)
        vals = [s0, s1, s2]
        row = {
            "sut": app,
            "mutants": mutants,
            "openai_seed0": s0,
            "openai_seed1": s1,
            "openai_seed2": s2,
            "min": min(vals),
            "max": max(vals),
            "range": max(vals) - min(vals),
            "mean": statistics.mean(vals),
            "stdev": statistics.stdev(vals),
        }
        rows.append(row)
        tot_m += mutants
        tot_k[0] += r0["killed"]; tot_k[1] += r1["killed"]; tot_k[2] += r2["killed"]

    agg_vals = [100.0 * k / max(1, tot_m) for k in tot_k]
    rows.append({
        "sut": "AGGREGATE",
        "mutants": tot_m,
        "openai_seed0": agg_vals[0],
        "openai_seed1": agg_vals[1],
        "openai_seed2": agg_vals[2],
        "min": min(agg_vals),
        "max": max(agg_vals),
        "range": max(agg_vals) - min(agg_vals),
        "mean": statistics.mean(agg_vals),
        "stdev": statistics.stdev(agg_vals),
    })
    return rows


def write_cross_csv(rows: list[dict]) -> Path:
    out = TABLES / "cross_provider_summary.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sut", "mutants", "sonnet_ablation", "openai_ablation",
                    "sonnet_full", "openai_full",
                    "sonnet_vs_openai_ablation_delta",
                    "sonnet_vs_openai_full_delta"])
        for r in rows:
            w.writerow([
                r["sut"], r["mutants"],
                fmt(r["sonnet_ablation"]), fmt(r["openai_ablation"]),
                fmt(r["sonnet_full"]), fmt(r["openai_full"]),
                signed(r["sonnet_vs_openai_ablation_delta"]),
                signed(r["sonnet_vs_openai_full_delta"]),
            ])
    return out


def write_variance_csv(rows: list[dict]) -> Path:
    out = TABLES / "seed_variance_summary.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sut", "mutants", "openai_seed0", "openai_seed1",
                    "openai_seed2", "min", "max", "range", "mean", "stdev"])
        for r in rows:
            w.writerow([
                r["sut"], r["mutants"],
                fmt(r["openai_seed0"]), fmt(r["openai_seed1"]),
                fmt(r["openai_seed2"]),
                fmt(r["min"]), fmt(r["max"]), fmt(r["range"]),
                fmt(r["mean"]), fmt(r["stdev"]),
            ])
    return out


def print_cross(rows: list[dict]) -> None:
    print("\n=== Cross-provider summary (Sonnet vs GPT-4o-mini) ===")
    header = f"{'SUT':<14} {'N':>4} {'S-Abl':>7} {'O-Abl':>7} {'Delta':>7} {'S-Full':>7} {'O-Full':>7} {'Delta':>7}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['sut']:<14} {r['mutants']:>4} "
              f"{r['sonnet_ablation']:>7.2f} {r['openai_ablation']:>7.2f} "
              f"{r['sonnet_vs_openai_ablation_delta']:>+7.2f} "
              f"{r['sonnet_full']:>7.2f} {r['openai_full']:>7.2f} "
              f"{r['sonnet_vs_openai_full_delta']:>+7.2f}")


def print_variance(rows: list[dict]) -> None:
    print("\n=== 3-seed variance (OpenAI GPT-4o-mini, ablation only) ===")
    header = f"{'SUT':<14} {'N':>4} {'Seed0':>7} {'Seed1':>7} {'Seed2':>7} {'Min':>7} {'Max':>7} {'Range':>6} {'Mean':>7} {'Stdev':>6}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['sut']:<14} {r['mutants']:>4} "
              f"{r['openai_seed0']:>7.2f} {r['openai_seed1']:>7.2f} {r['openai_seed2']:>7.2f} "
              f"{r['min']:>7.2f} {r['max']:>7.2f} {r['range']:>6.2f} "
              f"{r['mean']:>7.2f} {r['stdev']:>6.2f}")


def main() -> int:
    for p in [SONNET_PATH, OPENAI0_PATH, OPENAI1_PATH, OPENAI2_PATH]:
        if not p.exists():
            raise SystemExit(f"missing input: {p}")

    sonnet = load(SONNET_PATH)
    openai0 = load(OPENAI0_PATH)
    openai1 = load(OPENAI1_PATH)
    openai2 = load(OPENAI2_PATH)

    cross_rows = build_cross_provider(sonnet, openai0)
    var_rows = build_seed_variance(openai0, openai1, openai2)

    out_cross = write_cross_csv(cross_rows)
    out_var = write_variance_csv(var_rows)

    print_cross(cross_rows)
    print_variance(var_rows)

    print(f"\nWrote {out_cross}")
    print(f"Wrote {out_var}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
