# Exposed WALNUTS step-size ladder

Freeze before sampling. Reuse native_prefix02 learned geometry, starts and
exposed seed940850001; retain WALNUTS seeds941850001..4. New multipliers of each
native fixed step are0.5,2,4,8. Multiplier1 is the preserved matched_geometry01
result, not rerun or replaced. Other settings,2000 draws,accuracy thresholds and
full gradient accounting remain identical. No metric adaptation or warmup.

Run all five recoverable targets, including centered eight-schools and GP guards.
ARMA remains a failed recovery; do not change that gate to include it. Each of
20 new workers is bounded180s/2GiB/64MiB,one worker at a time,BLAS1,diskfloor1GiB.
An exception or resource failure is a failure, not missing data to replace.

This is exposed tuning, not validation. Ratios require both native and WALNUTS
accuracy gates. Record continuation and full-workflow ESS per actual gradient;
include native pilot/recovery costs in WALNUTS workflow. No wall-time comparison.

A reason to invest in fresh whole-pilot replication requires ONE global
multiplier: all three qualified-native targets(arK,regression,GARCH) still pass;
geometric mean full-workflow ratio>=1.2 across those three; GARCH ratio>=1.2;
no target among those three below0.9; and no paired accuracy loss against
multiplier1 on any recoverable target. Choose the largest geometric mean among
eligible factors, breaking exact ties toward the factor closest to1. No
confidence interval or confirmatory claim from selecting on these exposed data.
If no factor qualifies, do not extend the ladder or loosen these criteria.
Reassess another mechanism rather than replicate this transplant policy.
