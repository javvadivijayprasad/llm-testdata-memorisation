# Paper H artifact v1.2.1 — "Memorised, Not Generated: Verbatim Recall of Published Fixtures in LLM-Generated Test Data, Measured Across Five Models and Eight Public Schemas"

Zenodo: v1.2.1 https://doi.org/10.5281/zenodo.23173140 (5 Oct 2026; identical to v1.2.0, https://doi.org/10.5281/zenodo.22939799, except that the paper, README and CITATION.cff carry the final DOI); v1.1.0 https://doi.org/10.5281/zenodo.22939052 (24 Sep 2026). Manuscript for Empirical Software Engineering.

Vijay Prasad Javvadi, Independent Researcher, Plainsboro, NJ, USA (ORCID 0009-0004-1192-6906). v1.0.0 frozen 13 Sep 2026; v1.1.0 (E2c arm, regenerated cell tables, journal manuscript) 24 Sep 2026; v1.2.0 (E1c: copy rate across five models and eight schemas, Oracle HR fixture editions, restructured manuscript) and v1.2.1 (final DOI references) 5 Oct 2026.

Every number in the manuscript (`article/paperH_emse.tex`) is produced by a script in this bundle from the
files in this bundle; `article/NUMBER_TRACE.md` maps each table and headline number to its source file.
`MD5SUMS.txt` lists every file.

## Layout
- `RESEARCH_PLAN_PaperH_SynthData_2026-09-11.md` — the pre-registered plan (hypotheses, arms, metrics) written before any run.
- `e1_datastudy/` — E1 and E1b.
  - `ddl/` canonical DDLs (`<schema>.canonical.sql`) and renamed DDLs (`<schema>_r.canonical.sql`); `cases/` frozen business cases (+ `cases_MD5.txt`); `row_targets.json`; `rename_maps/`.
  - scripts: `canon_ddl.py` (catalogue → canonical DDL), `arm_direct.py`, `arm_plan.py`, `arm_faker.py`, `rename_schema.py`, `score_load.py` (PostgreSQL row-by-row scorer), `metrics_fidelity.py`.
  - `arms/pc/{plan,direct,plan_profiles}/`, `arms/pc_r/{plan_r,direct_r}/` — every LLM cell's output (CSV rows, `plan.yaml`, `plan_raw.txt`, `log.json` with tokens/latency); `arms/auto_v122*`, `arms/faker`.
  - `scores/`, `metrics/` — per-cell JSON; `results/E1_cells.csv`, `results/E1b_renamed_vs_original.csv`.
  - `STATUS_Week1..3` — the running record incl. the SynthData defect trail; `RUN_E1_LOG.txt`, `RUN_E1B_LOG.txt`.
