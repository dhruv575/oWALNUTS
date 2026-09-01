#!/usr/bin/env bash
# Benchmark-box runner. Usage (inside the image):
#   run_bench.sh <owalnuts-commit-sha> <suite>   suites: sv-v2 | sv-v2-native | smoke
# Clones the pinned commit, builds the flagship v2 study, runs the cells
# SEQUENTIALLY (one job at a time — this is a wall-time box), analyzes, and
# writes everything plus measured_on.json under /out.
set -euo pipefail

COMMIT="${1:?commit sha required}"
SUITE="${2:-sv-v2}"
OUT="${OUT_DIR:-/out}"
REPO="${REPO_URL:-https://github.com/dhruv575/oWALNUTS.git}"
THREADS="${BENCH_THREADS:-4}"

mkdir -p "$OUT"
echo "== bench: commit=$COMMIT suite=$SUITE threads=$THREADS"
{
  echo "{"
  echo "  \"commit\": \"$COMMIT\", \"suite\": \"$SUITE\", \"threads\": $THREADS,"
  echo "  \"cpu_model\": \"$(lscpu | sed -n 's/^Model name:[[:space:]]*//p' | head -1)\","
  echo "  \"cpus_visible\": $(nproc), \"kernel\": \"$(uname -r)\","
  echo "  \"started_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"rustc\": \"$(rustc --version)\", \"python\": \"$(python --version 2>&1)\""
  echo "}"
} > "$OUT/measured_on.json"
cat "$OUT/measured_on.json"

git clone --quiet "$REPO" src && cd src && git checkout --quiet "$COMMIT"
STUDY="STUDIES/flagship_crypto_sv_v2"

echo "== build owalnuts python package (editable) and study binary"
( cd integrations/python && maturin develop --release --quiet )
( cd "$STUDY" && cargo build --release --quiet )
BIN="$STUDY/target/release/flagship-crypto-sv-v2"
PY="python"

SYMBOLS="BTC ETH XRP BNB SOL"
SEEDS="98001 98002 98003"
PARTNERS="98011 98012 98013"
[ "$SUITE" = "smoke" ] && { SYMBOLS="BNB"; SEEDS="98001"; PARTNERS=""; }

cd "$STUDY"
mkdir -p artifacts/runs artifacts/draws artifacts/calibration
for sym in $SYMBOLS; do
  for seed in $SEEDS $PARTNERS; do
    [ -f "artifacts/calibration/$sym-$seed.json" ] || "../../$BIN" calibrate "data/$sym.json" artifacts "$seed"
    [ -f "artifacts/runs/$sym-native-$seed.json" ] || "../../$BIN" run2 "data/$sym.json" artifacts "$seed" "artifacts/calibration/$sym-$seed.json" E native
  done
done

if [ "$SUITE" != "sv-v2-native" ]; then
  for sym in $SYMBOLS; do
    for seed in $SEEDS; do
      [ -f "artifacts/runs/$sym-pymc-$seed.json" ] || THREAD_SAFE=1 $PY scripts/run_python_cells.py pymc "$sym" "$seed" E
      # Three-seed external references on the same box (fixes the v1 1-seed asymmetry).
      [ -f "artifacts/runs/$sym-nutpie-$seed.json" ] || $PY scripts/run_python_cells.py nutpie "$sym" "$seed"
      [ -f "artifacts/runs/$sym-numpyro-$seed.json" ] || $PY scripts/run_python_cells.py numpyro "$sym" "$seed"
    done
  done
fi

$PY scripts/analyze.py || true
echo "  \"finished_utc\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" >> "$OUT/measured_on.json"
cp -r artifacts/runs artifacts/calibration artifacts/summary.json artifacts/RESULTS.md "$OUT/" 2>/dev/null || true
mkdir -p "$OUT/draws" && cp artifacts/draws/*.npz "$OUT/draws/" 2>/dev/null || true
echo "== done; artifacts in $OUT (raw .f64 draws left in the container by design)"
