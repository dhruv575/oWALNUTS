#!/bin/bash
# WP90 lane-1 evidence run: every cell in manifest order (S, F, P), pinned to cores 0-3, resumable.
#   nohup bash run_all.sh > ~/lanes/trap_guard_confirmation_v1/logs/evidence.log 2>&1 &
set -u
source ~/lanes/trap_guard_confirmation_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D
git log --oneline -1
$TS $PY run_study.py run
echo ALL-CELLS-FINISHED
