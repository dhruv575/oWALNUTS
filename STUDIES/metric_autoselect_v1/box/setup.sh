#!/bin/bash
# WP75 lane-3 setup (infrastructure, no cells): build the harness, compile the 17 models.
set -u
source ~/lanes/metric_autoselect_v1/env.sh
mkdir -p $L/logs
cd $D && taskset -c 8-11 cargo build --release -j4 > $L/logs/build.log 2>&1 && echo BUILD_OK
cd $D && taskset -c 8-11 $PY run_study.py prepare > $L/logs/prepare.log 2>&1; echo PREPARE_EXIT $?
cd $D && taskset -c 8-11 $PY run_study.py predict > $L/logs/predict.log 2>&1; echo PREDICT_EXIT $?
echo SETUP_DONE
