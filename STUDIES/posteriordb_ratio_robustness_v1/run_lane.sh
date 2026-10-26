#!/bin/bash
# WP72: environment, core pinning and run on the Linux box (lane 1, cores 0-3).
#   nohup bash run_lane.sh run > ~/lanes/posteriordb_ratio_robustness_v1/logs/run.log 2>&1 &
set -uo pipefail
L="$HOME/lanes/posteriordb_ratio_robustness_v1"
S="$L/work/STUDIES/posteriordb_ratio_robustness_v1"
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1 TMPDIR="$L/tmp" CARGO_HOME="$L/cargo-home"
export CMDSTAN_HOME="$HOME/infra/cmdstan/cmdstan-2.39.0"
export POSTERIORDB_PATH="$HOME/infra/posteriordb/posterior_database"
export BENCH_MODELS="$L/models"
export OWALNUTS_HARNESS="$L/target-ext/release/posteriordb-bench-v7" OWALNUTS_SOURCE_TREE="$L/src-ext"
mkdir -p "$TMPDIR" "$S/artifacts"
cd "$S"
echo "[$(date -u +%FT%TZ)] $1 start"
case "$1" in
  run) taskset -c 0-3 "$L/venv/bin/python" -I run_robustness.py run > artifacts/run-log.txt 2>&1 ;;
  *) echo "unknown phase $1"; exit 2 ;;
esac
echo "[$(date -u +%FT%TZ)] $1 done $?"
