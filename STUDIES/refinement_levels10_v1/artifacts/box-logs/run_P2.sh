#!/bin/bash
source ~/lanes/refinement_levels10_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D
echo "[amendment 1] block P run 2 starts" >> artifacts/run-log.txt
taskset -c 8-11 $PY run_study.py run P
taskset -c 8-11 $PY run_study.py analyze > $L/logs/analyze.log 2>&1
echo ALL_DONE
