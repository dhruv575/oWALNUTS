# Preregistration — delta2_sidechecks_v1 (WP37A)

Frozen 2026-09-04 before any study harness, study implementation, build, or
sampling. The source baseline is commit
`443e86a3bb053ed1a2a1560caca5266427a3b35c` (tree
`b534495caf9fd8de5aa8f76a6d84be60a79e52eb`). `protocol.json` is the
machine-readable protocol. This scaffold contains no executable study code and
no evidence.

## Question and scope

WP34 found that fixed `max_error` / `delta = 2` was a near miss on ordinary
posteriors, but it did not supply enough fresh pure-Rust side-target evidence
to justify implementing a rule that adapts `delta` toward 2. This study asks
only whether that next experiment is safe enough to start.

This is a **qualification gate**, not a sampler-default decision. Passing every
gate below authorizes a separately preregistered adaptive-delta implementation
study. It does not authorize changing a default, and fixed `delta = 2` cannot
become the default from this study. If any gate fails or is inconclusive,
fixed 2 and an adaptive rule permitted to reach 2 are rejected; no
adaptive-delta implementation is started, and the next kernel work is the
cheaper reverse-coarsening check.

All targets are analytic, in-process Rust `Target` implementations. BridgeStan,
Stan, Python target callbacks, subprocess target servers, and posteriordb are
out of scope. Historical studies supply settings and motivation only; none of
their evidence cells or seeds enters this study's estimands or decisions.

## Frozen arms

There are exactly two arms:

| arm | frozen setting |
|---|---|
| `fixed1` | incumbent `Tuning::default()` with `max_error(1.0)` made explicit |
| `fixed2` | the same configuration with only `max_error(2.0)` |

Both arms use the final defaults at the source baseline: `h0 = 0.5`, depth 10,
one minimum micro-step, eight refinement levels, `MomentumSum`, divergence
threshold 1000, adapted diagonal metric from identity with Stan
regularization, cached initial evaluation where the `Sampler` facade provides
it, the final warmup exhaustion rule, worst-case admission, and **no chain
rescue** (`DEFAULT_CHAIN_RESCUE = None`). The adaptation target is 0.8 except
on the historical strict Eight Schools track, where it is 0.95. No arm may
inherit a later default: the harness must assert and serialize every effective
setting before evidence starts.

No adaptive-delta arm, pilot arm, rescue arm, alternate U-turn rule, or
per-target tuning is permitted.

## Pure-Rust targets and exact settings

### Neal's 10-D funnel

The target and run settings are the WP28/WP34 defaults check:

- `omega ~ Normal(0, 3)` and nine
  `x_i | omega ~ Normal(0, exp(omega / 2))`, equivalently conditional variance
  `exp(omega)`;
- four fixed starts, `omega in {-3, -1, 1, 3}` and every `x_i = 0`;
- four chains on four threads, 2,000 warmup and 20,000 retained per chain;
- current sampler defaults, adapted diagonal metric, target acceptance 0.8;
- analytic values
  `P(omega < -5) = 0.0477903522728147`,
  `P(omega < -6) = 0.0227501319481792`, and `Var(omega) = 9`.

For every seed and arm report both tail probabilities and their indicator
MCSEs, omega variance, rank-normalized split R-hat, bulk and tail ESS, retained
and warmup target calls, final step and metric, divergences, invalid-evaluation
stops, refinement exhaustions, depth caps, the full refinement-level-built
histogram, and reverse-coarsening rejections/stops. Across seeds report totals,
paired differences and ratios, and pooled tail/variance estimates. Pooled tail
MCSE and z scores are descriptive; they are not the decision rule.

The pooled estimate combines all 12 seed cells in an arm. Its uncertainty is
also reported from fixed 500-draw within-chain batches (12 seeds x 4 chains x
40 batches), without treating a result-driven subset as the pool.

### Strict noncentered Eight Schools

The target and track are copied from
`eight_schools_v9_rebench_v1` and the WP34 side check:

- unconstrained state `(mu, log_tau, z_1..z_8)`, with the same density,
  observations, scales, and transformations;
- fixed starts `log_tau in {-2, -1, 0, 1}`, all other coordinates zero;
- four sequential chains, one thread, 1,000 warmup and 1,000 retained;
- `h0 = 0.3`, depth 8, one minimum micro-step, eight refinement levels,
  divergence threshold 1000, target acceptance 0.95, adapted diagonal metric
  from identity, the final Stan metric regularization and warmup exhaustion
  rule, no rescue, the `walnutpie` sampling boundary/no initial-evaluation
  cache, and callback cap 10,000,000;
- six functionals: `mu`, `tau`, `mean_theta`, `sd_theta`, `theta_1`, and
  `theta_8`.

Each seed/arm is run in three separate timing repetitions. Retained draw bytes,
total and phase target-callback counts, final tuning and metric hashes, and
all retained diagnostics must be bit-identical across the three repetitions;
only timing and process metadata may differ. Median wall time is reported but
is not gated.

