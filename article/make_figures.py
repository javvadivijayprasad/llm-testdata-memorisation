#!/usr/bin/env python3
"""Paper H figures, every value read from results CSVs (E1_cells.csv, E1b_renamed_vs_original.csv, E2_cells.csv)."""
import csv, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
E1 = "/home/claude/work/paperH/exp/e1/results/"; E2 = "/home/claude/work/paperH/exp/e2/results/"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
C = {"plan": "#2a6f97", "direct": "#c8553d", "auto": "#5a5a5a", "faker": "#a8a8a8", "G": "#5a5a5a", "dfunc": "#2a6f97", "dall": "#1b4965", "dhuman": "#c8553d"}
e1 = list(csv.DictReader(open(E1 + "E1_cells.csv")))
SCH = ["chinook", "northwind", "dellstore2", "pagila", "employees"]
def cell(arm, s, p, r): return next(x for x in e1 if x["arm"] == arm and x["subject"] == s and x["provider"] == p and x["run"] == r)
# Fig 1: load rate per schema, plan vs direct, both providers, both runs (dots), + auto/faker markers
fig, ax = plt.subplots(figsize=(6.4, 3.0))
x = np.arange(len(SCH)); off = {"plan": -0.18, "direct": 0.18}
for arm in ("plan", "direct"):
    for p, mk in (("anthropic", "o"), ("openai", "s")):
        for r in ("1", "2"):
            ys = [float(cell(arm, s, p, r)["load_rate"]) * 100 for s in SCH]
            ax.scatter(x + off[arm] + (0.06 if p == "openai" else -0.06), ys, color=C[arm], marker=mk, s=26, alpha=0.85,
                       label=f"{arm} · {'Claude' if p=='anthropic' else 'GPT-4o'}" if r == "1" else None, zorder=3)
for arm, mk in (("auto", "_"), ("faker", "x")):
    ys = [float(next(x for x in e1 if x["arm"] == arm and x["subject"] == ("v122_" + s if arm == "auto" else s))["load_rate"]) * 100 for s in SCH]
    ax.scatter(x, ys, color=C[arm], marker=mk, s=60, label=f"{'auto (no LLM)' if arm=='auto' else 'Faker'}", zorder=2)
ax.set_xticks(x); ax.set_xticklabels(SCH); ax.set_ylabel("rows loaded (%)"); ax.set_ylim(-3, 103)
ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False); ax.grid(axis="y", lw=0.4, alpha=0.5)
fig.tight_layout(); fig.savefig("figures/fig1_e1_load.pdf", bbox_inches="tight"); plt.close(fig)
# Fig 2: tokens per cell (in+out), log scale, plan vs direct
fig, ax = plt.subplots(figsize=(3.4, 2.6))
for i, arm in enumerate(("plan", "direct")):
    v = [int(x["input_tokens"]) + int(x["output_tokens"]) for x in e1 if x["arm"] == arm]
    ax.scatter(np.full(len(v), i) + np.random.default_rng(1).uniform(-0.12, 0.12, len(v)), v, color=C[arm], s=18, alpha=0.8)
    ax.hlines(np.median(v), i - 0.25, i + 0.25, color="k", lw=1.2)
