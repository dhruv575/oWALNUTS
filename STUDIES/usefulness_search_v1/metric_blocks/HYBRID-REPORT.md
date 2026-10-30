# Fresh hybrid validation: prespecified continuation gate FAILED

All16 fresh seeds completed on six models, with five matched arms. 672 bounded
jobs drained,480 stage schedules verified,96 hybrid outputs exactly match their
selected branch apart from timing. Sources and targets are hash-identical across
four chunks. All pilot,400 score and64d probe calls are charged as prescribed.
Seven analytic/invalid-input gate checks passed before execution. No retuning or
reruns occurred. Four721-member private archives were each restored from exact
S3 versions and verified before redundant compressed results were reclaimed.

## Accuracy and target-call efficiency

Pass counts are out of16. Ratios are paired geometric means of minimum bulkESS
per total target calls. Intervals use10000 paired-seed bootstrap replicates;
they are exploratory per-target95% intervals, not simultaneous inference.

| Target | Hybrid / v4 / Fisher / dense / auto passes | Hybrid / auto [95% interval] | Hybrid / Fisher |
|---|---:|---:|---:|
| ARMA | 16 / 16 / 15 / 16 / 16 | 1.241 [1.196,1.280] | unqualified |
| arK | 16 / 16 / 16 / 16 / 16 | 1.298 [1.254,1.349] | .996 |
| Proper-prior regression | 16 / 16 / 16 / 16 / 16 | 10.865 [7.757,13.706] | .807 |
| Centered eight schools | 0 / 0 / 0 / 0 / 0 | unqualified | unqualified |
| GARCH | 16 / 16 / 16 / 16 / 16 | 1.490 [1.320,1.661] | .909 |
| GP Poisson regression | 16 / 16 / 13 / 8 / 16 | .99935 [.99933,.99937] | unqualified |

No paired hybrid accuracy loss against automatic adaptation or v4 was observed.
This is not a formal noninferiority guarantee. Failed arms receive no ratio
credit. Every method still fails the centered eight-schools accuracy gates.
GP uses automatic fallback on every seed; its small efficiency loss is overhead.

ARMA and GARCH meet the frozen non-Gaussian signal criterion against both auto
and v4. Against adaptive dense, ARMA is1.170 [1.131,1.203]; GARCH is1.057
[.927,1.177], inconclusive. The strong regression gain over auto is still not an
application case because a cheap collapsed moment control already qualifies.

## Why the overall gate fails

The frozen policy requires no fully qualified target's geometric hybrid/Fisher
ratio below .90. Proper-prior regression is .8066 [.6083,.9963], worst paired
ratio .1469. The gate declines Fisher on three regression pilots and selects v4;
the remaining13 use Fisher. These fallbacks lose enough efficiency to fail the
requirement. GARCH also declines Fisher on three seeds; its ratio .9093
[.8144,.9972] narrowly meets the point-estimate floor and its uncertainty does
not establish noninferiority. Preserve the complete failed gate despite gains
elsewhere. Do not remove the regression target or lower the floor retrospectively.

## Limits and next work

This is a staged research policy, not a production/default change. Timing scope
is incomplete: component timers exclude worker startup/model loading and cannot
support an end-to-end runtime claim (HYBRID-TIMING-AUDIT.md). The expensive
high-precision Fisher solver also precludes claims against optimized wall time.
Six targets and16 seeds do not establish general usefulness or novelty. Related
work already supplies metric switching and Fisher preconditioning.

Diagnose the three regression fallbacks using saved metrics and qualified
references. Test whether scale reconstruction, rather than an unsafe full Fisher
metric, explains the loss. Compare established Hessian/covariance selection
criteria before designing another guard; avoid threshold tuning to model names
or these outcomes. Any revised policy needs new seeds and unchanged strong
baselines. Application, general improvement and paper completion remain open.

Storage audit:251,365,930 bytes of redundant chunk RESULT gzip files reclaimed
only after verification; original raw results, exact archives and manifests
remain. Per-chunk RECLAIM.json records every exact path and hash. Root remains
above1GiB; tmpfs retains substantial headroom. All four chunks are terminal.
