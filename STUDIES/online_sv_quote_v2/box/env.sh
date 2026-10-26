# WP88 lane environment (source it). Queue cores: A 4-7, B 8-11, C 12-15 (LANES.md lanes 2-4).
export L=~/lanes/online_sv_quote_v2
export S=$L/repo/STUDIES/online_sv_quote_v2
export W=$L/work
export TMPDIR=$L/tmp RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
export CARGO_TARGET_DIR=$W/target
export WP88_PYVENV=$L/venv/bin/python
. ~/.cargo/env
source ~/venv/bin/activate
mkdir -p $W $L/tmp $L/logs
