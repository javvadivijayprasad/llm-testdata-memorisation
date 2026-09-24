# Paper H — E2 setup status (12 Sep 2026)

Design (approved by Vijay 12 Sep): baseline G = Paper E grounded RAITG (`full`, prompt v1.4.0; Claude
runs = Paper E v5 seed1/seed2 logs; GPT-4o = 2 new runs). Three new arms, both providers, 2 runs each:
`full_dfunc` (SynthData functional fixture, pre-loaded in the SUT DB), `full_dall` (functional pre-loaded +
edge/negative rows shown as payloads to try — same DB state as dfunc, so dall−dfunc isolates the
boundary/negative information), `full_dhuman` (project's own fixture: flaskr data.sql, fastapi-restful
players.db; task-manager ships none → empty table, identical DB state to G). httpbin: no block, no DB →
negative control. Verification/repair ON in all arms as in `full`.

## Built and verified today
- DDL + business cases for the 3 DB SUTs (from schema.sql / SQLAlchemy model / players.db catalog and the
  projects' READMEs + REST examples), frozen: `FROZEN_INPUTS_MD5.txt`.
- Fixtures: SynthData 1.2.2, Claude Sonnet 4.6 plan (temperature 0, SynthData system prompt), seed 42,
  profiles functional/edge/negative; `FIXTURES_MD5.txt`. Row counts: flaskr user 5 / post 20; players 26;
  tasks 20. Task-manager plan: attempt 1 and 2 both rejected by SynthData's YAML parser (multi-line flow
  sequence; PyYAML accepts it) → **SynthData defect #9 (parser strictness)**; the attempt-2 plan was
  re-serialised through PyYAML (values unchanged, recorded in `fixtures/fastapi_task_manager/log.json`).
  flaskr convention: fixture `password` is plain text; the loader stores generate_password_hash(plain).
- Every fixture validated through the SUT itself (`validate_fixtures.py`): flaskr 5/5 logins succeed and
  20 posts render; players GET /players returns 26 and lookup by squad number works; tasks GET returns
  20 with the completed filter working; human fixtures likewise (2/2 logins, 26 players, 0 tasks).
- Prompt v1.5.0 (`raitg/scripts/prompts.py`): [TEST DATA] element appended to [CONTEXT] for the three
  arms; `full` prompt byte-identical to v1.4.0 (verified on flaskr R-FLASKR-001). Block sizes: dfunc
  2.2–4.4k chars, dall 7–15k, dhuman 0.3–4.5k (httpbin 0). MD5s in `testdata/TESTDATA_MD5.txt`.
- Scoring: `W/pipeline_e2.py` wraps pipeline_v2 (protocol unchanged) and makes the per-arm conftests
  provision the fixture wherever the database is initialised: flaskr `init_db()` / instance db wrapper,
  fastapi-restful pristine `players.db` replaced, task-manager `Base.metadata.create_all()` wrapper.
  Smoke (Claude, 1 requirement per DB SUT, dfunc): 29 units, 26 known-good; a unit asserting all 20
  fixture post titles on a database it created itself passes only with the wrapper — the reason for it.
- PC package `e2_package.zip` + `RUN_E2.cmd` (parallel per app, resumable) + `ZIP_RUNS.cmd`.

## Cost / time (from Paper E v5 telemetry: 1.24 M in + 0.58 M out tokens per condition-run)
≈ $12 Claude / $9 GPT-4o per condition-run; 12 new arm-runs + 2 GPT-4o baselines ≈ $150; ~1 h per
condition-run with 4 parallel processes → ~14 h of PC time in total (resumable, can be split).

## Open
- SynthData defects to report: #6, #7, #8 (E1/E1b) and #9 (YAML parser strictness).
