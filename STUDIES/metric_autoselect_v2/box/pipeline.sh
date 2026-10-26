#!/bin/bash
# WP79 pipeline check (non-evidence, seed 990679): the full driver path (cells + analysis) into $L/scratch/pipe,
# plus the default arm from a plain-feature build (WP68's harness, no `research`) to compare draws hashes. Not committed.
set -u
source ~/lanes/metric_autoselect_v2/env.sh
P=$L/scratch/pipe; rm -rf $P; mkdir -p $P/art
M=kidiq-kidscore_momhsiq
cd $D && WP79_ARTIFACTS=$P/art WP79_DRAWS=$P/draws taskset -c 8-11 $PY - <<"PY"
import run_study as r
r.SEEDS = {"P": [990679], "F": [990679]}
for arm in r.ARMS:
    r.run_pdb_cell("kidiq-kidscore_momhsiq", arm, 990679)
for arm in r.ARMS:
    r.run_funnel_cell("F", arm, 990679)
r.analyze({})
PY
W=$R/STUDIES/refinement_levels10_v1
cd $W && taskset -c 8-11 cargo build --release -j4 --bin pdb --target-dir $L/target-plain > $L/logs/build-plain.log 2>&1 && \
  taskset -c 8-11 $L/target-plain/release/pdb $WP79_MODELS/${M}_model.so $WP79_MODELS/$M.data.json default 990679 $P/pdb-plain-default.json 4 2>> $P/pdb.log
$PY - <<"PY"
import json, os
P = os.environ["L"] + "/scratch/pipe"
plain = json.load(open(f"{P}/pdb-plain-default.json"))
cell = json.load(open(f"{P}/art/cells/P-kidiq-kidscore_momhsiq-diag-990679.json"))
print("plain execution", plain["execution"], plain["replicas"], "calls", plain["target_calls_total"], "research-build calls", cell["gradients_total"])
print("plain-feature default == research-build default:", [x["draws_fnv"] for x in plain["chains_data"]] == cell["draws_fnv"])
PY
echo PIPELINE_DONE
