#!/bin/bash
# WP64: build the byte-identical v7 harness crate against a clean git worktree of one commit (on the box).
#   taskset -c 0-3 ./build_harness.sh f097391cd956246e3fbd5a6593622bc424b65f9e v7
#   taskset -c 0-3 ./build_harness.sh c5c6012287fb99bea3ee73dd1abe01e7369c5d6f ext
set -euo pipefail
L="$HOME/lanes/posteriordb_bench_v7_linux_v1"
S="$L/work/STUDIES/posteriordb_bench_v7_linux_v1"
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
crate="$tree/STUDIES/posteriordb_bench_v7_linux_v1"
mkdir -p "$crate/src/bin"
cp "$S/Cargo.toml" "$S/Cargo.lock" "$crate/"
cp "$S/src/main.rs" "$crate/src/main.rs"
cp "$S/src/bin/funnel.rs" "$crate/src/bin/funnel.rs"
cd "$crate"
if [ "$name" = "v7" ]; then bins=(--bins); else bins=(--bin posteriordb-bench-v7); fi
rustc --version
CARGO_TARGET_DIR="$L/target-$name" cargo build --release --locked -j4 "${bins[@]}"
sha256sum "$L/target-$name/release/posteriordb-bench-v7" "$L/target-$name/release/funnel" 2>/dev/null || true
