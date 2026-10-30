# Exposed matched-geometry diagnostic

Use all six targets and exposed seed940850001. This is one mechanism diagnostic,
not a fresh efficacy screen. No policy promotion or goal completion is possible
from this single replicate. Preserve all failures.

Require the native no-jitter prefix qualification to pass on every target before
starting transfers. Native low_rank learns for1100 warmup draws;100 additional
draws recover its map and are discarded. The native continuation is the next2000
draws from a2100-draw run whose first100 and all warmup fields match exactly.
Actual gradient-count difference between long and short runs must agree with
the continuation's step count; record both rather than assuming equivalence.

Recover each map from the first50 paired coordinates and validate the other50
and gradients with unchanged reconstruction gates. Start each WALNUTS chain at
native draw99 using momentum covariance inverse(A*A^T), the native fixed step,
zero warmup and Adaptation::None. Use seeds941850001+i for chain i. The native
and WALNUTS random streams differ; native step sizes are not claimed optimal for
WALNUTS. No jitter in either continuation.

Evaluate both2000-draw four-chain outputs with the unchanged reference gates:
Rhat<=1.01,bulk/tailESS>=400,divergences0,z<=4.5,mean/refSD<=.1,SDerror<=.1.
Report an ESS/gradient ratio only when both qualify. Report both continuation
cost and full workflow cost: native long-run actual calls versus native
short-run actual calls plus WALNUTS continuation calls. Charge native learning
to the transplanted workflow. No ESS/time comparison: the new runner executes
chains sequentially while native uses four cores. Preserve timings as operational
metadata only. Do not infer application value or kernel-wide superiority.

Workers180s/2GiB/64MiB,one at a time,BLAS1,diskfloor1GiB. No cloud use.
