#!/bin/bash
# WP90 disclosed smoke (non-evidence, diagnostic seed from protocol.json): the pipeline on one cell per kind.
#   bash smoke.sh > ~/lanes/trap_guard_confirmation_v1/logs/smoke.log 2>&1
set -u
source ~/lanes/trap_guard_confirmation_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D && $TS $PY run_study.py smoke
echo SMOKE-DONE
