# Full-shape preflight passes; fresh sampling still required

2026-10-30. V3 preserves the full inverse block-precision shape and fits only a
single positive multiplier from the median log-ratio of incumbent variances to
block variances. V2 discovery and all thresholds are unchanged. Unselected
coordinates retain diagonal variances. This does not guarantee adequate overall
scaling and does not change the failed v2 classification.

All 47 analytic/exposed checks pass, including exact diagonal fallback, recovery
of relative block variances despite distorted incumbents, SPD, permutations,
unit transformations for exactly proportional shapes and discovery consistency
on sixteen exposed pilots. Variable-shape unit invariance is not claimed.
Three previously failed geometries improve their exact-covariance condition
proxies by 2748x, 12084x and 21056x. The resulting proxies are still approximately
2045, 100 and 10804, respectively: repair is not perfect whitening and these
numbers are not ESS or speedups. No new target calls or sampling occurred in
the preflight. Worker drained in .23s, sampled peak RSS ~39MB, inputs verified
again at archiving. These are development observations, not independent efficacy.

A separate frozen matched test uses fresh seeds928800001--928800016 and the
same five arms/schedules as the failed ablation, changing only reconstruction.
See FULL-SHAPE-VALIDATION.md. Even a passing result will require broader
nonconjugate controls; the earnings application remains disqualified by its
qualified direct sampler. No production/default changes or usefulness claim.

Preflight evidence: 31 members, 128,458 bytes, SHA256
daf1b4c3a583e3f3385b21f096fb6db2e3ba174408009b7192ed9984e1284579.
Exact-version S3 restore/member verification passed; see fullshape_archive.
