#!/bin/bash
# Pre-freeze smoke (not evidence; diagnostic seeds 99096x): remapcheck, a 2-tick gated reference through the gate
# code path, 60 ticks of every policy with a 10-tick draw interval and a 20-tick re-adaptation period, analyze.py on
# them. Cores 8-11 and 12-15.
set -e
. $(dirname $0)/env.sh
P=$L/prefreeze; rm -rf $P; mkdir -p $P/cells
B=$W/target/release/wp96
cd $S
taskset -c 8-11 $B remapcheck models/data-shift.json 250 $P/remapcheck.json
python - <<PY
import json; p=json.load(open("protocol.json")); p["reference"]["ticks"]=[0,10,20,30,40,50,60]; p["reference"]["every"]=10
p["reference"]["seed_base"]={"shift":990961,"control":990962}
p["accuracy"]["scored_ticks"]={"half1":[10,20,30],"half2":[40,50,60],"tick0":"scored separately"}
p["data"]["shift_tick"]=30
for c in p["cells"]:
    if c["arm"]=="ref": c["ticks"]=p["reference"]["ticks"]
    else:
        c["ticks"]=60; c["seed"]=990963 if c["seed"]==960101 else 990964
        c["policy"]={"m100":"every:20","m500":"every:40"}.get(c["policy_name"],c["policy"])
json.dump(p,open("$P/protocol-smoke.json","w"),indent=1)
PY
mkdir -p $P/smoke-study/models && cp models/data-*.json $P/smoke-study/models/ && cp run_cells.py analyze.py $P/smoke-study/ && cp $P/protocol-smoke.json $P/smoke-study/protocol.json
cd $P/smoke-study
taskset -c 8-11 nohup python run_cells.py queue 3 $W > $P/lane3.log 2>&1 &
taskset -c 12-15 python run_cells.py queue 4 $W > $P/lane4.log 2>&1
wait
taskset -c 12-15 python analyze.py artifacts/cells --out $P/smoke-out 2>&1 | tail -60
echo smoke-done
