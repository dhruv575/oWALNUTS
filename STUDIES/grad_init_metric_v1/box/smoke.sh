#!/bin/bash
# WP94 disclosed smoke (non-evidence, diagnostic seed from protocol.json): the pipeline on one cell per kind and
# arm, custom_noop bit-identity against defaults recorded into artifacts/environment.json. Pinned to cores 0-3.
#   bash smoke.sh > ~/lanes/grad_init_metric_v1/logs/smoke.log 2>&1
set -u
source ~/lanes/grad_init_metric_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D && nice -n 10 $TS0 $PY run_study.py smoke
$PY - <<"PY"
import json, os
D = os.environ["D"]; A = os.environ["WP94_ART"]
env = json.load(open(f"{D}/artifacts/environment.json"))
chk = json.load(open(f"{A}/smoke/noop-identity.json"))
env["smoke_custom_noop_identical"] = all(v.get("holds") for v in chk.values())
env["smoke_custom_noop_checks"] = chk
json.dump(env, open(f"{D}/artifacts/environment.json", "w"), indent=1)
print("smoke_custom_noop_identical", env["smoke_custom_noop_identical"])
PY
echo SMOKE-DONE
