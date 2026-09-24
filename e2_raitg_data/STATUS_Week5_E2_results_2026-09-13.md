# Paper H — E2 results (13 Sep 2026): provisioned test data and LLM-generated tests (RQ4, RQ5)

All numbers from `results/E2_cells.csv`, `results/E2_pairwise_vs_G.csv` and the per-mutant score CSVs in
`results/E2_scoring_2026-09-13.zip` (`scoring/<label>/<cond>__<sut>.csv`, kg stats, per-unit pre-screen
records, extraction manifests, driver log). Generation on Vijay's PC 12 Sep 12:37–17:30 (`RUN_E2_LOG.txt`,
`runs_snapshot.zip`); scoring in the cloud Paper E v2 environment through `pipeline_e2.py`.

## Design as run
- 172 requirements, 4 SUTs, 293 frozen mutants (Paper E, MD5-verified). Arms: G (grounded RAITG, prompt
  v1.4.0 == v1.5.0 without the block), G+D-func, G+D-all, G+D-human (prompt v1.5.0; see
  STATUS_Week4). Claude Sonnet 4.6 and GPT-4o, two independent runs each; the Claude G runs are the
  Paper E v5 seed-1/seed-2 generation logs, GPT-4o G is two new runs. 16 labels scored.
- Scoring harness = Paper E v2 (same shims, kill criterion, `-x --timeout=30`, 90 s per mutant run) plus
  (a) per-arm fixture provisioning in the conftests (flaskr `init_db()` wrapper and instance db,
  fastapi-restful pristine `players.db` replaced, task-manager `Base.metadata.create_all()` wrapper),
  (b) memoised low-cost password hashing (the default 260k-round hash made the flaskr suite exceed the
  90 s limit, which the scorer counts as a kill), and (c) a per-unit pre-screen before the known-good
  filter: each unit runs alone (30 s cap, the same limit v2 applies per test function); units that
  cannot pass alone are excluded and recorded. (c) was forced by a GPT-4o flaskr unit calling
  `init_db_command()` at module level (SystemExit inside pytest collection → INTERNALERROR → every
  flaskr mutant run exited 3 → 0 kills for all 130 units) and by script-style units that `sleep(60)`.
  **Every arm, including G for both providers, is scored under this one harness** (the Claude G logs
  were re-scored: 161/169 here vs 160/159 under plain v2; the difference is fastapi-restful run 2, where
  three units that pass only after an earlier unit has populated the SUT's 10-minute response cache were
  excluded — order-dependent units, not self-contained). Paper E's archived numbers are unchanged.

## RQ4 — mutants killed / 293 (usable yield = known-good units / emitted units)

| arm | Claude r1 | Claude r2 | GPT-4o r1 | GPT-4o r2 |
|---|---|---|---|---|
| G | 161 (88 %) | 169 (89 %) | 106 (52 %) | 109 (59 %) |
| G + SynthData functional fixture | 158 (85 %) | 167 (84 %) | 115 (53 %) | 109 (49 %) |
| G + functional + edge/negative payloads | 170 (83 %) | 167 (85 %) | 106 (50 %) | 113 (48 %) |
| G + project's own fixture | 145 (87 %) | 167 (81 %) | 109 (51 %) | 102 (48 %) |

Paired vs G, same provider and run (McNemar exact; bootstrap 95 % CI of Δ, 1,000 resamples, seed 42):
- Claude: func −3 (p = 0.51) / −2 (p = 0.75); all **+9 (p = 0.022, CI +2…+16)** / −2 (p = 0.73);
  human **−16 (p < 0.001, CI −25…−8)** / −2 (p = 0.82).
- GPT-4o: func +9 (p = 0.19) / 0; all 0 / +4 (p = 0.57); human +3 / −7 (p = 0.19). Nothing significant;
  discordant pairs 14–23 per comparison, i.e. arm-to-arm noise of ±10 mutants.

Per SUT (G / func / all / human): Claude httpbin 76/79/77/78 and 76/79/77/83 — the no-database
control moves by ≤ +7 and in both directions; fastapi-restful 16/16/25/16 (r1) and 25/25/25/25 (r2);
flaskr 31/31/31/15 and 31/31/31/21; task-manager 38/32/37/36 and 37/32/34/38. GPT-4o: no SUT moves
outside ±5 except flaskr r1 func (14→26).

## Findings
1. **The pre-registered hypothesis is rejected.** A provisioned fixture does not raise usable yield: for
   Claude it *lowers* it (88–89 % → 83–85 %), most on task-manager (known-good 241/254 → 176/275): with
   20 pre-loaded tasks, generated tests that create one task and assert a count of 1, or that assume
   id 1 is theirs, fail on clean source. Provisioned rows conflict with the empty-database assumption
   the generator carries, even when the prompt states the pre-loaded rows explicitly.
2. **No arm reliably raises the kill rate.** The one significant positive (Claude, edge/negative payloads,
   run 1, +9, driven by fastapi-restful 16→25 — validation-path mutants, as pre-registered) does not
   replicate in run 2, where the G baseline itself already kills 25 on that SUT. The one significant
   negative (Claude, project fixture, run 1, −16) is a flaskr collapse (31→15; known-good 113/163) that
   also does not replicate (21 in run 2). Two runs at temperature 0 are not enough to separate a
   ±10-mutant arm effect from run-to-run variation on this harness; the paper reports both runs.
3. **GPT-4o is a different regime**: ~3 tests per requirement (516 units vs ~1,300), about half unusable,
   4–5× more repair passes, 102–115 kills whatever the arm.
4. **Cost**: the functional block adds 14 % input tokens, the full block 40 % (Claude 1.24 M → 1.41 M /
   1.74 M per condition-run); output tokens and repairs unchanged. E2 API spend ≈ $80 Claude + $34 GPT-4o.
5. httpbin (no database, no block) behaves as a control should: Δ within ±7 in every arm.

## What this means for the paper
E1 stands on its own (validity parity, 30× cost advantage, memorisation-corrected fidelity). E2's
contribution is negative and useful: constraint-valid fixtures neither help nor hurt mutation kill rate
reliably, they *reduce* usable yield by breaking empty-database assumptions, and boundary/negative
payloads show a validation-path effect for the stronger model in one run only. Report as "no reliable
downstream effect at n = 172 × 2 runs; effect sizes ≤ 10/293", with the yield finding as the actionable
result (a provisioning tool should ship an *empty-plus-fixture* switch, or the generator must be told
which ids are free).

## Threats / notes for the write-up
- Harness hardening (b, c) was applied uniformly after being discovered; both scorings of the Claude G
  arm are on record. Timeout-kills: none in any E2 chunk (checked).
- The SynthData fixtures are semantically weak (faker names, mismatched position/abbreviation) — the
  arm tests provisioning, not fixture realism; the project-fixture arm is the realism control.
- Cross-provider comparison is confounded by GPT-4o's lower unit yield; RQ5 is answered as "the null
  holds for both".

## SynthData defects to report (cumulative): #6 expr dates, #7 fk on PK, #8 self-fk NOT NULL, #9 YAML
parser strictness (multi-line flow sequence).
