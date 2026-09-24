#!/bin/bash
# Re-run metrics_fidelity.py for every cell whose metrics JSON exists, using the subject and csv_dir
# recorded in that JSON (so the regenerated file is comparable). Idempotent; no LLM calls.
cd "$(dirname "$0")"
for f in metrics/pc/*.json metrics/pc_r/*.json metrics/faker_*.json metrics/auto_v122_*.json metrics/plan_*.json metrics/direct_*.json; do
  [ -f "$f" ] || continue
  subj=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['subject'])" "$f")
  dir=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['csv_dir'])" "$f")
  [ -d "$dir" ] || dir="../$dir"
  [ -d "$dir" ] || { echo "SKIP $f (csv_dir missing: $dir)"; continue; }
  python3 metrics_fidelity.py "$subj" "$dir" "$f" >/dev/null || echo "FAIL $f"
done
echo done
