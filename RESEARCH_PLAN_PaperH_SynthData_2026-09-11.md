# Paper H — Test-Data Provisioning for LLM-Generated Tests
## Research plan v0.1 — 11 September 2026

**Working title:** *Plan, Don't Emit: LLM-Planned, Engine-Executed Test Data and Its Effect on
LLM-Generated Test Suites — An Executable Study Against Human-Authored Fixtures*

**Artifact under study:** SynthData v1.1.0 (`@vijaypjavvadi/synthdata`, E:\Sy\testforge) —
DDL + business case → LLM writes a YAML generation plan → deterministic engine executes it
(FK dependency order, guaranteed-valid FKs incl. self-reference, UNIQUE/composite-UNIQUE,
CHECK IN/BETWEEN/cross-column, seeds, four profiles: functional / edge / negative / volume).

**Two tracks, two venues.**
- Software paper → JOSS (roadmap: submit 2 Jan 2027; v1.3/1.4 by then). Not this document.
- Empirical paper (this plan) → Information and Software Technology (first choice), Empirical
  Software Engineering (second). Target submission: mid-November 2026.

**Rules (NO_SHORTCUTS policy):** every number executable and traceable to a CSV; independent
human baselines the author did not write; frozen artifacts with MD5s; two independent runs per
LLM arm; two providers; per-condition token counts logged (the invariant that caught the
Paper E fault); Zenodo bundle + git tag before submission.

---

## Research questions

- **RQ1 (data validity).** Does plan-then-execute produce test data that satisfies the schema's
  declared constraints more reliably than direct LLM row emission, at what cost?
- **RQ2 (fidelity).** How close is LLM-planned data to the human-authored fixture data that
  real projects ship — in row ratios, value distributions, enum coverage and referential shape?
- **RQ3 (coverage of intent).** Do the edge/negative profiles cover the constraint surface
  (every enum value, every CHECK endpoint, every nullable column, every violation class) that
  human fixtures cover, and what do humans cover that the profiles miss?
- **RQ4 (downstream).** Given the same LLM test generator (RAITG, grounded arm, Paper E
  pipeline v1.4.0), does provisioning constraint-valid fixtures raise (a) the usable-test yield
  and (b) executable mutation kill rate, versus letting the generator invent its own data?
- **RQ5 (provider).** Do RQ1–RQ4 hold across two model families (Claude Sonnet 4.6, GPT-4o)?

## Experiment E1 — data provisioning vs human fixtures (RQ1–RQ3, RQ5)

**Subjects (schemas with human-authored sample data, all open-licensed):**

| Schema | Source (pinned) | Tables | Human fixture rows | Constraints | Notes |
|---|---|---|---|---|---|
| Pagila | devrimgunduz/pagila tag pagila-v3.1.0 (fef9675, BSD) | 22 (incl. 7 payment partitions) | 46,273 | 22 PK, 36 FK, 1 enum type (mpaa_rating) | PostgreSQL-native Sakila port; master (v4.1) needs PG18 → pinned v3.1.0 |
| Chinook | lerocha/chinook-database 7f67772 (v1.4.5, MIT) | 11 | 15,607 | 11 PK, 11 FK | music store; self-ref employee.reports_to |
| Northwind | pthom/northwind_psql cd0ef28 (MIT) | 14 | 3,362 | 14 PK, 13 FK | orders; composite PK order_details; self-ref employees.reports_to |
| employees | datacharmer/test_db e324b56 (CC BY-SA 3.0) | 6 | 3,919,015 | 6 PK, 6 FK, 1 CHECK, 1 UNIQUE | large; row targets scaled down (cap 2,000/table for LLM arms; human distributions from full data) |
| dellstore2 | Dell DVD Store 2 (normal-1.0) via morenoh149/postgresDBSamples 2bdc953 | 8 | 172,716 | 5 PK, 3 FK | replaces AdventureWorksLT: no PostgreSQL-native LT port is available; full AdventureWorks (68 tables, xml/hierarchyid) exceeds SynthData's DDL parser scope — kept as optional stretch subject |
| + Paper E SUT schemas | flaskr, fastapi-task-manager, fastapi-restful (players) | 1–3 | project fixtures | | link E1 → E2; httpbin has no DB → E1 excluded, E2 negative control |

All five loaded clean into PostgreSQL 16.13 with constraints on (11 Sep 2026); MD5s of every
DDL/data file in `Evidences/SUBJECT_MANIFEST_2026-09-11.json`. Observation to carry into the
design: the human schemas declare few CHECK constraints (1 across the five) — the constraint
surface is dominated by PK/FK/NOT NULL/enum-typed columns, so RQ3's "CHECK endpoint coverage"
will be measured mainly on the Paper E SUT schemas and on column domains inferred from the
human data (min/max, enum-like text columns), stated explicitly as such.

Business case per schema: written once from the project's own README/documentation (not by
reading the fixture data), frozen with MD5 before any generation.

**Arms (per schema × provider × 2 runs):**
1. **Direct emission** — LLM asked to emit rows as CSV/INSERTs for the DDL + business case
   (the naive approach; row target = human fixture count, capped at 2,000/table for cost).
2. **Plan-then-execute** — SynthData `plan` (LLM) + `generate` (engine), same row targets,
   profiles functional (main), edge, negative, volume.
