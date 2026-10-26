# WP66 `funnel_tail_deficit_v1` — preregistration

Frozen 2026-10-25, committed before the first evidence cell. `protocol.json`
is the machine-readable copy and wins on any discrepancy.

**WP number.** The highest WP in `README.md`, `wiki/` and the ledger at
`main` `a49df800` is WP63. Two concurrent lanes on the shared box take WP64
and WP65, so this study is **WP66**.

## Why

WP53 (`STUDIES/funnel_defaults_30seed_v1`, 30 fresh seeds, 4 x 2,000/20,000)
found that the shipped default under-estimates P(omega < -5) on Neal's 10-D
funnel: the pooled value is 0.0458 +/- 0.0014 against an exact 0.0478, the mean
house z is -0.42, and 4/30 seeds fall beyond |z| 2, all of them low. The misses
are silent. `delta = 2` shows the same deficit (0.0455 +/- 0.0010), and WP49's
12 seeds did too (0.0451). P(omega < -6) is 7 % low and the omega variance is
8.82 against 9. WP53 left the source open, suspecting step or metric
adaptation. This study asks why the deficit exists, and whether a single
setting removes it without hurting the posteriordb record.

## Library under test

`main` `a49df800` (0.3.0 plus docs), unchanged. The kernel revision is
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. The defaults that matter
here are `UTurnRule::MomentumSum`, `DiagonalMetricRegularization::Stan`,
`delta` 1, eight refinement levels (micro step `h/128`), depth 10, dual
averaging to 0.8 and `RejectLeaf`. Every arm is a public builder setting, and
no library source changes.

## Machine

Everything runs on AWS EC2 c7a.4xlarge `owalnuts-bench` (Ubuntu 24.04,
Rust 1.88) in lane 3. Every build and cell is pinned with `taskset -c 8-11`,
with `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`. Three other lanes are
active on cores 0–7 and 12–15 and share L3 and memory bandwidth, so all wall
numbers are labelled "pinned, co-tenanted". Tail mass, ESS per gradient and
pass counts are unaffected by co-tenancy.

## Hypotheses, diagnostics and candidates

Each hypothesis comes with one diagnostic recorded from the draws and one
candidate setting.

