#!/bin/bash
# WP80 (copied from WP72): build the byte-identical v7 harness crate against a clean git worktree of one commit (on the box).
#   taskset -c 0-3 ./build_harness.sh c5c6012287fb99bea3ee73dd1abe01e7369c5d6f ext
set -euo pipefail
L="$HOME/lanes/nutpie_gap_decomposition_v1"
S="$L/work/STUDIES/nutpie_gap_decomposition_v1"
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
crate="$tree/STUDIES/nutpie_gap_decomposition_v1"
mkdir -p "$crate/src/bin"
cp "$S/Cargo.toml" "$S/Cargo.lock" "$crate/"
cp "$S/src/main.rs" "$crate/src/main.rs"
cp "$S/src/bin/funnel.rs" "$crate/src/bin/funnel.rs"
cp "$S/src/bin/telemetry.rs" "$crate/src/bin/telemetry.rs"
cd "$crate"
bins=(--bin posteriordb-bench-v7 --bin telemetry)
rustc --version
CARGO_TARGET_DIR="$L/target-$name" cargo build --release --locked -j4 "${bins[@]}"
sha256sum "$L/target-$name/release/posteriordb-bench-v7" "$L/target-$name/release/telemetry"