3. **Schema-only** — SynthData `auto` mode (no LLM; Faker-style defaults from DDL).
4. **Faker baseline** — plain Faker/Mimesis script per schema, no FK resolution (the ecosystem
   default; shows what "no relational engine" costs).
5. **Human fixtures** — the project's shipped sample data, unmodified (independent baseline).

**Metrics (all computed by scripts, per table and aggregate):**
- Load success into PostgreSQL 16 with all constraints on (rows accepted / rows emitted).
- Violations by class: FK, UNIQUE, CHECK, NOT NULL, type/length — count and rate.
- Constraint-surface coverage: enum values hit / declared; CHECK endpoints hit; nullable
  columns with ≥1 NULL; FK fan-out distribution (Gini) vs human.
- Fidelity to human fixtures: per-column distribution distance (Jensen–Shannon for
  categorical, Kolmogorov–Smirnov for numeric/date), row-ratio error vs human table ratios.
- Reproducibility: byte-identical output under same seed (yes/no); plan stability across the
  two runs (YAML diff size).
- Cost: input/output tokens, wall time, per 1,000 rows.
- Statistics: paired per-table comparisons across arms (Wilcoxon signed-rank), bootstrap CIs
  stratified by schema; two runs reported side by side, never pooled.

## Experiment E2 — provisioned data and LLM-generated tests (RQ4, RQ5)

Reuse Paper E verbatim: 172 requirements, 293 frozen mutants (MD5-verified), scoring harness
v2, community baseline 153/293. SUTs with a database: flaskr (SQLite), fastapi-task-manager
(SQLite), fastapi-restful (players.db); httpbin has no DB → scored but expected unchanged
(acts as a negative control).

**Arms (Claude Sonnet 4.6 and GPT-4o; 2 runs each):**
- **G** — grounded RAITG (Paper E full arm; re-used run logs for Claude run 1/2, new for GPT-4o).
- **G+D-func** — grounded + SynthData functional fixture (≈20–50 rows/table) injected as a
  `[TEST DATA]` block (fixture file path + a compact preview) and a conftest that loads it.
- **G+D-all** — grounded + functional + edge + negative fixtures, with the negative rows'
  `_violation` tags exposed so the model can write validation tests against them.
- **G+D-human** — grounded + the project's own fixture data (where it exists) — the human
  control for the data block.

**Metrics:** raw units, known-good units (usable yield — the mechanism Paper E identified),
mutation kill rate per SUT and aggregate, paired McNemar vs G, bootstrap CIs, kills per 100
known-good units, tokens. Hypothesis (pre-registered here): the data block raises usable yield
on the three DB-backed SUTs and leaves httpbin unchanged; kill-rate gain, if any, concentrates
on constant/return-value mutants in validation paths.

## Threats to plan for now
- Human fixtures are small on some schemas (Northwind ~3k rows) → report per-table, not pooled.
- Business-case authoring could leak fixture knowledge → write cases from docs only, freeze,
  publish MD5 before runs.
- SynthData is the author's tool → all arms use identical schemas, row targets and seeds;
  the Faker and direct-emission arms get the same business case verbatim; scripts public.
- E2 adds context tokens → report token counts per arm (the Paper E invariant).

## Work plan (dates are targets)

| Week | Dates | Deliverable |
|---|---|---|
| 1 | Sep 15–19 | Freeze subjects: fetch 5 schemas + human fixtures, write & MD5 business cases; PostgreSQL 16 loader + violation scorer; Faker baseline scripts |
| 2 | Sep 22–26 | E1 runs: direct / plan+execute / auto / Faker × 5 schemas × 2 providers × 2 runs; metrics CSVs |
| 3 | Sep 29–Oct 3 | E1 analysis: stats, figures; write Sections 3–5 (method, E1 results) |
| 4 | Oct 6–10 | E2 fixtures for 3 SUTs (func/edge/neg); `[TEST DATA]` injection switch in prompts.py v1.5.0; conftest loaders; smoke |
| 5 | Oct 13–17 | E2 runs (Claude + GPT-4o, 2 runs each, 3 new arms) sharded; scoring v2 |
| 6 | Oct 20–24 | E2 analysis; Sections 6–7; threats; related work |
| 7 | Oct 27–31 | Full draft; independent number trace; Zenodo bundle v1.0.0; git tag |
| 8 | Nov 3–7 | Cover letter, IST submission package; submit |

## Folder layout (new)
```
E:\EB1A_Research\EB1_Master\06_Authorship\Paper_H_SynthData_TestDataProvisioning\
  RESEARCH_PLAN_PaperH_SynthData_2026-09-11.md   (this file)
  Experiment\   synthdata (clone of E:\Sy\testforge, tag frozen) · e1_datastudy\ · e2_raitg_data\ (links to Paper E harness)
  Article\      IST_2026-11-xx\
  Evidences\    business cases + MD5s, subject manifest, run logs index
```

## Immediate next steps (need Vijay)
1. ✅ Subject list frozen 11 Sep 2026 (Pagila v3.1.0, Chinook, Northwind, employees, dellstore2).
2. Create a fresh `.env` at `Paper_H…\Experiment\.env` with `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`
   (never paste keys in chat; never committed).
3. Confirm venue: IST first choice.
4. Approve this plan → I set up the Experiment folder, freeze subjects, and start Week 1.
