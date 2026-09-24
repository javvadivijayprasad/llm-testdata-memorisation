# Paper H — E2c: the state-contract arm (pre-statement, 17 Sep 2026, written BEFORE the run)

## Why
E2 rejected the advance hypothesis: pre-loading a constraint-valid fixture lowered the usable share of Claude-generated tests (88–89 % → 83–85 %), most on the task manager (known-good 241/254 → 176/275), because generated tests create one row and assert a count of one, or assume their row has id 1. The `[TEST DATA]` block listed the rows and their ids, but did not say what that implies for assertions. Draft 2 of the manuscript says: "Whether a stronger statement of the database state in the prompt removes the conflict is the natural next experiment; the present data show only that listing the rows does not." E2c is that experiment. A reviewer will otherwise say the yield loss is a prompt-engineering artefact and the paper's practical conclusion (an empty-plus-fixture contract) is untested.

## Design
- New condition `full_dstate` (prompt v1.5.1; `raitg/scripts/run_experiment.py`, `prompts.py` accept arm `state`; all other arms' prompt text unchanged).
- Block = the frozen `func` block byte for byte + a `[DATABASE STATE CONTRACT]` (built by `build_testdata_state.py`; MD5s appended to `testdata/TESTDATA_MD5.txt`): the tables are never empty; ids 1..N are taken; the first row a test creates gets id N+1; count assertions must be relative to N; use listed rows for existing-row tests; delete through the API if emptiness is needed; (fastapi-restful) squad numbers 1–26 taken, use ≥27, ten-minute list cache.
- Database state at scoring = exactly the `func` arm's (pipeline_e2.py `arm_of` maps `dstate` → functional fixture). Only the information given to the model differs from `full_dfunc`.
- One run, Claude Sonnet 4.6, 172 requirements, 4 apps (httpbin has no block: control). `RUN_E2C.cmd` on the PC (~$40). Scored under the identical E2 harness (pre-screen, memoised hashes) as every other arm.

## Hypotheses (stated in advance)
- H-E2c-1 (yield): usable yield of `full_dstate` returns to the G level, ≥ 88 % aggregate, and task-manager known-good ≥ 90 % of emitted (G: 241/254 = 95 %; dfunc: 176/275 = 64 %).
- H-E2c-2 (kills): mutants killed within ±10 of the run-1 G baseline (161); no claim of a kill-rate gain.
- H-E2c-3 (control): httpbin within ±7 of G.
- Interpretation rules: if H-E2c-1 holds, the paper reports that the yield loss is a fixture-contract problem solvable in the prompt, and the practical recommendation becomes evidence. If yield stays ≤ 85 %, the empty-database assumption is robust to instruction and the recommendation shifts to provisioning tools (empty-plus-fixture mode). Either result is reported with the run-1 dfunc arm side by side; no second E2c run is planned unless the first is within 3 points of the threshold.

## Steps for Vijay
1. Extract `e2c_patch.zip` over `Paper_H…\Experiment\e2_raitg_data\` (overwrites `raitg\scripts\run_experiment.py`, `raitg\scripts\prompts.py`, `run_e2.py`, `pipeline_e2.py`; adds `testdata\state\`, `RUN_E2C.cmd`, `build_testdata_state.py`; updates `testdata\TESTDATA_MD5.txt`).
2. Run `RUN_E2C.cmd`. Expect 172 files `runs\anthropic_r1\runs\full_dstate_R-*.json`; the log is `RUN_E2_LOG.txt`.
3. Run `ZIP_RUNS_v2.cmd` and tell Claude; scoring is in the cloud (label `e2c_dstate_sonnet_r1`).

## Optional (decide after E2c): run 3 of G/dfunc/dall/dhuman for Claude (~$60) to tighten the ±10-mutant variance claim.
