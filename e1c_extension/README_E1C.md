# Paper H — E1c: copy-rate extension for the EMSE revision (Boni's points 3 and 4), 4 Oct 2026

## What this adds and why
Boni's review: the copy-rate claim rests on five schemas, two models and two runs (p = 0.016 with a CI touching zero), and GPT-4o will look old by review time. Copy rate needs only the direct arm, so the cheap fix is more pairs: three more public schemas with human fixtures, the current model from each provider, and one open-weight model. Nothing in E1 is rerun or changed; E1c is a new folder with its own cells, and `copy_rate_e1c.py` scores old and new cells with the unchanged metric code from `e1_datastudy/copy_rate.py`.

Design is identical to E1's direct arm: same system prompt, chunking (200 rows), parent-key context, temperature 0, row targets min(human, 500), seed 20260911 + run. Only the model and the schema vary.

## New schemas (public datasets with human fixtures; drafts of the business cases are in cases/, written from each dataset's documentation, not its data — check them against the README of each before registering)
| subject | source | why | notes |
|---|---|---|---|
| classicmodels | mysqltutorial.org sample database (MySQL dump) | invented company/person names, scale-model products; widely copied in tutorials, so a plausible memorisation target | load into Postgres with pgloader or a converted dump; 8 tables |
| hr | Oracle HR sample schema (github.com/oracle-samples/db-sample-schemas) | invented employee names, 107 employees; the canonical teaching schema | Postgres ports exist; 7 tables |
| bikestores | sqlservertutorial.net BikeStores sample (SQL Server) | invented customers and staff, real bike product names (a mixed case worth having) | load with a converted script; 9 tables across production/sales (flatten to public, prefix table names if they clash) |
AdventureWorks is the alternative to bikestores if its Postgres port loads cleanly, but it is large (70 tables) and would need a subset, which weakens the "whole schema" design; I left it out.

## What is already done (cloud workspace, 4 Oct 2026)
The three datasets are loaded into the same PostgreSQL 16 instance that holds the five E1 subjects, with all constraints on, and each reloads cleanly into its canonical DDL (classicmodels 3,864 rows, hr 216, bikestores 9,071). Sources and conversions are in `subjects_pg/` (schema + data scripts for each) and recorded in `SUBJECT_MANIFEST_E1C.md`. The canonical DDLs, row targets, human caches and case MD5s are written into `..\e1_datastudy\` next to the E1 subjects (`ddl/`, `cases/`, `human_cache/`, `row_targets.json`, `cases_MD5.txt`).

## Steps on your PC (Windows, Python 3 with requests)
1. Read the three business cases in `..\e1_datastudy\cases\{classicmodels,hr,bikestores}.txt` against each dataset's own documentation. If anything needs changing, send me the correction rather than editing the file, so that the MD5 in `cases_MD5.txt` and the cloud copy stay in step.
2. Fill in `models_e1c.json`: the two NEWER model ids (the current model of each provider on the day you run) and the open-weight model id; for the open-weight model add `OPENAI_COMPAT_BASE_URL=` and `OPENAI_COMPAT_API_KEY=` to `..\.env` (any OpenAI-compatible host). Keys only in `.env`, never in chat.
3. `python check_models.py`, then double-click `RUN_E1C.cmd`. Resumable. Progress in `RUN_E1C_LOG.txt`.
4. When it says DONE, tell me; I collect `arms\` and score it here with `copy_rate_e1c.py` (the five E1 human caches live in the cloud workspace), rerun the statistics and update the paper.

## Cell count and cost
New schemas × 5 models × 2 runs = 30 cells; original five × 3 new models × 2 runs = 30 cells; 60 direct-arm cells in all. E1 cost about US$5 per schema-run for Claude and US$4 for GPT-4o; the new schemas are chinook-sized or smaller. Upper estimate US$250–300 for the two commercial providers plus the open-weight host's rate. To halve it, set run 2 aside: edit `for run in (1, 2)` in `plan_cells.py` to `(1,)` and add run 2 later if the budget allows; the paper would then have two runs only where E1 already does.

## Renamed-schema control (E1b) for the new subjects
Not included here. `e1_datastudy\rename_schema.py` carries a word map for the five E1 subjects; extending it to the three new ones is a short edit once the cases are final, and then `schemas_e1c.json` gets the `_r` entries. Worth doing, because the renamed contrast is the one Boni flagged as p = 0.30.

## What goes into the paper
A copy-rate table with schemas as rows and models as columns (exact_text, near90, overlap), the paired analysis repeated on 8 schemas × 5 models, and the "future work: open-weight model" sentence replaced by a result. The E1 cells are unchanged, so every number already in NUMBER_TRACE stays valid.
