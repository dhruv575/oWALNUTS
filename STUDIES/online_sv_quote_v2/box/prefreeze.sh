#!/bin/bash
# Pre-freeze disclosures (not evidence): bit-identity of run_warm vs the WP84 harness construction on the SV
# target (sim N=250, K=50, seed 880101, tick 1), one FULL-SIZE N=1,000 reference tick (sim, n=1000, diagnostic
# seed 990001), and a 2-tick warm/refit/stan/pyextra smoke feeding analyze.py. Cores 4-7 (bitcheck, smoke) and 8-11 (N=1000 tick).
set -e
. $(dirname $0)/env.sh
P=$L/prefreeze; rm -rf $P; mkdir -p $P/cells
cd $S
taskset -c 8-11 nohup $W/target/release/wp88 reftick models/data-sim.json 1000 990001 $P/ref-N1000-smoke > $P/ref-N1000-smoke.log 2>&1 &
taskset -c 4-7 $W/target/release/wp88 bitcheck models/data-sim.json 250 50 880101 $P/bitcheck.json
taskset -c 4-7 $W/target/release/wp88 warm models/data-sim.json 250 50 990002 2 $P/cells/warm50-sim-N250-s880101
taskset -c 4-7 $W/target/release/wp88 refit models/data-sim.json 250 990003 2 $P/cells/refit-sim-N250-s880101
taskset -c 4-7 python run_cells.py stan nutpie sim 250 990004 2 $P/cells/nutpie-sim-N250-s880101 $W
taskset -c 4-7 python run_cells.py stan cmdstan sim 250 990005 2 $P/cells/cmdstan-sim-N250-s880101 $W
taskset -c 4-7 $WP88_PYVENV -I run_cells.py pyextra sim 250 200 990006 2 $P/cells/pyextra-sim-N250-K200-s880101 $W
# a 3-tick smoke reference (ticks 1,2 of sim-N250 only) through the gate code path, with diagnostic seeds
python - <<PY
import json; p=json.load(open("protocol.json")); p["reference"]["ticks"]={"sim-N250":[0,1,2],"real-N250":[],"sim-N1000":[]}
p["reference"]["seed_base"]={"sim-N250":990100,"sim-N1000":990200,"real-N250":990300}; json.dump(p,open("$P/protocol-smoke.json","w"))
PY
mkdir -p $P/smoke-study && cp -r models run_cells.py analyze.py $P/smoke-study/ && cp $P/protocol-smoke.json $P/smoke-study/protocol.json
cd $P/smoke-study && taskset -c 4-7 python run_cells.py ref sim 250 $P/cells/ref-sim-N250 $W
cd $P/smoke-study && taskset -c 4-7 $L/venv/bin/python analyze.py $P/cells --out $P/smoke-out 2>&1 | tail -40
wait
cat $P/ref-N1000-smoke.json | head -c 600; echo
echo prefreeze-done
