# Curvature scaling and tuning, 2026-10-29

Calibration-selected tuning approximately halves WALNUTS's native sampling
time at fixed retained-draw budgets across this six-target grid. The strongest
curvature case improves from 0/8 qualifying default ladders to 8/8 selected
ladders. The predeclared broader advantage over tuned NUTS is **not achieved**.
The useful new lead is reduced target-evaluation work on the hardest target,
which could matter when evaluating a likelihood is expensive. That possibility
has not been demonstrated on an expensive or practical likelihood.

## Design and results

Protocol commit `0a5a5da7`, calibration selection `efc48c93`. Six exact targets
cross dimensions 8/24 with curvature 0.5/2/5, placing a curved transformation
in every independent pair. This is more extensively curved than the earlier
one-pair banana. Equal six-configuration searches per engine used two
calibration seeds each: 144 fits. All configuration choices were frozen before
384 held-out fits on eight fresh seeds, independent 3,000/6,000-draw budgets,
four chains, 750 warmup, maximum depth ten, and identical native target code.

The four arms are selected WALNUTS, selected NUTS, previous WALNUTS .99/error1,
and exact-reparameterized NUTS. The strict exact-functional error, MCSE,
R-hat/ESS, retained-divergence and depth gates remain fixed, with pairwise
functionals expanded to every pair. Every calibration and held-out job
executed successfully, drained its process group, and preserved source identity.
Calibration took 64.77 seconds and validation 166.27 seconds on twelve cores.

| Dimension | Curvature | Selected WALNUTS ladders /8 | Previous WALNUTS /8 | Selected NUTS /8 | Reparameterized NUTS /8 | Matched kernel cost ratio NUTS/WALNUTS |
|---|---:|---:|---:|---:|---:|---:|
| 8 | 0.5 | 8 | 8 | 7 | 8 | 1.80 (7 pairs) |
| 8 | 2 | 7 | 8 | 8 | 8 | 0.57 (7 pairs) |
| 8 | 5 | 8 | 2 | 8 | 8 | 0.43 (8 pairs) |
| 24 | 0.5 | 8 | 8 | 8 | 8 | 0.70 (8 pairs) |
| 24 | 2 | 8 | 8 | 7 | 8 | 0.65 (7 pairs) |
| 24 | 5 | 8 | 0 | 8 | 8 | 0.87 (8 pairs) |

Ratios above one favor WALNUTS. Ladders charge every unsuccessful smaller
budget before the first success. Censored seeds remain visible and are
excluded from paired successful-cost ratios, not assigned invented times.
The sole >=1.5 median is the mild, eight-dimensional target; its exploratory
95% interval is [0.91,2.25], crossing one. The rule required qualifying leads
on at least two targets. No convincing multi-target NUTS speed advantage is
established. Full fixed-budget outcomes and intervals are in SUMMARY.json.

## What tuning improved

All selected WALNUTS settings use target acceptance .90 instead of .99.
The selected local-error threshold is 10 on cases (8,.5), (8,5), (24,.5),
and 1 on the remaining cases. NUTS also received independent calibration
over .90/.99 and three mass adaptation settings; it was not left untuned.

At 3,000 draws, previous/selected median kernel costs range from approximately
1.92x to 2.17x. This is a **fixed-budget** speed improvement, not a claim that
all those draws qualify. In the hardest (24,5) case, previous WALNUTS had
106–143 depth-limit hits per 3,000-draw fit and 187–307 at 6,000. Its exact
accuracy/MCSE gates passed; depth saturation blocked qualification. Selected
WALNUTS qualifies seven seeds at each fixed budget and all eight across the
ladder. Thus 0/8 versus 8/8 does not mean the former produced eight demonstrably
wrong posterior distributions.

There is a tradeoff: (8,2) selected WALNUTS qualifies only 7/8 ladders versus
8/8 previously; its tighter MCSE requirement is the remaining issue. This
screen does not justify globally changing library defaults. NUTS's two 7/8
rows are driven by occasional retained divergences, despite accurate bounded
functionals. The frozen zero-divergence criterion is retained for both engines.

## Where a larger advantage might come from

On (24,5), both selected engines qualify all eight ladders. The median paired
NUTS/WALNUTS target-call ratio is **1.97**, with exploratory interval
**[1.78,2.18]**, while the kernel-time ratio is only **0.87** [0.75,1.02].
WALNUTS uses fewer density/gradient evaluations but has more overhead per call
on this cheap analytic target. Target calls, retained draws, and wall time are
different quantities.

An explicitly hypothetical additive-cost calculation, keeping these exact
trajectories and adding identical work to every target call, gives a median
ratio of 1.48 at an extra 1 microsecond per call and 1.82 at 5 microseconds.
These are **projections, not measured speedups** and not evidence about another
posterior. COST-SENSITIVITY.json and cost_sensitivity.py preserve the calculation.
The next useful experiment is a genuinely expensive curved likelihood with a
qualified reference, fresh seeds, strong NUTS tuning and optimized model
baselines. Artificial sleeps or duplicated arithmetic would not establish a
practical advantage.

The exact Gaussian reparameterization qualifies every seed at the smaller
budget and is substantially cheaper on strongly curved targets. For (24,5),
its median ladder kernel cost is 0.096 times selected WALNUTS's. This analytic
model rewrite is available for these synthetic targets and must be included:
raw-parameterization improvements are not evidence of uniqueness.

## Validation and preservation

Five test methods passed, including analytic finite-difference gradients,
exact transforms/functionals, equivalent native values and recoverable overflow,
all thirteen native configuration Gaussian smoke checks, and cost/censoring
analysis. All 528 fitted cases executed without failures. Raw double-precision
draws, source freezes, seeds, process receipts and metrics are preserved.

The local archive is `target/curvature-scaling-evidence-v1.tar.gz`; its complete
verification receipt is ARCHIVE-VERIFICATION.json. Streaming avoids allocating
a duplicate tar file on the nearly full EC2 disk. Remote originals remain at
`/home/ubuntu/lanes/curvature-scaling-20261029`. S3 remains pending renewal of
the previously expired local AWS login. The instance remains running.
All 2,139 archive members, both executed-source freezes, and the held-out
selection hash verified. Archive SHA256:
`7fa3702e257c9cc336454cc3121161711ae9da6ee5a62d35b253e28305011438`.
The last resource check showed about 30 GiB available RAM and 1.3 GiB free
root disk; another campaign must respect the 1 GiB admission reserve.

This is a selected-family exploratory study with eight held-out seeds, two
calibration seeds, one machine, coarse restart ladders and block-ordered jobs.
Timing uncertainty does not capture all machine/order effects. Bootstrap
intervals are descriptive and not adjusted for six-target selection. No
application decision value, profitability, novel uniqueness or AMM success
is established by these results.
