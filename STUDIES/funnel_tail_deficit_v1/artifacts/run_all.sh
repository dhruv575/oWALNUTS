#!/bin/bash
# WP66 lane-3 driver: everything pinned to cores 8-11.
set -u
source ~/.cargo/env
export RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1
L=~/lanes/funnel_tail_deficit_v1
R=$L/repo
D=$R/STUDIES/funnel_tail_deficit_v1
sudo touch /var/tmp/keep-alive
cd $D && taskset -c 8-11 cargo build --release -j4 > $L/logs/build-frozen.log 2>&1 || { echo BUILD_FAILED; exit 1; }
cd $R && taskset -c 8-11 cargo test --release -j4 --test kernel_fingerprint > $L/logs/fingerprint.log 2>&1; FP=$?
DIFF=$(git diff a49df800 -- src Cargo.toml Cargo.lock | wc -l)
mkdir -p $D/artifacts
python3 - <<PY
import json,subprocess,platform
fp = $FP == 0
env = {"kernel_fingerprint_test_passed": fp, "kernel_fingerprint_exit": $FP, "library_diff_empty": $DIFF == 0,
       "library_diff_lines": $DIFF, "commit": subprocess.check_output(["git","-C","$R","rev-parse","HEAD"]).decode().strip(),
       "rustc": subprocess.check_output(["rustc","--version"]).decode().strip(), "uname": platform.platform(),
       "cpu": [l.split(":",1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0],
       "taskset": "8-11", "lane": 3, "cotenancy": "three other lanes active on cores 0-7 and 12-15",
       "fingerprint_log_tail": open("$L/logs/fingerprint.log").read()[-1500:]}
json.dump(env, open("$D/artifacts/environment.json","w"), indent=1)
PY
cd $D
for b in A S C; do taskset -c 8-11 python3 run_study.py run $b; done
taskset -c 8-11 python3 run_study.py analyze > $L/logs/analyze.log 2>&1
echo ALL_DONE