For each functional report rank R-hat, bulk and tail ESS, mean, SD, MCSE, and
bulk/tail ESS per callback. Also report all health counters, final tuning and
the six-functional minimum bulk ESS/callback.

### Analytic 100-D Gaussian

The WP28 cost/control target is the 100-D standard Gaussian with
`Init::uniform()` (`uniform(-2, 2)`, seeded), four chains on four threads,
1,000 warmup and 1,000 retained, and the current sampler defaults with target
acceptance 0.8. For every coordinate report mean, variance, rank R-hat, bulk
ESS and tail ESS. Report mean bulk ESS over coordinates per **retained** target
call, the WP28 work statistic, plus all health counters and final tuning.

## Fresh paired seeds and cells

The contiguous fresh range is **93101 through 93112**, with no skipped
numbers. Funnel and Gaussian use all 12 seeds. Strict Eight Schools uses
93101 through 93106, each with three timing repetitions. The same seed and
fixed starts or seeded initializer are used in both arms.

Before this scaffold was written, this exact standalone whole-number search
was run against baseline `443e86a3bb053ed1a2a1560caca5266427a3b35c`:

```powershell
$pattern = '(?<![0-9A-Za-z_.])(?:93101|93102|93103|93104|93105|93106|93107|93108|93109|93110|93111|93112)(?![0-9A-Za-z_.])'
git grep -n -P $pattern 443e86a -- . ':(exclude)**/artifacts/**'
```

Result: **no matches**. The alphanumeric/underscore/dot lookarounds prevent a
digit sequence inside a longer integer, decimal, exponent, identifier, or
hexadecimal checksum from being mistaken for a whole-number token. These
seeds are not external-study evidence seeds and must not be supplemented or
replaced.

There are **84 planned one-shot child cells**:

- funnel: 12 seeds x 2 arms = 24;
- Eight Schools: 6 seeds x 2 arms x 3 repetitions = 36;
- Gaussian: 12 seeds x 2 arms = 24.

Targets run in the order funnel, Eight Schools, Gaussian; seeds ascend. For
funnel and Gaussian, zero-based even seed indices run `fixed1,fixed2` and odd
indices run `fixed2,fixed1`. For Eight Schools, arm order is
`fixed1,fixed2` when `(seed_index + repetition_index)` is even and reversed
when it is odd.

## Process, provenance, and no-rerun contract

Every planned cell runs in a fresh child process. Before launch, the parent
must create an immutable create-new marker keyed by target, seed, arm and
repetition. A marker or process record forbids a second launch. Every launch,
including a timeout, crash, setup error or malformed result, receives a
durable process record with command, timestamps, stdout/stderr hashes, timeout
state, signed/unsigned/hex exit status, raw-result state and SHA-256. The child
atomically publishes and flushes its result before teardown. A nonzero exit
after a complete result is still a process failure.

There are no result-driven reruns. A returned sampler error in an otherwise
valid process is a valid failing result. A process fault, missing cell,
identity mismatch, malformed result, protocol mismatch or implementation bug
after the first evidence launch makes the corresponding gate fail and the
study non-qualifying; it does not authorize replacement evidence.

Before the first evidence launch, a committed provenance record must bind the
baseline, preregistration and protocol UTF-8/LF-normalized SHA-256 values,
harness source commit and tree, complete release-binary SHA-256, serialized
effective arm/target configs, `rustc -Vv`, Cargo lockfile hash, OS/CPU
metadata, and the ordered 84-cell manifest. Evidence outputs are append-only.
This is intentionally simple source/binary/config/checksum provenance, not an
external model or data pipeline.

## Frozen gates

All comparisons use all process-valid preregistered cells; there is no seed,
chain, coordinate, functional or repetition selection.

### F — funnel gates

**F1 Completeness.** All 24 launch/process records exist and all 24 cells are
process-valid, schema-valid, finite, and configuration-authenticated.

**F2 Pooled substantive accuracy and arm agreement.** For each arm, using all
12 seeds:

- `|P(omega < -5) - 0.0477903522728147| <= 0.006`;
- `|P(omega < -6) - 0.0227501319481792| <= 0.004`;
- `|Var(omega) - 9| <= 1.0`.

In addition, absolute `fixed2 - fixed1` pooled differences are at most 0.004
for `P(omega < -5)`, 0.003 for `P(omega < -6)`, and 0.75 for omega variance.
These fixed substantive bounds, not twelve simultaneous `|z| <= 2` tests,
decide pooled accuracy.

**F3 Gross per-seed safety.** Every `fixed2` seed has finite draws and
diagnostics, no sampler error, zero retained divergences, rank R-hat <= 1.05,
absolute error <= 0.025 for `P(omega < -5)`, absolute error <= 0.015 for
`P(omega < -6)`, and omega variance in `[5, 13]`.

