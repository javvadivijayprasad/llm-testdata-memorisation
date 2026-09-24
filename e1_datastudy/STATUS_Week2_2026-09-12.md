# Paper H — E1 data study — Week 2 status (12 Sep 2026): all LLM cells run and scored

Everything below is computed from `results/E1_cells.csv` (one row per cell) and the per-cell JSON in
`scores/pc/` and `metrics/pc/`, all derived from the frozen snapshot `arms_snapshot.zip`
(final, 11 Sep 2026 20:29 local, after the `=== DONE ===` of the third runner pass). SynthData 1.2.2,
seed 42, temperature 0, models claude-sonnet-4-6 and gpt-4o. Row cap 500 per table.

## Runs
- 40 LLM cells = {plan-then-execute, direct emission} × {Claude, GPT-4o} × {run 1, run 2} × 5 schemas.
  All 40 completed. Two plan cells (Northwind × GPT-4o, both runs) ended in an engine abort
  (`row.order_date.getTime is not a function`, defect #6) and count as 0 % load for that arm — the
  arm produced no data.
- Runner history (`RUN_E1_LOG.txt`): passes 1–3 (14:11–14:27) failed on key loading (401) — no data;
  pass 4 (14:27–18:15) produced all cells except Chinook × Claude direct, which crashed twice on a
  harness bug (Windows cp1252 default encoding vs. "Łukasz"); pass 5 resumed those two cells after the
  UTF-8 fix (20:07–20:29). The direct-arm `log.json` files therefore contain the early 401 entries as
  `error` records; token/latency totals count successful calls only (`llm_calls` in the CSV).
- Harness note for the paper: direct-arm CSVs written before the fix are cp1252; the cloud scorer
  transcodes them to UTF-8 (`arms/pc/direct_utf8/`, originals untouched) before loading. This changes
  bytes, not values.

## RQ1 — validity (load rate into PostgreSQL with all constraints on)

| schema | plan Claude r1/r2 | plan GPT-4o r1/r2 | direct Claude r1/r2 | direct GPT-4o r1/r2 | auto (no LLM) | Faker | human |
|---|---|---|---|---|---|---|---|
| chinook | 100 / 100 | 100 / 100 | 93.8 / 98.1 | 99.7 / 99.6 | 100 | 99.3 | 100 |
| northwind | 100 / 100 | abort / abort | 98.4 / 97.7 | 77.3 / 77.1 | 100 | 23.5 | 100 |
| dellstore2 | 93.8 / 100 | 93.9 / 93.8 | 99.97 / 98.8 | 100 / 99.97 | 100 | 100 | 100 |
| pagila | 100 / 100 | 100 / 90.8 | 99.9 / 99.6 | 94.7 / 94.4 | 100 | 52.4 | 100 |
| employees | 100 / 100 | 100 / 100 | 99.8 / 99.3 | 98.6 / 97.7 | 100 | 0.4 | 100 |

- Paired over the 20 (schema, provider, run) cells: plan mean 0.886 / median 1.000; direct mean 0.962 /
  median 0.987; Wilcoxon p = 0.85 — **no significant validity difference at 500 rows/table**.
  Excluding the two engine aborts (n = 18): plan 0.985 vs direct 0.983, p = 0.29.
- The distributions differ in shape: plan is **bimodal** — 100 % in 14 of 18 executed cells, and every
  sub-100 cell is one engine defect (#6 expr-date: 443 type errors, pagila GPT-4o r2 + the two Northwind
  aborts; #7 `fk` on a PK column sampled with replacement: 185–187 duplicate PKs in three dellstore2
  cells). Direct emission is **never 100 % on a schema with declared FKs** and degrades with model:
  GPT-4o Northwind 77 % both runs (152/139 FK + 147/164 unique + 13/12 type).
- Violation classes over all executed cells (plan / direct): FK 0 / 504; UNIQUE 559 / 1009; CHECK 0 / 0;
  NOT NULL 0 / 4; type 443 / 79. The engine never emits an FK, CHECK or NOT NULL violation; the
  LLM-written rows do.
- Provider effect: Claude plan 0.994 vs direct 0.985; GPT-4o plan 0.779 (aborts) vs direct 0.939.
- Baselines: `auto` (SynthData, no LLM) = 100 % on all five; Faker 0.4–100 % (fails wherever FKs are
  not 1..N integers); human = 100 % by construction.

## RQ2 — cost and latency (per cell, medians over 20 cells)
- Tokens (in+out): plan 3,472 vs direct 90,340 — **29.5× median ratio**. Totals over the study:
  plan 39.9k in / 30.8k out; direct 864.5k in / 1,441.1k out.
- LLM calls: plan 1; direct 14–63 (200-row chunks).
- Latency: plan median 15 s (one call) vs direct median 658 s (up to 27 min for Pagila with Claude).

## RQ3 — fidelity to the human fixtures (medians of per-column metrics, 18 paired cells)
- JS distance on categorical columns: plan 1.000 vs direct 0.083 (p = 0.003); value coverage plan 0.00
  vs direct 1.00 (p = 0.004) — **direct emission reproduces the human categorical values; the plan arm
  invents its own**. But this is dominated by memorisation: direct Claude scores JS = 0.000 on all 36
  Northwind categorical columns and on Pagila's, i.e. it re-emits the published dataset (Northwind and
  Sakila/Pagila are in every training corpus). On the less famous dellstore2 the direct arm's JS is
  0.41/0.88 and value coverage 0.88/0.22 — no better than the plan arm (0.47/0.86, 0.60/0.19).
