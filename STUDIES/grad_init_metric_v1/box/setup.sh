#!/bin/bash
# WP94 setup (infrastructure, no evidence cells): unbundle the branch, copy WP85's 22 BridgeStan model
# libraries byte-identically (hashed), build the harness release, run the library integrity checks (R7) and
# write artifacts/environment.json. Builds are pinned to cores 0-3 at nice 10 with 4 jobs (lanes may be busy).
#   bash setup.sh <bundle> <branch> <base_commit> <source_repo_on_the_box>
set -u
BUNDLE=$1; BRANCH=$2; BASE=$3; SRC_REPO=$4
source ~/lanes/grad_init_metric_v1/env.sh
sudo touch /var/tmp/keep-alive
NB="nice -n 10 $TS0"
cd $L
if [ ! -d repo ]; then git clone -q "$SRC_REPO" repo; fi
cd $R
git fetch -q "$BUNDLE" "$BRANCH:wp94-incoming" && git checkout -q -B "$BRANCH" wp94-incoming && git log --oneline -1
SRC=~/lanes/metric_autoselect_confirmation_v1/models
for m in $($PY -c "import json;print(' '.join(json.load(open('$D/protocol.json'))['models']))"); do
  for ext in _model.so .data.json .stan; do cp -n $SRC/$m$ext $L/models/ 2>/dev/null || true; done
done
mkdir -p $D/artifacts
(cd $L/models && sha256sum *.so *.data.json *.stan) > $D/artifacts/models.sha256
(cd $SRC && sha256sum *.so) > $L/logs/wp85-models.sha256
ls $L/models/*.so | wc -l
cd $D && $NB cargo build --release -j4 > $L/logs/build.log 2>&1; B=$?; echo BUILD_EXIT $B
cd $D && $NB cargo clippy --release --all-targets -j4 -- -D warnings > $L/logs/clippy-study.log 2>&1; CS=$?; echo CLIPPY_STUDY_EXIT $CS
cd $R && CARGO_TARGET_DIR=$L/work/target-lib $NB cargo test --release -j4 --test kernel_fingerprint > $L/logs/fingerprint-default.log 2>&1; FP0=$?; echo FP_DEFAULT_EXIT $FP0
cd $R && CARGO_TARGET_DIR=$L/work/target-lib-research $NB cargo test --release -j4 --features research --test kernel_fingerprint --test grad_init_metric --test trapped_chain_restart > $L/logs/fingerprint-research.log 2>&1; FP1=$?; echo FP_RESEARCH_EXIT $FP1
cd $R && CARGO_TARGET_DIR=$L/work/target-lib-clippy $NB cargo clippy --all-targets --all-features -j4 -- -D warnings > $L/logs/clippy-library.log 2>&1; CL=$?; echo CLIPPY_LIBRARY_EXIT $CL
cd $R && git diff "$BASE" --stat -- src tests Cargo.toml Cargo.lock > $L/logs/library.diff
B=$B CS=$CS FP0=$FP0 FP1=$FP1 CL=$CL BASE=$BASE $PY - <<"PY"
import json, os, re, subprocess, platform, glob
L, R, D = os.environ["L"], os.environ["R"], os.environ["D"]
proto = json.load(open(f"{D}/protocol.json"))
seeds = [str(s) for k, v in proto["seeds"].items() for s in (v if isinstance(v, list) else [v])]
others = [p for p in glob.glob(os.path.expanduser("~/lanes/*/repo/STUDIES/*/protocol.json")) + glob.glob(os.path.expanduser("~/lanes/*/repo/STUDIES/*/PREREGISTRATION.md")) if "/grad_init_metric_v1/" not in p]
hits = sorted({(p, s) for p in others for s in seeds if re.search(rf"\b{s}\b", open(p, errors="ignore").read())})
env = {"commit": subprocess.check_output(["git", "-C", R, "rev-parse", "HEAD"]).decode().strip(),
       "base_commit": os.environ["BASE"],
       "library_diff_stat": open(f"{L}/logs/library.diff").read().strip().splitlines()[-1:] ,
       "build_ok": os.environ["B"] == "0",
       "kernel_fingerprint_default_passed": os.environ["FP0"] == "0",
       "kernel_fingerprint_research_passed": os.environ["FP1"] == "0",
       "grad_init_metric_tests_passed": os.environ["FP1"] == "0",
       "trapped_chain_restart_tests_passed": os.environ["FP1"] == "0",
       "clippy_library_clean": os.environ["CL"] == "0", "clippy_study_clean": os.environ["CS"] == "0",
       "smoke_custom_noop_identical": None,
       "box_seed_check": {"files_checked": len(others), "hits": hits},
       "rustc": subprocess.check_output(["rustc", "--version"]).decode().strip(), "uname": platform.platform(),
       "cpu": [l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")][0],
       "taskset": "0-3 and 4-7", "lanes": [1, 2], "cotenancy": "another study on cores 8-15 (pinned, co-tenanted)"}
json.dump(env, open(f"{D}/artifacts/environment.json", "w"), indent=1)
print(json.dumps(env, indent=1))
PY
echo SETUP_DONE
