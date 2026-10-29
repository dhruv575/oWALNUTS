# Four-pivot screening results

**None of these small formulations establishes a reason to choose WALNUTS over
cheap approximate inference.** Hierarchical A/B and inventory show value from
modeling, but Laplace obtains similar decisions at far lower measured cost.
Revenue A/B supplies little discrimination. Contextual Thompson sampling loses
to logistic UCB in this short-horizon screen. These are synthetic triage results,
not a dismissal of every possible formulation in the four application areas.

## What ran

The protocol and source were committed at `2e92ea94` before the main run. Four
candidates x five fixed scenarios x 20 independent replicates = 400 planned
replicates. All 400 completed; no resource timeouts or missing result files.
Main campaign wall time: 203.49 seconds on the existing EC2 instance, up to
12 one-core jobs. Four separate sparse-case pilots are excluded from results.
The main run includes 1,400 sampler fits (NUTS and WALNUTS), each four chains,
500 warmup and 750 retained iterations. Bandit policies make 80 decisions in
four batches following 20 common randomized observations.

Six implementation/inference tests and two analysis tests passed. They cover
all model/scenario gradients, likelihood differences against SciPy, exact
inventory loss calculations, seed separation, future-outcome isolation, both
samplers against one-dimensional posterior quadrature, and paired failure
accounting. This is not a broad simulation-based calibration exercise.

## Decision quality

Regret is expected loss relative to the known generating-model optimal action.
Lower is better. Units differ by row and must not be compared across domains.
Scenario weights are fixed at one fifth each.

| Candidate | WALNUTS mean regret | Laplace mean regret | Other relevant baseline | Interpretation |
|---|---:|---:|---|---|
| Hierarchical A/B | 0.007279 conversion probability | 0.007214 | Separate Beta: 0.009037; pooled Beta: 0.010298 | Partial pooling can help; sampling has no demonstrated advantage over Laplace |
| Revenue A/B | 0.658735 revenue units/customer | 0.658241 | Sample mean: 0.718067; bootstrap: 0.658735 | Apparent sample-mean gain is concentrated in one replicate; not a robust sampler use case |
| Contextual bandit | 0.028107 expected reward/decision | 0.029792 | UCB: 0.022092 | UCB has lower regret than both sampled policies in this screen |
| Inventory | 1.105235 cost units/item | 1.117851 | Empirical quantile: 1.883784; shrinkage NB: 2.055733 | Strongest modeling opportunity here, but almost all observed benefit is available through Laplace |

Paired WALNUTS advantage over Laplace (Laplace regret minus WALNUTS regret),
with exploratory stratified 95% bootstrap intervals:

| Candidate | Mean advantage | 95% interval |
|---|---:|---:|
| Hierarchical A/B | -0.0000651 | [-0.0002304, 0.0000565] |
| Revenue A/B | -0.0004946 | [-0.0014838, 0.0000000] |
| Contextual bandit | 0.0016849 | [-0.0006402, 0.0039603] |
| Inventory | 0.0126158 | [-0.0040622, 0.0290037] |

None supplies a clearly positive incremental benefit over Laplace. Inventory's
point estimate is approximately 1.1% of Laplace regret, below the provisional
10% practical-improvement target. Against UCB, WALNUTS's advantage is negative:
-0.0060153 [-0.0085116, -0.0037316]. The screen is exploratory and intervals are
not adjusted for the many candidate/scenario/method comparisons.

Hierarchical WALNUTS improves over separate Beta by 0.001758 [0.000380, 0.003141]
and over pooled Beta by 0.003019 [0.001835, 0.004173], but the benefit is not uniform:
pooled Beta is best in the easy global-effect cases, separate Beta is best in
the heterogeneous cases, and neither fact licenses choosing a baseline after
seeing the true scenario. Inventory WALNUTS improves over empirical quantiles by
0.778549 [0.592257, 0.964629], with Laplace retaining almost the same gain.

The revenue bootstrap is deliberately disclosed as weak evidence: its expected
bootstrap mean equals the sample mean analytically. Finite 2,000-resample Monte
Carlo changed one action (heterogeneous replicate 11), avoiding a true regret
of 5.933120 on that replicate. This alone accounts for the aggregate difference
between bootstrap and sample-mean policies. It is not evidence of a systematic
bootstrap improvement. NUTS and WALNUTS made the same revenue decisions in all
100 runs; Laplace differs only slightly on the near-tie cases.

## Diagnostics and posterior comparisons

WALNUTS passes the loose screening gate on all 400 replicates. NUTS passes on
399/400: inventory/easy/replicate 3 has maximum R-hat 1.05511 and minimum ESS
76.24, without divergences or depth hits. Its comparison is retained as a
failure, not rerun; NUTS available-case tables disclose n=99 for inventory.
WALNUTS/Laplace inventory comparisons use all 100 and avoid that denominator issue.

