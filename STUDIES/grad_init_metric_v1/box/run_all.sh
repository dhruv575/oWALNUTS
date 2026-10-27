#!/bin/bash
# WP94 evidence run: every cell in manifest order (S, F, P) on two lanes (even positions on cores 0-3, odd on 4-7),
# resumable. Started only when lanes 1-2 are free (no tick_pooling process).
#   nohup bash run_all.sh > ~/lanes/grad_init_metric_v1/logs/evidence.log 2>&1 &
set -u
source ~/lanes/grad_init_metric_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D
git log --oneline -1
cp $D/artifacts/environment.json $WP94_ART/environment.json 2>/dev/null || true
date -u
$TS0 $PY run_study.py run all 0 2 > $L/logs/lane0.log 2>&1 &
P0=$!
$TS1 $PY run_study.py run all 1 2 > $L/logs/lane1.log 2>&1 &
P1=$!
wait $P0; echo LANE0_EXIT $?
wait $P1; echo LANE1_EXIT $?
date -u
echo ALL-CELLS-FINISHED
