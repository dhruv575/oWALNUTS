# WP96 lane environment (source it). Lane cores: 3 = 8-11 (shift stream), 4 = 12-15 (control stream).
export L=~/lanes/warm_drift_v1
export S=$L/repo/STUDIES/warm_drift_v1
export W=$L/work
export TMPDIR=$L/tmp RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export CARGO_TARGET_DIR=$W/target
. ~/.cargo/env
source ~/venv/bin/activate
mkdir -p $W $L/tmp $L/logs
