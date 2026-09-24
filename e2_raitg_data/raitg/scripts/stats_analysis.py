"""Statistical analysis for the RAITG experiment.

Computes:
  * Bootstrap 95% confidence intervals on per-requirement metrics
  * Cohen's d effect size between conditions
  * Paired Wilcoxon signed-rank test p-value (no scipy; using mid-rank fallback)
  * Per-domain significance tests

Writes:
  tables/statistics.csv
  tables/bootstrap_confidence_intervals.csv

Usage:
    python scripts/statistics.py
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
RUNS = ROOT / "results" / "runs"
TAB = ROOT / "tables"
TAB.mkdir(exist_ok=True)

# Deterministic seed for bootstrap
random.seed(20260421)

CONDITIONS = ["unverified", "ablation", "full"]
DOMAINS = ["commercial_web", "financial_services", "healthcare", "logistics"]


def load_per_req() -> list[dict]:
    out = []
    for f in sorted(RUNS.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        cov = d.get("coverage") or {}
        out.append({
            "req_id": d.get("req_id") or (d.get("req") or {}).get("id"),
            "condition": d.get("condition"),
            "domain": d.get("domain") or (d.get("req") or {}).get("domain"),
            "coverage": int(bool(cov) and all(cov.values())),
            "mutation": float(d.get("mutation_score") or 0.0),
            "verify": int(d.get("verify_first_pass") or 0),
        })
    return out


def bootstrap_ci(values: list[float], n_boot: int = 5000,
                 alpha: float = 0.05) -> tuple[float, float, float]:
    """(mean, lower, upper) for the given alpha level."""
    if not values:
        return 0.0, 0.0, 0.0
    n = len(values)
    means = []
    for _ in range(n_boot):
        sample = [values[random.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(n_boot * alpha / 2)]
    hi = means[int(n_boot * (1 - alpha / 2))]
    return mean(values), lo, hi


def cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d for two independent samples. Positive → a > b."""
    if not a or not b:
        return 0.0
    ma, mb = mean(a), mean(b)
    # pooled standard deviation
    try:
        sa, sb = stdev(a) if len(a) > 1 else 0.0, stdev(b) if len(b) > 1 else 0.0
    except Exception:
        return 0.0
    pooled = math.sqrt((sa ** 2 + sb ** 2) / 2) if (sa or sb) else 0.0
    if pooled == 0:
        return 0.0
    return (ma - mb) / pooled


def _wilcoxon_signed_rank(diffs: list[float]) -> tuple[float, float]:
    """Approximate Wilcoxon signed-rank test.

    Returns (W, p_approx) using normal approximation. Adequate for n >= 20.
    """
    non_zero = [d for d in diffs if d != 0]
    n = len(non_zero)
    if n < 6:
        return 0.0, 1.0
    abs_vals = sorted(enumerate(non_zero), key=lambda x: abs(x[1]))
    # Mid-rank assignment
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs_vals[j + 1][1]) == abs(abs_vals[i][1]):
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[abs_vals[k][0]] = avg_rank
        i = j + 1
    W_plus = sum(r for r, d in zip(ranks, non_zero) if d > 0)
    W_minus = sum(r for r, d in zip(ranks, non_zero) if d < 0)
    W = min(W_plus, W_minus)
    # Normal approximation
    mu = n * (n + 1) / 4
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    if sigma == 0:
        return W, 1.0
    z = (W - mu) / sigma
    # Two-sided p via normal CDF
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return W, p


def paired_test(rows: list[dict], metric: str,
                cond_a: str, cond_b: str) -> dict:
    """Pair rows by req_id and run the test on difference series."""
    a_by_id = {r["req_id"]: r[metric] for r in rows if r["condition"] == cond_a}
    b_by_id = {r["req_id"]: r[metric] for r in rows if r["condition"] == cond_b}
    common = sorted(set(a_by_id) & set(b_by_id))
    diffs = [a_by_id[i] - b_by_id[i] for i in common]
    a_vals = [a_by_id[i] for i in common]
    b_vals = [b_by_id[i] for i in common]
    W, p = _wilcoxon_signed_rank(diffs)
    d = cohens_d(a_vals, b_vals)
    ma, lo_a, hi_a = bootstrap_ci(a_vals)
    mb, lo_b, hi_b = bootstrap_ci(b_vals)
    return {
        "metric": metric,
        "cond_a": cond_a, "cond_b": cond_b,
        "n": len(common),
        "a_mean": ma, "a_ci_lo": lo_a, "a_ci_hi": hi_a,
        "b_mean": mb, "b_ci_lo": lo_b, "b_ci_hi": hi_b,
        "diff_mean": ma - mb,
        "cohens_d": d,
        "wilcoxon_W": W,
        "wilcoxon_p": p,
        "significant_p05": int(p < 0.05),
        "significant_p01": int(p < 0.01),
    }


