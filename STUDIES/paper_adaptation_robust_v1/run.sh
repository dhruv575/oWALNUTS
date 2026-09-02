#!/usr/bin/env bash
# Run every preregistered cell sequentially (resumable: existing cells are kept).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
export RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu
export CARGO_TARGET_DIR="$HERE/target"
export POSTERIORDB_MODELS="${POSTERIORDB_MODELS:-$HERE/../posteriordb_bench_v1/models}"
cd "$HERE" && cargo build --release || exit 1
BIN="$CARGO_TARGET_DIR/release/paper-adaptation-robust-v1.exe"
mkdir -p "$HERE/artifacts/cells"
for model in kidiq__kidscore_momhsiq sblrc__blr earnings__logearn_interaction diamonds__diamonds nes2000__nes mesquite__logmesquite_logvash hmm_example__hmm_example; do
  for arm in ${ARMS:-da paper floor defer guarded guarded-trim zero floor-zero guarded-zero zero-wide guarded-zero-wide}; do
    for seed in 77201 77202; do
      out="$HERE/artifacts/cells/$model-$arm-$seed.json"
      [ -e "$out" ] && continue
      "$BIN" run "$model" "$arm" "$seed" "$out" 2>&1 | tee -a "$HERE/artifacts/run-log.txt"
    done
  done
done
"$BIN" analyze "$HERE/artifacts/cells" "$HERE/artifacts/results-table.md" "$HERE/artifacts/summary.json"
