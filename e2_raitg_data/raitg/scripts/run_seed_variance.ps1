# run_seed_variance.ps1
# 3-seed variance study on the GPT-4o-mini ablation condition.
#
# Seed=0 is the default (main run in run_cross_provider.ps1).
# This script runs the two ADDITIONAL seeds (1 and 2), ablation condition
# only, on the full 362-requirement corpus, so the paper can report a
# mean+/-SD on ablation coverage/mutation-score for GPT-4o-mini.
#
# Prereqs:
#   $env:OPENAI_API_KEY = "sk-..."
#   pip install openai   (in the .venv)
#   OpenAIAdapter must support the --seed argument (added 2026-08-06).

$ErrorActionPreference = "Stop"

Write-Host "=== RAITG Seed Variance Study (GPT-4o-mini, ablation only) ==="

if (-not $env:OPENAI_API_KEY) {
    Write-Error "OPENAI_API_KEY is not set. Run: `$env:OPENAI_API_KEY = 'sk-...' first."
    exit 1
}

if (Test-Path .\.venv\Scripts\Activate.ps1) {
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Warning ".venv not found in current directory; using ambient python."
}

$start = Get-Date
Write-Host ("Started at: {0}" -f $start)
# Two seeds x 362 reqs x 1 condition = ~724 API calls; expect ~15-45 min.

foreach ($seed in 1, 2) {
    Write-Host ("`n--- Seed $seed starting: {0} ---" -f (Get-Date))
    python scripts/run_experiment.py --full --backend openai `
        --model gpt-4o-mini --conditions ablation `
        --seed $seed --out-suffix "_openai_seed$seed"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Seed $seed run FAILED (exit $LASTEXITCODE)."
        exit $LASTEXITCODE
    }
    Write-Host ("--- Seed $seed done: {0} ---" -f (Get-Date))
}

$end = Get-Date
Write-Host ("`n=== DONE at {0} ===" -f $end)
Write-Host ("Total elapsed: {0}" -f ($end - $start))
Write-Host "Outputs:"
Write-Host "  results_openai_seed1/runs/ -- ablation, seed=1"
Write-Host "  results_openai_seed2/runs/ -- ablation, seed=2"
Write-Host "Combine with results_openai/runs/*ablation* (seed=0) for the 3-seed variance table."