def main() -> int:
    rows = load_per_req()
    if not rows:
        print("No run logs found under results/runs/")
        return 1
    print(f"Loaded {len(rows)} per-requirement records")

    # ----------------- bootstrap CIs per condition × metric -----------------
    ci_rows = []
    for cond in CONDITIONS:
        vals = [r for r in rows if r["condition"] == cond]
        for metric in ("coverage", "mutation", "verify"):
            values = [float(r[metric]) for r in vals]
            m, lo, hi = bootstrap_ci(values)
            # Express coverage and verify as %
            scale = 100.0 if metric in ("coverage", "verify", "mutation") else 1.0
            ci_rows.append({
                "condition": cond,
                "metric": metric,
                "n": len(values),
                "mean": round(scale * m, 2),
                "ci95_lo": round(scale * lo, 2),
                "ci95_hi": round(scale * hi, 2),
            })

    with (TAB / "bootstrap_confidence_intervals.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["condition", "metric", "n", "mean",
                                          "ci95_lo", "ci95_hi"])
        w.writeheader()
        w.writerows(ci_rows)
    print(f"Wrote {TAB / 'bootstrap_confidence_intervals.csv'}")

    # ----------------- pairwise significance tests ---------------------------
    sig_rows = []
    pairs = [
        ("full", "unverified"),
        ("full", "ablation"),
        ("ablation", "unverified"),
    ]
    for a, b in pairs:
        for metric in ("coverage", "mutation", "verify"):
            r = paired_test(rows, metric, a, b)
            sig_rows.append(r)

    with (TAB / "statistics.csv").open("w", newline="") as f:
        fields = ["metric", "cond_a", "cond_b", "n",
                  "a_mean", "a_ci_lo", "a_ci_hi",
                  "b_mean", "b_ci_lo", "b_ci_hi",
                  "diff_mean", "cohens_d",
                  "wilcoxon_W", "wilcoxon_p",
                  "significant_p05", "significant_p01"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in sig_rows:
            w.writerow({k: round(r[k], 4) if isinstance(r[k], float) else r[k]
                        for k in fields})
    print(f"Wrote {TAB / 'statistics.csv'}")

    # ----------------- per-domain paired tests --------------------------------
    per_domain_rows = []
    for dom in DOMAINS:
        sub = [r for r in rows if r["domain"] == dom]
        for a, b in [("full", "unverified"), ("full", "ablation")]:
            for metric in ("coverage", "verify"):
                res = paired_test(sub, metric, a, b)
                per_domain_rows.append({"domain": dom, **res})

    with (TAB / "per_domain_significance.csv").open("w", newline="") as f:
        fields = ["domain", "metric", "cond_a", "cond_b", "n",
                  "diff_mean", "cohens_d", "wilcoxon_p", "significant_p05"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in per_domain_rows:
            w.writerow({k: (round(r[k], 4) if isinstance(r[k], float) else r[k])
                        for k in fields})
    print(f"Wrote {TAB / 'per_domain_significance.csv'}")

    # ----------------- print summary -----------------------------------------
    print("\n=== Bootstrap 95% CIs ===")
    for r in ci_rows:
        print(f"  {r['condition']:11} {r['metric']:9}  "
              f"mean={r['mean']:.1f}  "
              f"95% CI=[{r['ci95_lo']:.1f}, {r['ci95_hi']:.1f}]  n={r['n']}")

    print("\n=== Pairwise Significance ===")
    for r in sig_rows:
        stars = "**" if r["significant_p01"] else ("*" if r["significant_p05"] else "")
        print(f"  {r['cond_a']:10} vs {r['cond_b']:10} "
              f"[{r['metric']:8}]  "
              f"Δ={100 * r['diff_mean']:+.1f}pp  "
              f"d={r['cohens_d']:+.2f}  "
              f"p={r['wilcoxon_p']:.4f} {stars}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
