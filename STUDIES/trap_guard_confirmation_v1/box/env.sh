# WP90 lane-1 environment on owalnuts-bench. Source before anything else.
source ~/.cargo/env
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export L=~/lanes/trap_guard_confirmation_v1
export R=$L/repo D=$L/repo/STUDIES/trap_guard_confirmation_v1
export WP90_ART=$L/art WP90_WORK=$L/work WP90_MODELS=$L/models WP90_BIN=$L/work/target/release WP90_DRAWS=$L/draws
export CARGO_TARGET_DIR=$L/work/target
export TMPDIR=$L/tmp
export PY=~/venv/bin/python3
export TS="taskset -c 0-3"
mkdir -p $L/work $L/art $L/draws $L/tmp $L/logs $L/models