**F4 Health-count noninferiority.** A seed is funnel-healthy when it has
finite draws, no sampler error, rank R-hat <= 1.01, omega bulk ESS >= 400,
omega tail ESS >= 400, zero retained divergences, zero retained invalid stops,
and zero retained refinement exhaustions. `fixed2` must have at least 9 of 12
healthy seeds and at least as many healthy seeds as `fixed1`.

**F5 Counter nonregression.** Summed across all 12 seeds, `fixed2` has no more
retained divergences, invalid stops, or refinement exhaustions than `fixed1`.
Refinement-level-built histograms and reverse-coarsening rejection/stop totals
and paired ratios are mandatory reported mechanism estimands, but ordinary
refinement and reverse-coarsening events are not themselves failures.

### E — strict Eight Schools gates

**E1 Completeness and identity.** All 36 launch/process records exist and all
cells are valid and authenticated. For every seed/arm, all three repetitions
are bit-identical under the fields defined above.

**E2 Six-functional agreement.** After identity is established, repetition
zero supplies one nonduplicated draw set per seed/arm. Pooling all six seeds,
every functional satisfies both:

- `|mean_fixed2 - mean_fixed1| <= 0.10 * pooled_SD + 2 * pooled_MCSE`;
- `|SD_fixed2 - SD_fixed1| <= 0.15 * pooled_SD + 2 * pooled_MCSE`.

`pooled_SD = sqrt((SD_fixed1^2 + SD_fixed2^2) / 2)` and
`pooled_MCSE = sqrt(MCSE_fixed1^2 + MCSE_fixed2^2)`.

**E3 ESS/callback.** For each seed/arm, the score is the minimum over the six
functionals of bulk ESS divided by total callbacks started, warmup included.
The geometric mean over the six paired `fixed2/fixed1` seed ratios must be at
least 0.90. Tail ESS/callback ratios are reported.

**E4 No new failure.** A seed/arm is strict-track healthy when every
functional has bulk and tail ESS >= 400 and rank R-hat <= 1.01, all draws are
finite, divergence and maximum-depth rates are each <= 0.01, retained
refinement exhaustions and invalid stops are zero, and there is no sampler
error. `fixed2` must be healthy on at least 5 of 6 seeds, its healthy count
must be at least `fixed1`'s, and there may be no seed on which `fixed1` is
healthy but `fixed2` is not. `fixed2` may introduce no process, sampler,
nonfinite, divergence, invalid-stop, or refinement-exhaustion failure absent
from the paired `fixed1` seed.

### G — Gaussian gates

**G1 Completeness.** All 24 launch/process records exist and all cells are
process-valid, schema-valid, finite, and configuration-authenticated.

**G2 Coordinate accuracy and agreement.** Pooling all 12 seeds within each
arm, every one of the 100 coordinates has absolute mean <= 0.08 and variance
in `[0.85, 1.15]`. For every coordinate, the absolute `fixed2 - fixed1`
difference is <= 0.08 for means and <= 0.12 for variances.

**G3 ESS/call.** For each seed/arm compute mean coordinate bulk ESS divided by
retained target calls. The ratio of the `fixed2` seed median to the `fixed1`
seed median must be at least 0.90. The median of paired seed ratios and all
tail-ESS work ratios are reported.

**G4 No health regression.** A seed/arm is Gaussian-healthy when every
coordinate has bulk and tail ESS >= 400 and rank R-hat <= 1.01, all draws are
finite, retained divergences, invalid stops and refinement exhaustions are
zero, and there is no sampler error. `fixed2` must be healthy on at least 11
of 12 seeds, its healthy count must be at least `fixed1`'s, and there may be no
seed on which `fixed1` is healthy but `fixed2` is not. Summed candidate
divergence, invalid-stop and refinement-exhaustion counts may not exceed the
incumbent counts.

## Mechanical decision

The study returns `QUALIFIED_FOR_SEPARATE_ADAPTIVE_DELTA_STUDY` if and only if
F1–F5, E1–E4, and G1–G4 all pass. That outcome permits writing a new
preregistration and then implementing its adaptive-delta candidate. It makes
no default change and gives fixed 2 no default-selection status.

Any failed, incomplete or inconclusive gate returns
`REJECT_FIXED2_AND_ADAPTIVE_TO_2`; no adaptive-delta implementation proceeds,
and the research program moves to the cheaper reverse-coarsening check. All
84 planned outcomes and every gate must be reported regardless of result.

## Predictions

1. Both arms meet the pooled funnel substantive bounds; `fixed2` reduces
   refinement and reverse-coarsening counts without losing healthy seeds.
2. Strict Eight Schools repetitions are bit-identical, six-functional
   agreement holds, and `fixed2/fixed1` minimum-bulk-ESS/callback is at least
   0.90.
3. Both Gaussian arms meet coordinate accuracy, and fixed 2 retains at least
   0.90 of the incumbent's WP28 ESS/call statistic without a health loss.
4. The predicted decision is qualification for a separate adaptive-delta
   study. This prediction does not weaken any gate or authorize an
   implementation before the side-check result is frozen.
