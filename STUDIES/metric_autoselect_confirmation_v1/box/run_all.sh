#!/bin/bash
# WP85 lane-3 driver: everything pinned to cores 8-11.
set -u
source ~/lanes/metric_autoselect_confirmation_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D && taskset -c 8-11 cargo build --release -j4 > $L/logs/build.log 2>&1 || { echo BUILD_FAILED; exit 1; }
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests --test kernel_fingerprint > $L/logs/fingerprint.log 2>&1; FP0=$?
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests-research --features research --test kernel_fingerprint > $L/logs/fingerprint-research.log 2>&1; FP1=$?
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests-research --features research --test metric_autoselect --test metric_autoselect_hessian > $L/logs/metric-autoselect-test.log 2>&1; T=$?
cd $R && git diff fa04c5b9 -- src tests Cargo.toml Cargo.lock > $L/logs/library.diff
mkdir -p $D/artifacts
FP0=$FP0 FP1=$FP1 T=$T $PY - <<"PY"
import json, os, re, subprocess, platform, glob
L, R, D = os.environ["L"], os.environ["R"], os.environ["D"]
diff = open(f"{L}/logs/library.diff").read()
proto = json.load(open(f"{D}/protocol.json"))
seeds = [str(s) for v in proto["seeds"].values() for s in v]
others = [p for p in glob.glob(os.path.expanduser("~/lanes/*/repo/STUDIES/*/protocol.json")) + glob.glob(os.path.expanduser("~/lanes/*/repo/STUDIES/*/PREREGISTRATION.md")) if "/metric_autoselect_confirmation_v1/" not in p]
hits = sorted({(p, s) for p in others for s in seeds if re.search(rf"\b{s}\b", open(p, errors="ignore").read())})
env = {"commit": subprocess.check_output(["git", "-C", R, "rev-parse", "HEAD"]).decode().strip(),
       "library_diff_files": sorted(set(re.findall(r"^diff --git a/(\S+)", diff, re.M))),
       "library_diff_scoped": set(re.findall(r"^diff --git a/(\S+)", diff, re.M)) <= {"src/walnutpie.rs", "tests/metric_autoselect_hessian.rs"},
       "kernel_fingerprint_test_passed": os.environ["FP0"] == "0" and os.environ["FP1"] == "0",
       "autoselect_tests_passed": os.environ["T"] == "0",
       "box_seed_check": {"files_checked": len(others), "hits": hits},
       "rustc": subprocess.check_output(["rustc", "--version"]).decode().strip(), "uname": platform.platform(),
       "cpu": [l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0],
       "taskset": "8-11", "lane": 3, "cotenancy": "other lanes active on the remaining cores"}
json.dump(env, open(f"{D}/artifacts/environment.json", "w"), indent=1)
print(json.dumps(env))
PY
cd $D
for b in P F; do taskset -c 8-11 $PY run_study.py run $b; done
taskset -c 8-11 $PY run_study.py analyze > $L/logs/analyze.log 2>&1
echo ALL_DONE