ax.set_yscale("log"); ax.set_xticks([0, 1]); ax.set_xticklabels(["plan-then-execute", "direct emission"]); ax.set_ylabel("LLM tokens per schema (in + out)")
ax.grid(axis="y", lw=0.4, alpha=0.5); fig.tight_layout(); fig.savefig("figures/fig2_e1_tokens.pdf"); plt.close(fig)
# Fig 3: E1b JS distance original vs renamed, direct arm, per schema x provider
b = [x for x in csv.DictReader(open(E1 + "E1b_renamed_vs_original.csv")) if x["arm"] == "direct"]
fig, ax = plt.subplots(figsize=(6.4, 2.6))
lab = [f"{x['subject']}\n{'Claude' if x['provider']=='anthropic' else 'GPT-4o'}" for x in b]
xo = np.arange(len(b))
ax.bar(xo - 0.18, [float(x["js_orig"]) for x in b], 0.36, color=C["direct"], label="original schema")
ax.bar(xo + 0.18, [float(x["js_renamed"]) for x in b], 0.36, color="#e8a598", label="renamed schema")
# run-2 value of the ORIGINAL schema = the run-to-run noise reference for each cell (median |delta| 0.000, max 0.056)
r2 = []
for x in b:
    c2 = next((y for y in e1 if y["arm"] == "direct" and y["subject"] == x["subject"] and y["provider"] == x["provider"] and y["run"] == "2"), None)
    r2.append(float(c2["js_median"]) if c2 and c2["js_median"] else np.nan)
ax.scatter(xo - 0.18, r2, marker="_", color="k", s=90, lw=1.4, zorder=4, label="original schema, run 2 (run-to-run reference)")
ax.set_xticks(xo); ax.set_xticklabels(lab, fontsize=7); ax.set_ylabel("JS distance to human data\n(categorical columns, median)"); ax.set_ylim(0, 1.05)
ax.legend(frameon=False, fontsize=7, loc="upper left"); fig.tight_layout(); fig.savefig("figures/fig3_e1b_memorisation.pdf"); plt.close(fig)
# Fig 4: E2 kills per arm, provider x run
e2 = [x for x in csv.DictReader(open(E2 + "E2_cells.csv")) if x["sut"] == "ALL"]
fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.6), sharey=True)
names = {"g": "G", "dfunc": "+functional", "dall": "+func/edge/neg", "dhuman": "+project fixture"}
for ax, prov in zip(axes, ("sonnet", "gpt4o")):
    for j, arm in enumerate(("g", "dfunc", "dall", "dhuman")):
        for r, mk in (("1", "o"), ("2", "^")):
            k = int(next(x for x in e2 if x["provider"] == prov and x["arm"] == arm and x["run"] == r)["killed"])
            ax.scatter(j, k, color=C[arm if arm != "g" else "G"], marker=mk, s=40, zorder=3, label=f"run {r}" if j == 0 else None)
    ax.set_xticks(range(4)); ax.set_xticklabels([names[a] for a in ("g", "dfunc", "dall", "dhuman")], fontsize=7, rotation=15)
    ax.set_title("Claude Sonnet 4.6" if prov == "sonnet" else "GPT-4o", fontsize=9); ax.grid(axis="y", lw=0.4, alpha=0.5)
axes[0].set_ylabel("mutants killed (of 293)"); axes[0].legend(frameon=False, fontsize=7)
fig.tight_layout(); fig.savefig("figures/fig4_e2_kills.pdf"); plt.close(fig)
# Fig 5: E2 usable yield per arm
fig, ax = plt.subplots(figsize=(3.6, 2.6))
for prov, mk in (("sonnet", "o"), ("gpt4o", "s")):
    for r in ("1", "2"):
        ys = [float(next(x for x in e2 if x["provider"] == prov and x["arm"] == a and x["run"] == r)["usable_fraction"]) * 100 for a in ("g", "dfunc", "dall", "dhuman")]
        ax.plot(range(4), ys, marker=mk, color="#2a6f97" if prov == "sonnet" else "#c8553d", alpha=0.8, lw=0.8, label=("Claude" if prov == "sonnet" else "GPT-4o") if r == "1" else None)
ax.set_xticks(range(4)); ax.set_xticklabels([names[a] for a in ("g", "dfunc", "dall", "dhuman")], fontsize=7, rotation=15)
ax.set_ylabel("usable (known-good) units, %"); ax.legend(frameon=False, fontsize=7); ax.grid(axis="y", lw=0.4, alpha=0.5)
fig.tight_layout(); fig.savefig("figures/fig5_e2_yield.pdf"); plt.close(fig)
print("figures written")
