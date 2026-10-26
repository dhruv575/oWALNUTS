#!/bin/bash
# WP81 (copied from WP80): build the byte-identical v7 harness crate against a clean git worktree of one commit (on the box).
#   taskset -c 0-3 ./build_harness.sh f52537a1e221bebe62d4441edcba8a228fd4abe4 ext
set -euo pipefail
L="$HOME/lanes/diagonal_metric_shrinkage_v1"
S="$L/work/STUDIES/diagonal_metric_shrinkage_v1"
commit="$1"; name="$2"
tree="$L/src-$name"
export CARGO_HOME="$L/cargo-home" RAYON_NUM_THREADS=4 OMP_NUM_THREADS=1 PATH="$HOME/.cargo/bin:$PATH"
if [ ! -d "$tree" ]; then
  # sparse: the library (src/, integrations/, tests/, Cargo.*, ...) without STUDIES/ (lane disk limit)
  git -C "$L/work" worktree add --no-checkout --detach "$tree" "$commit"
  git -C "$tree" sparse-checkout set --no-cone '/*' '!/STUDIES/'
  git -C "$tree" reset -q --hard "$commit"
fi
test "$(git -C "$tree" rev-parse HEAD)" = "$commit"
git -C "$tree" diff --quiet HEAD -- src integrations tests Cargo.toml
crate="$tree/STUDIES/diagonal_metric_shrinkage_v1"
mkdir -p "$crate/src/bin"
cp "$S/Cargo.toml" "$S/Cargo.lock" "$crate/"
cp "$S/src/main.rs" "$S/src/arms.rs" "$crate/src/"
cp "$S/src/bin/funnel.rs" "$crate/src/bin/funnel.rs"
cd "$crate"
bins=(--bin posteriordb-cell --bin funnel)
rustc --version
CARGO_TARGET_DIR="$L/target-$name" cargo build --release --locked -j4 "${bins[@]}"
sha256sum "$L/target-$name/release/posteriordb-cell" "$L/target-$name/release/funnel"
# R7: the kernel fingerprint test at the commit under test, research feature off and on
cd "$tree"
{ CARGO_TARGET_DIR="$L/target-test" cargo test --release --locked -j4 --test kernel_fingerprint 2>&1
  echo "--- with --features research"
  CARGO_TARGET_DIR="$L/target-test" cargo test --release --locked -j4 --features research --test kernel_fingerprint 2>&1; } | tee "$S/artifacts/fingerprint-test.txt"
