# Paper H artifact v1.1.0 — "Remembered, Not Generated: A Renamed-Schema Control for LLM-Provisioned Test Data, the Cost of Planning Instead of Emitting, and What Valid Data Does Not Do for LLM-Generated Tests"

Zenodo: https://doi.org/10.5281/zenodo.22939052 (v1.1.0, 24 Sep 2026). Manuscript submitted to the Journal of Systems and Software.

Vijay Prasad Javvadi, Independent Researcher, Plainsboro, NJ, USA (ORCID 0009-0004-1192-6906). v1.0.0 frozen 13 Sep 2026; v1.1.0 (E2c arm, regenerated cell tables, JSS manuscript) 24 Sep 2026.

Every number in the manuscript (`article/paperH_jss.tex`) is produced by a script in this bundle from the
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
- `e2_raitg_data/` — E2.
  - `ddl/`, `cases/`, `fixtures/` (SynthData plans + CSVs per profile), `testdata/` (the [TEST DATA] prompt blocks), MD5 files.
  - `raitg/scripts/` — the Paper E pipeline with prompt v1.5.0 (`prompts.py`) and the three conditions (`run_experiment.py`); `raitg/datasets/`.
  - `runs/<provider>_r<n>/runs/*.json` — every generated test suite with telemetry (Claude G runs are the Paper E v5 logs, see below).
  - `pipeline_e2.py`, `fixture_loader.py` — scoring harness (wraps the Paper E v2 pipeline); `e2_analysis.py`.
  - `results/E2_cells.csv`, `results/E2_pairwise_vs_G.csv`, `results/scoring/<label>/` (per-mutant kill CSVs, known-good lists, pre-screen records, extraction manifests).
  - `STATUS_Week4`, `STATUS_Week5`, `RUN_E2_LOG.txt`.
- `article/` — manuscript source, `references.bib`, `figures/`, `make_figures.py`, `NUMBER_TRACE.md`.

## External inputs (not redistributed here)
- Human fixtures: Pagila v3.1.0 (BSD), Chinook 7f67772 (MIT), Northwind pthom/northwind_psql cd0ef28 (MIT),
  datacharmer/test_db e324b56 (CC BY-SA 3.0), Dell DVD Store 2 via postgresDBSamples 2bdc953; checksums in
  `e1_datastudy/STATUS_Week1` / the subject manifest. `score_load.py` and `metrics_fidelity.py` expect them loaded
  as `<schema>_canon` PostgreSQL databases (see STATUS_Week1 for the load procedure).
- SynthData 1.2.2: `npm install @vijaypjavvadi/synthdata@1.2.2`; checksums in `e1_datastudy/synthdata_v1.2.2_MD5.txt`.
- Paper E harness (SUT snapshots, 293 frozen mutants, v2 scoring environment): Zenodo 10.5281/zenodo.20285103 (v5.0.0).

## Reproduce
1. E1 scoring: `score_load.py <schema> <csv_dir> <out.json>`; fidelity: `metrics_fidelity.py <schema> <csv_dir> <out.json>`.
2. E1/E1b LLM arms (needs API keys in `../.env`): `RUN_E1_LLM_ARMS_v4.cmd`, `RUN_E1B_RENAMED.cmd` (Windows) or the `arm_*.py` scripts directly.
3. E2 generation: `run_e2.py`; scoring: `pipeline_e2.py extract|kg|score|summarize <label> ...` inside the Paper E v2 environment; analysis: `e2_analysis.py`.
4. Figures: `article/make_figures.py`.


## Changes in v1.1.0 (September 2026)
- Manuscript retargeted to the Journal of Systems and Software (`article/paperH_jss.tex`); memorisation control is the headline; effect sizes, Holm correction, run-to-run and renaming-cost references added. All statistics: `article/stats_paper.py`; trace: `article/NUMBER_TRACE.md`.
- `e1_datastudy/build_cells.py` regenerates `results/E1_cells.csv` and `results/E1b_renamed_vs_original.csv` from `scores/`, `metrics/` and `arms/*/log.json` (the v1.0.0 tables were built by inline code). Two new columns: `js_declared_median`, `js_freetext_median`.
- `e1_datastudy/metrics_fidelity.py`: boolean spellings normalised (psql `t/f` vs `true/false`; previously every boolean column scored JS 1.0 by representation); all `metrics/` regenerated with `rebuild_metrics.sh`. No schema-level median in the paper changed.
- `e2_raitg_data/`: E2c arm `full_dstate` (functional fixture + explicit database-state contract; `build_testdata_state.py`, `testdata/state/`, `RUN_E2C.cmd`; prompt v1.5.1) with its pre-statement `STATUS_Week6_E2c_prestatement_2026-09-17.md`. Run 1 (Claude Sonnet 4.6, 172 requirements) and its scoring are in `runs/anthropic_r1/runs/full_dstate_*.json` and `results/scoring/e2_dstate_sonnet_r1/`; `e2_analysis.py` prints the E2c block (usable yield 1,207/1,294 = 93.3 %; 160 mutants killed vs 161 for G, McNemar p = 1.0, bootstrap CI [-6, +3]) into `results/E2_analysis_output.txt`. `run_e2.py` docstring escape fixed (no SyntaxWarning).