- `e1c_extension/` — E1c (added in v1.2.0): the copy-rate extension to five models (Claude Sonnet 4.6 and 5.5, GPT-4o, GPT-5.6, Qwen3-235B via OpenRouter) and eight schemas (the five above plus ClassicModels, Oracle HR, BikeStores), direct arm only.
  - `README_E1C.md` (design, steps, budget), `SUBJECT_MANIFEST_E1C.md` (provenance and conversion of the three new subjects), `subjects_pg/` (their PostgreSQL ports, plus the 2015-2019 edition of the Oracle HR data).
  - scripts: `arm_direct_e1c.py` (the E1 direct arm with the model as an argument and an OpenAI-compatible provider; logs tokens, latency, stop reason, serving host and sampling settings per call), `plan_cells.py`, `check_models.py`, `RUN_E1C.cmd`, `copy_rate_e1c.py` (imports the E1 metric code unchanged), `copy_rate_stats_e1c.py`, `hr_editions.py`, `model_identity_check.py` (+ `CHECK_MODEL_IDENTITY.cmd`: re-queries each provider's model listing and a one-token completion for every identifier the paper names and compares with the run logs; writes `results/model_identity_check.json`).
  - `arms/direct/<schema>_<model>_r1/` — every new cell's CSV rows and `log.json`; `RUN_E1C_LOG.txt`.
  - `results/E1c_copy_rate.csv` (all 50 cells incl. the E1 ones re-scored), `results/E1c_stats.txt` (Tables 4 and 5 of the manuscript), `results/hr_editions.json`, `results/copy_rate/<cell>.json` (per-table).
  - The three new schemas' canonical DDLs, cases, row targets and human caches are in `e1_datastudy/` beside the E1 subjects (`human_cache/hr_v19/` is the 2019 edition).
- `e2_raitg_data/` — E2 (exploratory in the v1.2.0 manuscript).
  - `ddl/`, `cases/`, `fixtures/` (SynthData plans + CSVs per profile), `testdata/` (the [TEST DATA] prompt blocks), MD5 files.
  - `raitg/scripts/` — the Paper E pipeline with prompt v1.5.0 (`prompts.py`) and the three conditions (`run_experiment.py`); `raitg/datasets/`.
  - `runs/<provider>_r<n>/runs/*.json` — every generated test suite with telemetry (Claude G runs are the Paper E v5 logs, see below).
  - `pipeline_e2.py`, `fixture_loader.py` — scoring harness (wraps the Paper E v2 pipeline); `e2_analysis.py`.
  - `results/E2_cells.csv`, `results/E2_pairwise_vs_G.csv`, `results/scoring/<label>/` (per-mutant kill CSVs, known-good lists, pre-screen records, extraction manifests).
  - `STATUS_Week4`, `STATUS_Week5`, `RUN_E2_LOG.txt`.
- `article/` — manuscript source, `references.bib`, `figures/`, `make_figures.py`, `NUMBER_TRACE.md`.

## External inputs (not redistributed here)
- Human fixtures: Pagila v3.1.0 (BSD), Chinook 7f67772 (MIT), Northwind pthom/northwind_psql cd0ef28 (MIT),
  datacharmer/test_db e324b56 (CC BY-SA 3.0), Dell DVD Store 2 via postgresDBSamples 2bdc953; for E1c, ClassicModels (mysqltutorial.org dump, mirrored at bklogic/example-data-access-service 241750c), Oracle HR (oracle-samples/db-sample-schemas 6660bad, and tag v19.2 for the 2015-2019 edition), BikeStores (sqlservertutorial.net scripts, mirrored at ant-analytics/mssql) — see `e1c_extension/SUBJECT_MANIFEST_E1C.md`; checksums in
  `e1_datastudy/STATUS_Week1` / the subject manifest. `score_load.py` and `metrics_fidelity.py` expect them loaded
  as `<schema>_canon` PostgreSQL databases (see STATUS_Week1 for the load procedure).
- SynthData 1.2.2, **exactly this version**: `npm install @vijaypjavvadi/synthdata@1.2.2`; checksums in `e1_datastudy/synthdata_v1.2.2_MD5.txt`. The study froze 1.2.2 (npm publish 2026-09-11 18:01 UTC). Later releases do not reproduce the paper: 1.2.3 (same day, 21:35 UTC) fixes defects #6 (`expr` date arithmetic) and #7 (`fk` on a primary key), so the plan-arm load rates and the defect trail differ; a release after 1.2.3 introduces per-table seed streams, so `--seed 42` output differs from 1.2.x. To reproduce the plan and auto arms, install 1.2.2 and verify the MD5s first.
- Paper E harness (SUT snapshots, 293 frozen mutants, v2 scoring environment): Zenodo 10.5281/zenodo.20285103 (v5.0.0).

## Reproduce
1. E1 scoring: `score_load.py <schema> <csv_dir> <out.json>`; fidelity: `metrics_fidelity.py <schema> <csv_dir> <out.json>`.
2. E1/E1b LLM arms (needs API keys in `../.env`): `RUN_E1_LLM_ARMS_v4.cmd`, `RUN_E1B_RENAMED.cmd` (Windows) or the `arm_*.py` scripts directly.
3. E2 generation: `run_e2.py`; scoring: `pipeline_e2.py extract|kg|score|summarize <label> ...` inside the Paper E v2 environment; analysis: `e2_analysis.py`.
4. E1c: `python e1c_extension/copy_rate_e1c.py` then `python e1c_extension/copy_rate_stats_e1c.py` and `python e1c_extension/hr_editions.py` (the human caches are in `e1_datastudy/human_cache/`); regenerating the cells needs API keys (`RUN_E1C.cmd`).
5. Figures: `article/make_figures.py`, `article/figures/make_diagrams.py`, `article/figures/make_overview_v4.py`.


## Changes in v1.1.0 (September 2026)
- Manuscript `article/paperH_emse.tex` (Empirical Software Engineering); memorisation control is the headline; effect sizes, Holm correction, run-to-run and renaming-cost references added. All statistics: `article/stats_paper.py`; trace: `article/NUMBER_TRACE.md`.
- `e1_datastudy/build_cells.py` regenerates `results/E1_cells.csv` and `results/E1b_renamed_vs_original.csv` from `scores/`, `metrics/` and `arms/*/log.json` (the v1.0.0 tables were built by inline code). Two new columns: `js_declared_median`, `js_freetext_median`.
- `e1_datastudy/metrics_fidelity.py`: boolean spellings normalised (psql `t/f` vs `true/false`; previously every boolean column scored JS 1.0 by representation); all `metrics/` regenerated with `rebuild_metrics.sh`. No schema-level median in the paper changed.
- `e2_raitg_data/`: E2c arm `full_dstate` (functional fixture + explicit database-state contract; `build_testdata_state.py`, `testdata/state/`, `RUN_E2C.cmd`; prompt v1.5.1) with its pre-statement `STATUS_Week6_E2c_prestatement_2026-09-17.md`. Run 1 (Claude Sonnet 4.6, 172 requirements) and its scoring are in `runs/anthropic_r1/runs/full_dstate_*.json` and `results/scoring/e2_dstate_sonnet_r1/`; `e2_analysis.py` prints the E2c block (usable yield 1,207/1,294 = 93.3 %; 160 mutants killed vs 161 for G, McNemar p = 1.0, bootstrap CI [-6, +3]) into `results/E2_analysis_output.txt`. `run_e2.py` docstring escape fixed (no SyntaxWarning).
