@echo off
REM Paper H / E1c — copy-rate extension: DIRECT arm only, every model in models_e1c.json x every schema in
REM schemas_e1c.json x 2 runs, except (E1 model x E1 schema) which E1 already has. RESUMABLE: rerun after any
REM interruption; completed tables are skipped. Keys from ..\.env. Needs python 3 with requests.
REM Order: new schemas first (all models), then new models on the original five. Progress in RUN_E1C_LOG.txt.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
python -c "import requests" 2>nul || pip install requests
python check_models.py || (pause & exit /b 1)
set LOG=%~dp0RUN_E1C_LOG.txt
echo === RUN_E1C %DATE% %TIME% === >> "%LOG%"
for /f "usebackq tokens=1-5" %%A in (`python plan_cells.py`) do (
  REM %%A subject  %%B provider  %%C model  %%D tag  %%E run
  echo [!TIME!] direct %%A %%D run%%E >> "%LOG%"
  python arm_direct_e1c.py %%A %%B %%C %%E "arms\direct\%%A_%%D_r%%E" >> "%LOG%" 2>&1
)
echo === DONE %DATE% %TIME% === >> "%LOG%"
echo Finished. See RUN_E1C_LOG.txt. Then run: python copy_rate_e1c.py
pause
