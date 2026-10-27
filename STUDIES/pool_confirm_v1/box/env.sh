# WP97 lane environment (source it). Lanes: 3 = cores 8-11, 4 = cores 12-15 (LANES.md lanes 3-4).
export L=~/lanes/pool_confirm_v1
export S=$L/repo/STUDIES/pool_confirm_v1
export W=$L/work
export TMPDIR=$L/tmp RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export CARGO_TARGET_DIR=$W/target
. ~/.cargo/env
source ~/venv/bin/activate
mkdir -p $W $L/tmp $L/logs
