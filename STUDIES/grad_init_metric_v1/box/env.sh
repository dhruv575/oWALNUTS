# WP94 environment on owalnuts-bench (lanes 1-2, cores 0-7). Source before anything else.
source ~/.cargo/env
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export L=~/lanes/grad_init_metric_v1
export R=$L/repo D=$L/repo/STUDIES/grad_init_metric_v1
export WP94_ART=$L/art WP94_WORK=$L/work WP94_MODELS=$L/models WP94_BIN=$L/work/target/release WP94_DRAWS=$L/draws
export CARGO_TARGET_DIR=$L/work/target
export TMPDIR=$L/tmp
export PY=~/venv/bin/python3
export TS0="taskset -c 0-3"
export TS1="taskset -c 4-7"
export TS="$TS0"
mkdir -p $L/work $L/art $L/draws $L/tmp $L/logs $L/models