- Numeric/date KS: plan 0.501 vs direct 0.522 (p = 0.83, no difference). Range coverage: plan 0.960 vs
  direct 0.520 (p = 0.019) — plans cover the human numeric/date ranges better; LLM-written rows cluster.
  Pagila KS = 1.0 for every arm because all `last_update`/rental dates in the human data are 2005–2006
  while every arm generated 2025 dates (the metric is dominated by the 30 timestamp columns).
- FK fan-out Gini abs. diff: plan 0.101 vs direct 0.068 (p = 0.028) — the LLM-written rows imitate the
  human fan-out slightly better; the engine's `fk` sampling is closer to uniform.

## Profiles (engine only, run-1 plans, no extra LLM calls)
- `edge`: 100 % load on all schemas except dellstore2 (93.8 %, defect #7 again). Northwind × GPT-4o's
  plan executes under `edge` (rc 0, 100 %) although it aborts under `functional`/`negative` — the expr
  column is evidently not evaluated on that path; recorded as is.
- `negative`: 0 % load on every schema — by design each row carries a deliberate violation; the scorer
  reports them as type / not_null / fk / check classes, which is the property a negative fixture needs
  (every emitted row is rejected for a stated reason).

## SynthData defects found by the study (1.2.2 stays frozen; to fix in the next release)
- #6 `expr` receives DATE/TIMESTAMP values as strings: `row.order_date.getTime` aborts the run (Northwind
  GPT-4o r1, r2, and negative profile); `row.rental_date + 7` concatenates → "2025-03-18 16:25:007"
  (pagila GPT-4o r2, 443 rejected rows).
- #7 `{gen: fk, ref: other.col}` on a PRIMARY KEY column (dellstore2 `products.prod_id` ↔
  `inventory.prod_id`, no declared FK) samples with replacement → 185–187 duplicate PKs. Should sample
  without replacement or refuse `fk` on PK/UNIQUE columns.

## Threats to record
- Memorisation of public datasets (Northwind, Pagila/Sakila, Chinook) inflates direct-arm fidelity;
  a renamed-schema condition is the natural control (Week 3 option, ~$20).
- Row cap 500/table; the direct arm's chunked resume was exercised (harness restarts), which is part
  of the cost record, not of the validity record.
- Two runs per cell at temperature 0: run-to-run differences exist for both arms (e.g. dellstore2
  Claude plan 93.8 vs 100; Chinook Claude direct 93.8 vs 98.1), so temperature 0 is not determinism.

## Files
`results/E1_cells.csv` · `scores/pc/{plan,direct}_<schema>_<provider>_r<n>.json` ·
`scores/pc/planprof_<cell>_{edge,negative}.json` · `metrics/pc/*.json` · `arms_snapshot.zip` (frozen
outputs) · `RUN_E1_LOG.txt` · `arm_direct.py`/`arm_plan.py` (UTF-8 fix, 11 Sep).
