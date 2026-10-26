#!/bin/bash
# WP81: environment, core pinning and run on the Linux box (lane 1, cores 0-3).
#   nohup bash run_lane.sh run > ~/lanes/diagonal_metric_shrinkage_v1/logs/run.log 2>&1 &
set -uo pipefail
L="$HOME/lanes/diagonal_metric_shrinkage_v1"
S="$L/work/STUDIES/diagonal_metric_shrinkage_v1"
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1 TMPDIR="$L/tmp" CARGO_HOME="$L/cargo-home"
export LD_LIBRARY_PATH="$L/tbb${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export POSTERIORDB_PATH="$HOME/infra/posteriordb/posterior_database" BENCH_MODELS="$L/models"
export OWALNUTS_HARNESS="$L/target-ext/release/posteriordb-cell" OWALNUTS_FUNNEL="$L/target-ext/release/funnel" OWALNUTS_SOURCE_TREE="$L/src-ext"
mkdir -p "$TMPDIR" "$S/artifacts"
cd "$S"
echo "[$(date -u +%FT%TZ)] $1 start"
case "$1" in
  run) taskset -c 0-3 "$L/venv/bin/python" -I run_shrinkage.py run > artifacts/run-log.txt 2>&1 ;;
  funnel) taskset -c 0-3 "$L/venv/bin/python" -I run_shrinkage.py funnel > artifacts/funnel-log.txt 2>&1 ;;
  refscales) taskset -c 0-3 "$L/venv/bin/python" -I run_shrinkage.py refscales > artifacts/refscales-log.txt 2>&1 ;;
  analyze) taskset -c 0-3 "$L/venv/bin/python" -I analyze_shrinkage.py > artifacts/analyze-log.txt 2>&1 ;;
  *) echo "unknown phase $1"; exit 2 ;;
esac
echo "[$(date -u +%FT%TZ)] $1 done $?"
