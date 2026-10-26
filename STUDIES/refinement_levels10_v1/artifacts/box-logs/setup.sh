#!/bin/bash
source ~/lanes/refinement_levels10_v1/env.sh
cd $D && taskset -c 8-11 cargo build --release -j4 > $L/logs/build-default.log 2>&1 && echo BUILD_DEFAULT_OK
cd $D && taskset -c 8-11 cargo build --release -j4 --features levels10 --target-dir target-levels10 > $L/logs/build-levels10.log 2>&1 && echo BUILD_L10_OK
cd $D && taskset -c 8-11 $PY run_study.py prepare > $L/logs/prepare.log 2>&1; echo PREPARE_EXIT $?
echo SETUP_DONE
