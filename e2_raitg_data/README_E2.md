# Paper H — E2: provisioned test data for LLM-generated tests (Paper E harness, prompt v1.5.0)

Frozen inputs (MD5s): `FROZEN_INPUTS_MD5.txt` (ddl/, cases/), `FIXTURES_MD5.txt` (SynthData 1.2.2 output,
Claude Sonnet 4.6 plan, seed 42, profiles functional/edge/negative), `testdata/TESTDATA_MD5.txt`
(the [TEST DATA] blocks injected into the prompt, one per arm x app; httpbin has none).

Arms (conditions in `raitg/scripts/run_experiment.py`): `full` = Paper E grounded RAITG (G);
`full_dfunc` = G + functional fixture (pre-loaded at scoring); `full_dall` = G + functional (pre-loaded)
+ edge/negative rows shown as payloads; `full_dhuman` = G + the project's own fixture.
`full` with v1.5.0 is byte-identical to v1.4.0 (verified) — the Claude G runs are Paper E v5 seed1/seed2.

Run: `RUN_E2.cmd` (unpacks e2_package.zip on first run). Then `ZIP_RUNS.cmd` -> runs_snapshot.zip.
Scoring: cloud, `W/pipeline_e2.py` (v2 protocol; conftests pre-load the arm's fixture via
fixture_loader.py: flaskr init_db()/instance db, fastapi-restful pristine players.db swap,
task-manager Base.metadata.create_all()).