The stricter reference gate is much less favorable for inventory: only 17/100
NUTS and 26/100 WALNUTS replicates have all-coordinate R-hat <=1.01 and bulk/tail
ESS >=400. All 100 replicates qualify strictly for both samplers in each of the
other three candidates (all four sequential fits required for a bandit replicate).
Thus the inventory run is not a high-fidelity reference benchmark. Its known-truth
decision scores remain computable, but posterior accuracy and precision-matched
speed need further work. The correlated global/intercept effects are a plausible
mixing issue, not a verified root cause.

Among static cases with a strict NUTS reference, maximum decision-functional
mean differences exceed three combined MCSEs in 2/100 hierarchical cases and
1/100 revenue cases; none of the 17 strict inventory cases exceeds three.
These are unadjusted maximum-over-functionals diagnostics, not hypothesis tests
or proof of equality. Bandit policies evolve different histories; their later
posteriors cannot be compared as though they condition on identical data.

## Measured costs

Median method times in seconds, including method inference/diagnostic/decision
work, excluding common framework initialization:

| Candidate | NUTS | WALNUTS | Laplace |
|---|---:|---:|---:|
| Hierarchical A/B | 1.485 | 1.394 | 0.00608 |
| Revenue A/B | 1.094 | 0.852 | 0.00380 |
| Contextual bandit, four updates | 3.220 | 2.320 | 0.00779 |
| Inventory | 1.595 | 1.973 | 0.01075 |

These are shared-host, Python-callback, fixed-draw-budget measurements. They do
not establish optimized native performance or a matched-accuracy speedup. In
particular, WALNUTS is slower than NUTS on the tested inventory target, and both
are far costlier than Laplace. The pilot's first-import timing penalty was
identified and corrected before the main freeze; pilot timing is not pooled.

## What to pursue

1. **Inventory: retain as a modeling candidate, not yet a WALNUTS candidate.** A
   future study would need an independently justified setting where posterior
   shape changes the stock decision and Laplace fails, plus a stronger reference.
   Fixed known dispersion and uncensored demand make this screen intentionally
   simpler than many actual inventory problems.
2. **Hierarchical A/B: retain as a second modeling candidate.** This screen fixes
   pooling scales and uses simple segment decisions. Learned pooling, multiple
   outcomes or explicit continuation decisions are hypotheses for fresh tests,
   not claims supported here. Do not add complexity solely to make Laplace lose.
3. **Revenue A/B: deprioritize this formulation.** Little decision separation,
   bounded lognormal-scale assumptions, and one influential replicate do not
   justify a large follow-up batch.
4. **Contextual bandits: deprioritize this short-horizon formulation.** UCB is
   cheaper and better in aggregate here. Longer horizons, a different update
   cadence or other structures require fresh frozen experiments.

None currently meets the combined decision-value and computational-advantage
case for promoting WALNUTS. A narrow formulation screen should not be generalized
into a claim that these domains can never benefit from posterior sampling.

## Reproduction and preservation

`SUMMARY.json` contains all five scenario results, all baseline contrasts,
qualification denominators and timing summaries. `INPUT-HASHES.json` binds the
400 case reports. The full archive includes generated datasets, retained raw
draws, reports, diagnostics, failures, source and control manifests. The main
execution source hashes match its frozen manifest. Pilot manifests are retained;
the source directory in the archive is the main-run version, including the
documented pre-main timing/resource-accounting changes.

Remote root: `/home/ubuntu/lanes/pivot-screen-20261029`.
Local raw archive: `target/pivot-screen-evidence-v1.tar.gz`, 238,904,495 bytes,
SHA256 `796c1c1260b2e4b27f5611379468ad9c384984590cbc3829b480d817798ef38f`.
`verify_archive.py` checks the whole archive, all 3,853 manifest members, and
main frozen-source identity without extracting paths. See ARCHIVE-VERIFICATION.json
for the actual verification receipt. The local AWS session expired, so S3 upload
is pending. No EC2 evidence was reclaimed; both local and EC2 copies are retained.

Run `supervisor.py NEW_RUN_DIRECTORY main` in the recorded pinned runtime to
repeat the frozen simulation schedule (the original seeds reproduce exposed
screening data, not fresh confirmation). Run `analyze.py RUN_DIRECTORY NEW_OUTPUT`
to regenerate summaries. All bootstrap resampling is paired at the independent
replicate level and stratified by the five fixed scenarios. Synthetic truth,
proper target priors, algorithmic diagnostics, business relevance and real-world
profitability are separate claims throughout.
