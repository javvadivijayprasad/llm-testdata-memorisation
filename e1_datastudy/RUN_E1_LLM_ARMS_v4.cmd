@echo off
REM Paper H / E1 — runs the two LLM arms (plan-then-execute, direct emission) for all five schemas,
REM both providers (Claude Sonnet 4.6, GPT-4o), two independent runs each. RESUMABLE: rerun this
REM file after any interruption; completed tables/plans are skipped. Keys are read from ..\.env
REM (ANTHROPIC_API_KEY, OPENAI_API_KEY). Needs: node (>=18), python 3 with `requests`.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
if not exist "..\.env" if not exist "..\.env.example" (echo ERROR: no ..\.env found & pause & exit /b 1)
python check_keys.py || (echo ERROR: could not read both keys from ..\.env - see message above & pause & exit /b 1)
echo Keys loaded. Starting runs (this window stays open; progress in RUN_E1_LOG.txt)...
python -c "import requests" 2>nul || pip install requests
where node >nul 2>nul || (echo ERROR: node not found on PATH & pause & exit /b 1)
if not exist synthdata_pkg\node_modules\@vijaypjavvadi\synthdata\package.json (
  mkdir synthdata_pkg 2>nul
  pushd synthdata_pkg & call npm init -y >nul & call npm install @vijaypjavvadi/synthdata@1.2.2 & popd
)
set "SYNTHDATA_DIR=%~dp0synthdata_pkg\node_modules\@vijaypjavvadi\synthdata"
set LOG=%~dp0RUN_E1_LOG.txt
echo === RUN_E1_LLM_ARMS %DATE% %TIME% === >> "%LOG%"
for %%R in (1 2) do (
  for %%P in (anthropic openai) do (
    for %%S in (chinook northwind dellstore2 pagila employees) do (
      set "PLANOK="
      if exist "arms\plan\%%S_%%P_r%%R\log.json" findstr /c:"\"generate_rc\": 0" "arms\plan\%%S_%%P_r%%R\log.json" >nul && set "PLANOK=1"
      if not defined PLANOK (
        echo [!TIME!] plan %%S %%P run%%R >> "%LOG%"
        python arm_plan.py %%S %%P %%R "arms\plan\%%S_%%P_r%%R" >> "%LOG%" 2>&1
      )
    )
  )
)
for %%R in (1 2) do (
  for %%P in (anthropic openai) do (
    for %%S in (chinook northwind dellstore2 pagila employees) do (
      echo [!TIME!] direct %%S %%P run%%R >> "%LOG%"
      python arm_direct.py %%S %%P %%R "arms\direct\%%S_%%P_r%%R" >> "%LOG%" 2>&1
    )
  )
)
echo === DONE %DATE% %TIME% === >> "%LOG%"
echo Finished. See RUN_E1_LOG.txt. Tell Claude to collect arms\ for scoring.
pause
