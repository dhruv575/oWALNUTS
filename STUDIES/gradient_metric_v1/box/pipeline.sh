#!/bin/bash
# WP71 pipeline check (non-evidence, seed 990671): the full driver path (cells + analysis) into $L/scratch/pipe,
# plus the default arm from a plain-feature build (WP68's harness, no `research`) to compare draws hashes. Not committed.
set -u
source ~/lanes/gradient_metric_v1/env.sh
P=$L/scratch/pipe; rm -rf $P; mkdir -p $P/art
M=eight_schools-eight_schools_noncentered
cd $D && WP71_ARTIFACTS=$P/art WP71_DRAWS=$P/draws taskset -c 8-11 $PY - <<"PY"
import run_study as r
r.SEEDS = {"P": [990671], "F": [990671]}
for arm in r.ARMS:
    r.run_pdb_cell("eight_schools-eight_schools_noncentered", arm, 990671)
for arm in r.ARMS:
    r.run_funnel_cell("F", arm, 990671)
r.analyze({})
PY
W=$R/STUDIES/refinement_levels10_v1
cd $W && taskset -c 8-11 cargo build --release -j4 --bin pdb --target-dir $L/target-plain > $L/logs/build-plain.log 2>&1 && \
  taskset -c 8-11 $L/target-plain/release/pdb $WP71_MODELS/${M}_model.so $WP71_MODELS/$M.data.json default 990671 $P/pdb-plain-default.json 4 2>> $P/pdb.log
$PY - <<"PY"
import json, os
P = os.environ["L"] + "/scratch/pipe"
plain = json.load(open(f"{P}/pdb-plain-default.json"))
cell = json.load(open(f"{P}/art/cells/P-eight_schools-eight_schools_noncentered-default-990671.json"))
print("plain execution", plain["execution"], plain["replicas"], "calls", plain["target_calls_total"], "research-build calls", cell["gradients_total"])
print("plain-feature default == research-build default:", [x["draws_fnv"] for x in plain["chains_data"]] == cell["draws_fnv"])
PY
echo PIPELINE_DONE
