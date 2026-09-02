#!/bin/sh
# Runs every preregistered cell strictly sequentially; skips cells whose JSON exists.
B="${B:-../../target-study-funnel-defaults/release/funnel-defaults-v1.exe}"
for target in funnel eight gauss100; do
  for arm in defaults levels8 delta0.5 delta0.25 levels8+delta0.5 paper-4 paper-8 stan-style nuts-1; do
    for seed in 82101 82102 82103; do
      out="artifacts/cells/$target-$arm-$seed.json"
      [ -f "$out" ] && continue
      "$B" cell "$target" "$arm" "$seed" "$out" || echo "FAILED $target $arm $seed"
    done
  done
done
echo GRID-DONE
