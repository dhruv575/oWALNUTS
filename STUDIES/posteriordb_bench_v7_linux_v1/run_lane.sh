#!/bin/bash
# WP64: environment, core pinning and phase sequence on the Linux box (lane 1, cores 0-3).
#   nohup ./run_lane.sh all > ~/lanes/posteriordb_bench_v7_linux_v1/logs/all.log 2>&1 &
# Phases: prepare | A (v7 CmdStan+nutpie) | B (v7 oWALNUTS, funnel, dense) | C (extension) | D (analyses) | all (A-D)
set -uo pipefail
L="$HOME/lanes/posteriordb_bench_v7_linux_v1"
S="$L/work/STUDIES/posteriordb_bench_v7_linux_v1"
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export BRIDGESTAN="$L/bridgestan-2.9.0" TMPDIR="$L/tmp" CARGO_HOME="$L/cargo-home"
export CMDSTAN_HOME="$HOME/infra/cmdstan/cmdstan-2.39.0"
export POSTERIORDB_PATH="$HOME/infra/posteriordb/posterior_database"
export BENCH_MODELS="$S/models"
mkdir -p "$TMPDIR" "$S/artifacts/v7" "$S/artifacts/ext"
PY=(taskset -c 0-3 "$L/venv/bin/python" -I)
cd "$S"
v7env() { export OWALNUTS_HARNESS="$L/target-v7/release/posteriordb-bench-v7" OWALNUTS_FUNNEL="$L/target-v7/release/funnel" OWALNUTS_SOURCE_TREE="$L/src-v7"; }
extenv() { export OWALNUTS_HARNESS="$L/target-ext/release/posteriordb-bench-v7" OWALNUTS_SOURCE_TREE="$L/src-ext"; unset OWALNUTS_FUNNEL; }
stamp() { echo "[$(date -u +%FT%TZ)] $*"; }
phase() {
  case "$1" in
    prepare) "${PY[@]}" prepare_competitors.py 4 > artifacts/compile-log.txt 2>&1 ;;
    A) stamp "phase A start"; "${PY[@]}" run_posteriordb.py run --arms=cmdstan,nutpie > artifacts/v7/run-log-phase1.txt 2>&1; stamp "phase A end $?" ;;
    B) stamp "phase B start"; v7env
       "${PY[@]}" run_posteriordb.py run --arms=owalnuts > artifacts/v7/run-log-phase2-owalnuts.txt 2>&1
       "${PY[@]}" run_posteriordb.py checks > artifacts/v7/checks-log.txt 2>&1
       "${PY[@]}" run_posteriordb.py run --arms=owalnuts-dense > artifacts/v7/run-log-phase2-dense.txt 2>&1
       stamp "phase B end" ;;
    C) stamp "phase C start"; extenv; "${PY[@]}" run_extension.py run > artifacts/ext/run-log.txt 2>&1; stamp "phase C end $?" ;;
    D) stamp "phase D start"
       "${PY[@]}" run_posteriordb.py analyze > artifacts/v7/analyze-log.txt 2>&1
       "${PY[@]}" run_extension.py analyze > artifacts/ext/analyze-log.txt 2>&1
       "${PY[@]}" compare_windows.py > artifacts/reproduction-log.txt 2>&1
       stamp "phase D end" ;;
    *) echo "unknown phase $1"; return 2 ;;
  esac
}
if [ "$1" = "all" ]; then for p in A B C D; do phase "$p"; done; else phase "$1"; fi
stamp "run_lane $1 done"