| | mechanism | diagnostic recorded | signature in the default arm (frozen) | candidate arm |
|---|---|---|---|---|
| **H1** step adaptation | Dual averaging to 0.8 sizes `h` for the bulk. In the neck that `h` is under-resolved: neck transitions are energy-error limited and short, so the chain enters and explores the neck too rarely. | For retained transitions classified by the starting state's omega (bulk >= -5, neck [-7, -5), deep < -7): the energy-acceptance proxy `min(1, exp(-max\|dH\|))`, moved fraction and selected level. Spearman of per-chain P5 against log adapted `h` over 120 chains. | neck proxy <= bulk proxy - 0.10, **or** \|Spearman\| >= 0.20 | `accept0.9`: `Adaptation::DualAveraging { target_accept: 0.9 }` |
| **H2** refinement ceiling | Eight levels (`h/128`) are too few in the deep neck at the adapted `h`. Leaves there take the top level or exhaust, the two-sided Stop rule ends the orbit, and the deep neck is under-entered. | Per class: top-level selections and RefinementExhausted stops. The tail profile P(omega < c)/exact for c = -1..-10. | (top-level + exhaustion stops) >= 1 % of deep-class transitions, **and** the relative deficit at c = -8 exceeds that at c = -5 | `levels10`: `Tuning::default().max_refinement_levels(10)` (`h/512`) |
| **H3** U-turn rule | The post-hoc default `MomentumSum` rule (Stan's criterion, one momentum per macro leaf, with no `walnutpie` oracle) stops neck orbits early or interacts with variable refinement. | Per class: tree-depth histogram, mean depth, stop reasons, U-turn stops at depth <= 3, orbit macro length. | neck share of U-turn stops at depth <= 3 >= 1.5x bulk's, **or** neck mean depth differs from the `endpoint` arm's by >= 0.5 | `endpoint`: `Tuning::default().kernel_options(KernelOptions::default())` (the frozen, oracle-tested `v10` endpoint rule; exhaustion rule unchanged) |

The task's fourth example, best-of-16 starts biasing the first window, cannot
act here. The house funnel check passes explicit starts (omega in
{-3, -1, 1, 3}, x = 0), as WP53 did.

## Blocks and cells (strictly sequential, one process per cell, never rerun)

- **A (core).** 4 x 2,000/20,000 on the funnel. Arms `default` (control),
  `accept0.9`, `levels10` and `endpoint`. 30 fresh seeds, 668101–668130. Order:
  seeds ascending, and within a seed the arms in that order. 120 cells.
- **S (sanity arm).** `default` at 4 x 2,000/**80,000**, 10 fresh seeds,
  668201–668210, to separate bias from variance. 10 cells.
- **C (cost side check).** WP28's two ordinary targets: noncentred Eight
  Schools with explicit starts, and a 100-D Gaussian with `Init::uniform()`.
  Four arms x 10 seeds (668301–668310) x 4 x 1,000/1,000. Order: seeds, then
  targets (eight, gauss100), then arms. 80 cells.

An errored cell is recorded as an error file and counts as a failure
(|z| > 2, not removed). A cell is rerun only if the host killed the driver
mid-cell, and that rerun is recorded as a deviation.

Seeds were checked with `git grep -lwE` over every tracked file of
`a49df800`, artifacts included, and with the same regex over every
`protocol.json` / `PREREGISTRATION.md` in `C:\dev\owalnuts-wt\*\STUDIES`:
neither found a hit. The ranges 6601xx (660125 occurs inside a float) and
6641xx–6671xx (hits) were rejected.

## Harness: WP53's, copied and parametrised

`src/bin/funnel.rs` keeps WP53's density, run configuration, P5 estimate,
MCSE z, P6, batch-means z, omega variance, ESS / R-hat and `chain_warnings`
verbatim. It makes these changes:

1. The arms are those in `src/lib.rs`, replacing the three `delta` arms.
2. Retained `ChainOutput::diagnostics()` are aggregated by the starting
   state's omega class (bulk / neck / deep). For each class it records the
   depth histogram, the stop reasons, U-turn stops at depth <= 3, the selected
   level histogram, the top-level count, exhaustion stops, the moved fraction,
   the energy-error mean and quantiles, the energy-acceptance proxy, the
   refinement attempts, reverse-coarser rejections, the orbit macro length and
   the target evaluations per transition.
3. Per chain it records warmup acceptance-statistic means (all warmup, the
   last slow window, the last 50) and the warmup top-level / exhaustion
   counts. Warmup positions are not available, so the warmup neck cannot be
   classified.
4. Tail-mass profiles: P(omega < c) for c = -1..-10 and P(omega > c) for
   c = 1..10.
5. Per chain: the tail fraction by retained quarter, neck entries, excursion
   count / mean / max, min / max omega and the first retained omega.
6. The P5 estimate over the first min(draws, 20,000) retained draws per chain
   (the prefix).
7. Wall time is labelled `pinned_cotenanted`. The Linux binary path is used.
   A side binary, `src/bin/side.rs`, carries WP28's Eight Schools and
   Gaussian code.
8. `run_study.py` is WP53's driver with protocol-driven blocks A/S/C. The
   analysis adds between-seed s.e., paired seed differences, the D/E rules and
   the signatures.

The acceptance statistic itself is captured only in warmup (the sampler does
not expose `RunConfig::with_acceptance_capture`). For retained transitions,
"acceptance in the neck" is therefore the energy proxy plus the moved
fraction.

## Decision rules (frozen)

Statistic: per arm, the pooled P5 is the mean of the 30 per-seed estimates,
and its between-seed s.e. is sd/√30.

**A candidate X removes the deficit iff all of D1–D4 hold:**

- **D1:** |pooled P5(X) − 0.04779| <= the between-seed s.e. of X.
- **D2:** the mean house z of X is in [−0.2, 0.2].
- **D3:** at most 4 seeds have |z| > 2 (WP53's default count; errored cells
  count), **and** the pooled retained divergence rate is below 1e-3.
- **D4:** there is no library change (`git diff a49df800 -- src/ Cargo.toml
  Cargo.lock` at the repository root is empty at the build commit), and
  `cargo test --release --test kernel_fingerprint` passes on the box build.
  None of the arms is a kernel change. A passing arm is labelled a *candidate
  default change* and is not applied.

**A candidate that removes the deficit is recommended for a posteriordb
confirmation iff E1 and E2 hold.** Otherwise it is reported as "removes the
deficit, not a default candidate".

- **E1 (block C):** on each of Eight Schools and the 100-D Gaussian, the
  geomean over seeds of X's min-bulk-ESS-per-gradient divided by the
  default's (paired by seed) is >= 0.95, and X has at least as many
  house-healthy cells as the default minus 1.
- **E2 (ledger):** no posteriordb geomean loss of 4 % or more is recorded for
  the same setting or a weaker form of it. This was assessed before the
  freeze:
  - `accept0.9` **fails**: WP40 sweep 4 gives target 0.85 alone at 0.958x
    over the 17 models, and sampling-only costs of 0.89–0.94x.
  - `endpoint` **fails**: the shipped MomentumSum + Stan pair is 1.51x the
    endpoint pair (WP31/32), and endpoint with Stan regularisation gives
    0.08x on `earnings`.
  - `levels10` **passes**: there is no posteriordb record, and WP28 shows the
    level cap is not reached on ordinary targets.

**Hypothesis support.** H_k is SUPPORTED iff (i) its candidate raises the
pooled estimate over the paired default, with the mean seed difference > 0
and paired t >= 2.0, **and** (ii) its signature holds. If only (i) holds, the
reading is "candidate helps, mechanism not shown". If only (ii) holds, it is
"signature present, not causal at this budget". If neither holds, the
hypothesis is NOT SUPPORTED.

**Replication.** The deficit replicates iff the block-A default's pooled P5
is more than 1 s.e. below exact. If it does not replicate, the verdict says so
first.

**Sanity arm S.** Let r = 1 − pooled/exact.

- **FINITE-RUN** iff r_S < r_A(default)/2 and |pooled_S − exact| <= s.e._S.
- **PERSISTENT-BIAS** iff r_S >= r_A/2 and pooled_S < exact − 1.5 s.e._S.
- **INCONCLUSIVE** otherwise. The expected s.e. is about 0.0012, so the arm
  can only separate a deficit that halves.

The descriptive companion compares each S seed's first 20,000 draws with its
last 60,000.

**No default is changed in this study under any outcome.**

## Predictions (written before any cell, including the pipeline check)

- **P1:** the default replicates. Pooled P5 is in [0.0440, 0.0475] and mean z
  is in [−0.6, −0.1].
- **P2:** the deficit is specific to the lower tail. The default's pooled
  P(omega > 5) is within 1 s.e. of 0.0478.
- **P3:** H2 is not supported. Top-level plus exhaustion stops are under 1 %
  of deep transitions, and `levels10` is within 1 paired s.e. of the default.
- **P4:** `accept0.9`'s median adapted `h` is 20–50 % below the default's.
- **P5:** H3 is not supported. `endpoint` is within 1 paired s.e. of the
  default.
- **P6:** no candidate passes D1–D4.
- **P7:** S reads INCONCLUSIVE or FINITE-RUN.

## Disclosed non-evidence work before the freeze

1. **A post-hoc look at WP53's committed cells**, made before the hypotheses
   were written:
   - per-chain P5 against warmup-end `h` has Spearman +0.156 (default) and
     −0.01 (`delta2`), with small-`h` chains at 0.0435 and large-`h` chains
     at 0.048;
   - omega mean is 0.0035 +/- 0.026 and omega variance 8.82 +/- 0.07;
   - the median omega bulk ESS is 522 per 80,000 draws.
2. **Pipeline checks on diagnostic seed 990661** (unused), made after the
   predictions above were written. Outputs are in the lane scratch directory
   and are not committed.
