#!/bin/bash
# usage: run_cell.sh <model-short> <seed> <variant> [outdir]
# model-short: sblrc__blr, earnings__logearn_interaction, ...
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
m=$1; seed=$2; var=$3; out=${4:-$HERE/artifacts/telemetry}
mkdir -p "$out"
"$HERE/../../target/release/step-collapse-v1.exe" "$HERE/models/${m}_model.so" "$HERE/models/${m}.data.json" "$seed" "$var" "$out/${m}-${var}-${seed}.json" 2>&1 | tail -1
