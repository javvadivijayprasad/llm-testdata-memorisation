@echo off
REM Paper H / E2c (17 Sep 2026) — one Claude Sonnet 4.6 run of the full_dstate arm (functional fixture +
REM DATABASE STATE CONTRACT). Resumable. Output: runs\anthropic_r1\runs\full_dstate_R-*.json (172 files).
REM Cost estimate ~$40. Afterwards run ZIP_RUNS_v2.cmd and tell Claude.
cd /d "%~dp0"
if not exist raitg\scripts\run_experiment.py (
  echo raitg not unpacked - run RUN_E2.cmd first, then apply e2c_patch.zip
  pause & exit /b 1
)
if not exist testdata\state\flaskr.txt (
  echo testdata\state missing - extract e2c_patch.zip over this folder first
  pause & exit /b 1
)
python -c "import anthropic" 2>nul || pip install anthropic
python run_e2.py anthropic 1 full_dstate
echo Finished. Run ZIP_RUNS_v2.cmd and tell Claude.
pause
