#!/bin/bash
# WP68 lane-3 driver: everything pinned to cores 8-11.
set -u
source ~/lanes/refinement_levels10_v1/env.sh
sudo touch /var/tmp/keep-alive
cd $D && taskset -c 8-11 cargo build --release -j4 > $L/logs/build-default.log 2>&1 || { echo BUILD_FAILED; exit 1; }
cd $D && taskset -c 8-11 cargo build --release -j4 --features levels10 --target-dir target-levels10 > $L/logs/build-levels10.log 2>&1 || { echo BUILD_FAILED; exit 1; }
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests --test kernel_fingerprint > $L/logs/fingerprint.log 2>&1; FP=$?
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests --test sampler_api default_refinement_levels > $L/logs/feature-off.log 2>&1; T0=$?
cd $R && taskset -c 8-11 cargo test --release -j4 --target-dir $L/target-tests-l10 --features candidate-levels10 --test sampler_api default_refinement_levels > $L/logs/feature-on.log 2>&1; T1=$?
cd $R && git diff 5af9903e -- src Cargo.toml Cargo.lock tests > $L/logs/library.diff
mkdir -p $D/artifacts
FP=$FP T0=$T0 T1=$T1 $PY - <<"PY"
import json, os, re, subprocess, platform
L, R, D = os.environ["L"], os.environ["R"], os.environ["D"]
diff = open(f"{L}/logs/library.diff").read()
files = sorted(set(re.findall(r"^diff --git a/(\S+)", diff, re.M)))
plus = [l[1:].strip() for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
minus = [l[1:].strip() for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
src_files_ok = set(files) <= {"Cargo.toml", "src/sampler.rs", "tests/sampler_api.rs"}
minus_ok = minus == ["max_refinement_levels: 8,"]
sampler_part = diff.split("diff --git a/src/sampler.rs")[1].split("diff --git")[0]
sp = [l[1:].strip() for l in sampler_part.splitlines() if l.startswith("+") and not l.startswith("+++")]
code = [l for l in sp if l and not l.startswith("///")]
code_ok = code == ["pub const DEFAULT_MAX_REFINEMENT_LEVELS: usize = if cfg!(feature = \"candidate-levels10\") {", "10", "} else {", "8", "};", "max_refinement_levels: DEFAULT_MAX_REFINEMENT_LEVELS,"]
env = {"commit": subprocess.check_output(["git", "-C", R, "rev-parse", "HEAD"]).decode().strip(),
       "library_diff_files": files, "library_diff_removed": minus, "library_diff_sampler_code_added": code,
       "library_default_build_unchanged": bool(src_files_ok and minus_ok and code_ok),
       "kernel_fingerprint_test_passed": os.environ["FP"] == "0",
       "feature_test_passed": os.environ["T0"] == "0" and os.environ["T1"] == "0",
       "feature_off_test_exit": int(os.environ["T0"]), "feature_on_test_exit": int(os.environ["T1"]),
       "rustc": subprocess.check_output(["rustc", "--version"]).decode().strip(), "uname": platform.platform(),
       "cpu": [l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0],
       "taskset": "8-11", "lane": 3, "cotenancy": "other lanes active on cores 0-7 and 12-15",
       "bridgestan_source_sha256": "b6034f83fb2ffb71ce7be9525b7dded1a225e9a4eaf4b75d4c7e97e3ade05a4c",
       "fingerprint_log_tail": open(f"{L}/logs/fingerprint.log").read()[-800:]}
json.dump(env, open(f"{D}/artifacts/environment.json", "w"), indent=1)
print(json.dumps({k: env[k] for k in ("library_default_build_unchanged", "kernel_fingerprint_test_passed", "feature_test_passed")}))
PY
cd $D
for b in F P L; do taskset -c 8-11 $PY run_study.py run $b; done
taskset -c 8-11 $PY run_study.py analyze > $L/logs/analyze.log 2>&1
echo ALL_DONE
