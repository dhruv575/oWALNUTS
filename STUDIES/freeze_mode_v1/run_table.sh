#!/usr/bin/env bash
# The preregistered arm table of STUDIES/freeze_mode_v1: both models, three
# seeds, every arm. Resumable (existing cells are skipped). Cells are
# strictly sequential so the walls are comparable.
set -u
cd "$(dirname "$0")"
EXE=${EXE:-../../target-study/release/freeze-mode-v1.exe}
ARMS=${ARMS:-"baseline exhaust-accept mean-accept stan-style step-floor exhaust-signed exhaust-signed+mean-accept stan-style+exhaust-signed warmup-signed"}
SEEDS=${SEEDS:-"78101 78102 78103"}
MODELS=${MODELS:-"arma__arma11 hudson_lynx_hare__lotka_volterra"}
mkdir -p artifacts/table
for model in $MODELS; do
  for arm in $ARMS; do
    for seed in $SEEDS; do
      out="artifacts/table/$model-$arm-$seed.json"
      if [ -f "$out" ]; then continue; fi
      echo "[$(date +%H:%M:%S)] $model $arm $seed"
      "$EXE" "models/${model}_model.so" "models/${model}.data.json" "$seed" "$arm" "$out" 2>&1 | tail -1
    done
  done
done
echo "[$(date +%H:%M:%S)] done"
