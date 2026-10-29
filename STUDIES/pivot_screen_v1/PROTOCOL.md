# Four-candidate pivot screen

Frozen before main execution. Exploratory synthetic triage, not a confirmation,
real-world economic validation, SBC study, or proof of sampler uniqueness.

Four candidates: hierarchical segment-level Bernoulli A/B decisions; hurdle
lognormal revenue A/B; batched logistic contextual Thompson sampling; hierarchical
negative-binomial inventory ordering. Five fixed scenarios per candidate: easy,
near tie (inventory: homogeneous demand), sparse, heterogeneous, misspecified.
20 independent datasets/trajectories per scenario, 400 planned replicates total.
Treatment direction is randomized across A/B and bandit replicates. Parameters,
sample sizes, priors and misspecifications are fixed in models.py.

All inference targets have proper normal priors in unconstrained coordinates.
Hierarchical pooling scales are fixed, not learned. Revenue positive amounts are
lognormal, with sigma .2+1.6*logistic(eta), eta~Normal(0,1), so predictive revenue
means are finite. This is a bounded prior, not a transformed uniform prior; no
extra Jacobian is appropriate. Inventory uses known dispersion 5; misspecification
generates dispersion 1. Revenue misspecification adds a 5% fivefold amount mixture;
hierarchical A/B adds cluster overdispersion; bandits omit a quadratic arm interaction.
These are deliberately small models; no claim they exhaust the possible pivots.

Actions: choose an arm by posterior expected revenue/conversion (separately per
segment for hierarchical A/B); order the posterior predictive 80th percentile
with shortage cost 4 and surplus cost 1; Thompson-sample 80 bandit decisions after
20 common randomized observations, in four batches of 20. Each bandit policy has
its own history and observes only selected-arm outcomes. Common contexts and
potential outcomes reduce paired evaluation variance; truth is used only to
calculate regret. Initial 20 decisions are excluded equally from policy regret.

Baselines: separate/pooled Beta(1,1) conversion posteriors; sample mean/bootstrap
revenue; empirical demand quantile and shrinkage NB; Laplace Thompson sampling and
logistic UCB. Laplace inference is also included for all static models. NUTS and
WALNUTS use the same target and Python callback interface, four chains, 500 warmup,
750 retained draws, target acceptance .9, maximum depth 9, one core per job.
Neither callback timing establishes optimized native performance. Common framework
imports are recorded separately before method timers; cold process runtime is also
retained. The pilot included first-import overhead in the first NUTS call; this
accounting was corrected before the main freeze. Cheap methods
remain competitors, not merely implementation checks. NUTS is a comparator, not
an assumed exact oracle. Known generating truth determines decision regret.

Screen diagnostic qualification requires all-coordinate R-hat <=1.05, bulk/tail
ESS >=100, no retained divergences and no depth-cap hits. Also report strict
reference qualification (R-hat <=1.01, ESS >=400); the looser screen gate cannot
establish posterior fidelity. Preserve per-functional summaries, all failures,
raw retained draws and timing. Fixed budgets are not matched-precision speed tests.

For static candidates report paired regret improvement over each baseline and
Laplace; for bandits report whole-trajectory expected regret comparisons. Divide
regret by oracle expected reward (A/B/bandit) or oracle expected inventory cost
for dimensionless display, but do not rank different markets by these numbers
as though they had equal business value. Bootstrap entire independent replicates,
not individual sequential actions: 10,000 paired replicates, fixed analysis seed
549100000, descriptive 95% intervals. Missing/failed slots retain denominator;
available-case means are labeled, with no silent fallback or successful-only timing.
No multiple-comparison-adjusted discovery claim is permitted.

Promotion is a hypothesis for a later fresh study, not a screen-level success:
look for >=95% successful screen-qualified WALNUTS runs, a useful NUTS/reference
decision advantage over the strongest observed cheap competitor, small WALNUTS
decision degradation, and a plausible computational opportunity. A provisional
practical effect is 10% relative reduction in mean decision regret; absolute
effects and uncertainty must accompany ratios, and near-zero denominators are
not promoted. No isolated favorable scenario is enough; show all five. Because
the screen does not match precision, any efficiency claim needs a second stage.

Resource bounds: existing 16-core instance only; up to 12 jobs, each one CPU,
1 GiB RSS, 32 MiB output and 900 seconds. Admission stops after two hours or below
1 GiB free disk; running bounded jobs finish. Each subprocess gets an isolated
XDG cache to avoid the prior ArviZ cache race. Freeze source hashes and planned
job identities before launch. A separate four-job sparse-case timing pilot uses
disjoint seeds and is excluded from inference. Main seed blocks start 529100000,
pilot blocks 539100000, candidate stride 1000000, scenario stride 100000,
replicate stride 1000; within-replicate offsets stay below 1000.

Implementation validation: analytic gradients versus finite differences across
all 20 model/scenario combinations; independent SciPy likelihood differences;
inventory expected loss versus explicit probability summation and quantile
optimality; disjoint seed blocks; future-outcome mutation cannot affect bandit
training target. Small conjugate/one-dimensional calibration checks and broader
SBC would be required before a strong posterior-accuracy claim.
