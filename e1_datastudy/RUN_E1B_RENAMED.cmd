@echo off
REM Paper H / E1b — RENAMED-SCHEMA CONTROL for the memorisation threat. Same two LLM arms as E1
REM (plan-then-execute, direct emission), both providers, ONE run, on the five schemas with every
REM table/column renamed to a synonym and the dataset name removed from the case (ddl\*_r.canonical.sql,
REM cases\*_r.txt). RESUMABLE. Keys from ..\.env. Needs node >=18, python 3 with `requests`.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "..\.env" if not exist "..\.env.example" (echo ERROR: no ..\.env found & pause & exit /b 1)
python check_keys.py || (echo ERROR: could not read both keys from ..\.env - see message above & pause & exit /b 1)
echo Keys loaded. Starting E1b runs (this window stays open; progress in RUN_E1B_LOG.txt)...
python -c "import requests" 2>nul || pip install requests
where node >nul 2>nul || (echo ERROR: node not found on PATH & pause & exit /b 1)
if not exist synthdata_pkg\node_modules\@vijaypjavvadi\synthdata\package.json (
  mkdir synthdata_pkg 2>nul
  pushd synthdata_pkg & call npm init -y >nul & call npm install @vijaypjavvadi/synthdata@1.2.2 & popd
)
set "SYNTHDATA_DIR=%~dp0synthdata_pkg\node_modules\@vijaypjavvadi\synthdata"
set LOG=%~dp0RUN_E1B_LOG.txt
echo === RUN_E1B_RENAMED %DATE% %TIME% === >> "%LOG%"
for %%P in (anthropic openai) do (
  for %%S in (chinook_r northwind_r dellstore2_r pagila_r employees_r) do (
    set "PLANOK="
    if exist "arms\plan_r\%%S_%%P_r1\log.json" findstr /c:"\"generate_rc\": 0" "arms\plan_r\%%S_%%P_r1\log.json" >nul && set "PLANOK=1"
    if not defined PLANOK (
      echo [!TIME!] plan %%S %%P run1 >> "%LOG%"
      python arm_plan.py %%S %%P 1 "arms\plan_r\%%S_%%P_r1" >> "%LOG%" 2>&1
    )
  )
)
for %%P in (anthropic openai) do (
  for %%S in (chinook_r northwind_r dellstore2_r pagila_r employees_r) do (
    echo [!TIME!] direct %%S %%P run1 >> "%LOG%"
    python arm_direct.py %%S %%P 1 "arms\direct_r\%%S_%%P_r1" >> "%LOG%" 2>&1
  )
)
echo === DONE %DATE% %TIME% === >> "%LOG%"
echo Finished. See RUN_E1B_LOG.txt. Run ZIP_ARMS.cmd and tell Claude.
pause
