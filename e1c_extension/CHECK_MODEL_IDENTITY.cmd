@echo off
REM Paper H / E1c — model-identity check: for every model identifier named in the manuscript, query the provider's
REM model listing and a one-token completion, record the identifier the provider echoes back, and compare with the
REM E1c run logs. Keys from ..\.env (never printed). Writes results\model_identity_check.json. Double-click.
cd /d "%~dp0"
python -c "import requests" 2>nul || pip install requests
python model_identity_check.py
pause
