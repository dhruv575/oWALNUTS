# WP93 lane environment (source it). Lanes: 1 = cores 0-3, 2 = cores 4-7 (LANES.md lanes 1-2).
export L=~/lanes/tick_pooling_v1
export S=$L/repo/STUDIES/tick_pooling_v1
export W=$L/work
export TMPDIR=$L/tmp RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export CARGO_TARGET_DIR=$W/target
. ~/.cargo/env
source ~/venv/bin/activate
mkdir -p $W $L/tmp $L/logs
