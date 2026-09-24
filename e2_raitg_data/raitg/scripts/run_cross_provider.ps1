# run_cross_provider.ps1
# Cross-provider sensitivity study for the RAITG Springer ASE revision.
# Runs the full 362-requirement experiment on GPT-4o-mini and Groq-hosted
# Meta Llama 3.3 70B, WITHOUT overwriting the existing Sonnet baseline in
# results/. (Gemini was dropped from this study after hitting the free-tier
# per-minute limit; Groq's free tier -- no credit card -- is used instead.)
#
# Prereqs:
#   $env:OPENAI_API_KEY = "sk-..."
#   $env:GROQ_API_KEY   = "gsk_..."
#   pip install openai groq   (in the .venv)

$ErrorActionPreference = "Stop"

Write-Host "=== RAITG Cross-Provider Experiment (Anthropic Sonnet baseline + OpenAI GPT-4o-mini + Groq Llama 3.3 70B) ==="

if (-not $env:OPENAI_API_KEY) {
    Write-Error "OPENAI_API_KEY is not set. Run: `$env:OPENAI_API_KEY = 'sk-...' first."
    exit 1
}
if (-not $env:GROQ_API_KEY) {
    Write-Error "GROQ_API_KEY is not set. Run: `$env:GROQ_API_KEY = 'gsk_...' first."
    exit 1
}

# ---- Estimated total time ----
# OpenAI phase: ~4300 API calls (362 reqs x 3 conditions + repair passes),
# ~1-3 s per call, so roughly 1-4 wall hours.
# Groq phase: same ~4300 API calls but throttled to ~30 req/min on the free
# tier, so plan for ~5-8 wall hours regardless of raw latency. If you hit
# the daily quota (~6000 req/day), rerun with --resume the next day.
$openaiCalls   = 4300
$openaiSecsLo  = $openaiCalls * 1
$openaiSecsHi  = $openaiCalls * 3
$groqSecs      = $openaiCalls * 2.0  # rate-limited: ~2 s/req average
$etaLow  = [TimeSpan]::FromSeconds($openaiSecsLo + $groqSecs)
$etaHigh = [TimeSpan]::FromSeconds($openaiSecsHi + ($openaiCalls * 6.0))
Write-Host ("Expected wall time: {0:hh\:mm} to {1:hh\:mm}" -f $etaLow, $etaHigh)
Write-Host ("Started at: {0}" -f (Get-Date))

# ---- venv ----
if (Test-Path .\.venv\Scripts\Activate.ps1) {
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Warning ".venv not found in current directory; using ambient python."
}

# ---- Sanity check: 3 reqs per provider ----
Write-Host "`n--- Sanity check: OpenAI (3 reqs) ---"
python scripts/run_experiment.py --pilot 3 --backend openai `
    --model gpt-4o-mini --out-suffix "_sanity_openai" --no-resume
if ($LASTEXITCODE -ne 0) {
    Write-Error "OpenAI sanity check FAILED (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "`n--- Sanity check: Groq Llama 3.3 70B (3 reqs) ---"
python scripts/run_experiment.py --pilot 3 --backend groq `
    --model llama-3.3-70b-versatile --out-suffix "_sanity_groq" --no-resume
if ($LASTEXITCODE -ne 0) {
    Write-Error "Groq sanity check FAILED (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

Write-Host "`nSanity checks passed."
$confirm = Read-Host "Kick off the FULL 362-requirement cross-provider runs? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Aborted by user."
    exit 0
}

$start = Get-Date

# ---- Phase 1: OpenAI GPT-4o-mini ----
Write-Host ("`n=== Phase 1/2: OpenAI GPT-4o-mini @ {0} ===" -f (Get-Date))
python scripts/run_experiment.py --full --backend openai `
    --model gpt-4o-mini --out-suffix "_openai"
if ($LASTEXITCODE -ne 0) {
    Write-Error "OpenAI phase FAILED (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}
$mid = Get-Date
Write-Host ("Phase 1 done at {0}. Elapsed: {1}" -f $mid, ($mid - $start))
Write-Host ("Groq phase is rate-limited (~30 req/min free tier) -- expect ~5-8h.")

# ---- Phase 2: Groq Llama 3.3 70B ----
# NOTE: Groq free tier is ~30 requests/min and ~6000 requests/day. The
# ~4300 calls in a 3-condition x 4-SUT x 362-req run therefore take ~5-8
# wall hours even though individual responses are sub-second. If the daily
# cap trips, rerun this script -- --resume (on by default) skips already
# completed run logs so the phase picks up where it left off.
Write-Host ("`n=== Phase 2/2: Groq Llama 3.3 70B @ {0} ===" -f (Get-Date))
python scripts/run_experiment.py --full --backend groq `
    --model llama-3.3-70b-versatile --out-suffix "_groq"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Groq phase FAILED (exit $LASTEXITCODE)."
    exit $LASTEXITCODE
}

$end = Get-Date
Write-Host ("`n=== DONE at {0} ===" -f $end)
Write-Host ("Total elapsed: {0}" -f ($end - $start))
Write-Host "Outputs:"
Write-Host "  results_openai/runs/    - GPT-4o-mini run logs"
Write-Host "  results_openai/tables/  - GPT-4o-mini aggregate CSVs"
Write-Host "  results_groq/runs/      - Groq Llama 3.3 70B run logs"
Write-Host "  results_groq/tables/    - Groq Llama 3.3 70B aggregate CSVs"
