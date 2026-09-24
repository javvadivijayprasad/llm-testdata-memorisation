#!/bin/bash
# usage: e2_driver.sh <label> [<label> ...]  — kg + score + summarize each label sequentially
cd /home/claude/work/paperE/W
for lab in "$@"; do
  c=$(echo $lab | sed 's/e2_\([a-z0-9]*\)_.*/\1/'); cond=full_$c; [ "$c" = g ] && cond=full
  echo "[$(date +%H:%M:%S)] $lab kg start" >> e2_driver.log
  python3 pipeline_e2.py kg $lab $cond >> logs_e2_$lab.txt 2>&1
  echo "[$(date +%H:%M:%S)] $lab score start" >> e2_driver.log
  python3 pipeline_e2.py score $lab >> logs_e2_$lab.txt 2>&1
  python3 pipeline_e2.py summarize $lab $cond > summary_e2_$lab.txt 2>&1
  echo "[$(date +%H:%M:%S)] $lab DONE" >> e2_driver.log
done
echo "[$(date +%H:%M:%S)] driver finished: $*" >> e2_driver.log
