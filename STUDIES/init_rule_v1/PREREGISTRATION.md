# init_rule_v1 (WP43): preregistration

Frozen 2026-10-24 before the first evidence cell. Machine-readable copy:
`protocol.json` (it wins on any discrepancy).

## Question

`wiki/open-questions.md` item 6. On `hmm_drive_0` (a chain started in the
basin of a second HMM mode) and `lotka_volterra` (starts on the `rk45` failure
boundary that freeze one chain) the 17-model screen's gates are decided by the
uniform(-2, 2) start lottery for every sampler. `Init::uniform()` retries a
draw until the log density and gradient are finite and does nothing else.
Does a cheap init-time rule remove the lottery without hurting anything?

Chain rescue (WP33, WP36) attacked the same failure class after the fact and
was removed from the defaults because a density rescue can overwrite a genuine
mode and blind R-hat to it. An init rule has the same risk in a different
form: if every chain is pulled toward the same basin, a second mode can go
unseen. That risk is what the hidden-mode clause below measures.

## Change under test

A new opt-in variant, nothing else changed:

```rust
Init::Candidates { radius, candidates, max_attempts, selection: StartSelection }
Init::best_of(k)    // radius 2, 100 attempts per candidate, HighestDensity
Init::median_of(k)  // radius 2, 100 attempts per candidate, MedianDensity
candidate_starts(target, chains, seed, radius, k, max_attempts, selection) -> CandidateStarts
```

Per chain, `k` evaluable starts are drawn exactly as `Init::Uniform` draws
one, from the same start RNG stream, and one is kept by its log density. With
`k = 1` the starts equal `uniform_starts` bit for bit (tested).
`Init::uniform()`, `Init::Given`, the default and the kernel fingerprints are
unchanged; `cargo test` is green.

The target API has no gradient-free evaluation, so each candidate costs one
full log-density-and-gradient call. All of them, rejected non-finite draws
included, are counted in `gradients_total`.

## Arms (at most two rule arms)

| arm | rule |
|---|---|
| `default` | `Init::uniform()` |
| `best16` (A) | `Init::best_of(16)`: start at the highest-density candidate |
| `median16` (C) | `Init::median_of(16)`: start at the lower-median-density candidate |

Arm B (best-of-16 with a gradient-norm feasibility margin) is not run. The
highest-density candidate almost never has a gradient norm many times the
pool median, so B would reproduce A on nearly every cell. The second slot
goes to the opposite hedge instead: C keeps a typical start, discards both
tails, and cannot systematically prefer one basin.

## Protocol

- 17 posteriordb models (the v6 list), posteriordb `28f8d3d`, reference
  draws as the truth.
- 4 chains x 1,000 warmup / 1,000 retained, four threads, sampler defaults
  otherwise (`Tuning::default()`, `Metric::diagonal()`,
  `Adaptation::default()` with no rescue, `Limits::admit_worst_case()`).
- Five fresh seeds 943101-943105 (no `git grep -w` hit anywhere in the
  repository).
- Order: models as listed; seeds ascending; arms default, best16, median16;
  strictly sequential; one harness process per cell. Then the funnel.
- Gates: rank R-hat <= 1.01, bulk and tail ESS >= 400 on every reference
  parameter, zero retained divergences, finite draws, no sampler error.
- Per cell: each chain's start and start log density, every candidate's log
  density and the chosen index, init evaluations, gates, the Rust
  `ChainDisagreement` (leave-one-chain-out R-hat on the unconstrained draws),
  each chain's reference distance (max over reference parameters of |chain
  mean - reference mean| / reference SD; above 3 = the chain ended in a
  different mode), and min bulk ESS per gradient.
- **Hidden mode.** A cell with max rank R-hat <= 1.01 whose mean on some
  reference parameter is more than 3 reference SD from the reference is a
  hidden-mode failure. It is never a credited pass and ranks below a visible
  R-hat failure. The check runs on every cell; `hmm_drive_0` is the named
  target.
- Efficiency: per model, the geomean over seeds of min bulk ESS per gradient,
  using the seeds where both arms are ok; the rule/default ratio per model;
  then the geomean of the 17 ratios.
- Funnel side check: Neal's 10-D funnel at the defaults, 4 x 2,000 / 20,000,
  five seeds. The default arm uses the house starts omega in {-3, -1, 1, 3},
  x = 0. The rule arms draw each chain's 16 candidates from uniform(-3, 3)^10,
  so the largest |omega| among the house starts caps the pool. Gate: MCSE z of
  P(omega < -5) (exact 0.0478) within +-2 on every seed.

## Decision rule (frozen)

Recommend a rule arm as the new default iff all four hold:

- D1: credited passes over the 85 cells >= default's;
- D2: zero hidden-mode cells;
- D3: geomean ESS/gradient ratio vs default >= 0.97;
- D4: funnel |z| <= 2 on every seed.

If both qualify, take more credited passes, then the higher ratio. Otherwise
keep `Init::uniform()`. This study ships only the opt-in variant and changes
no default.

## Predictions (numeric, before running)

- P1: default 70-74 credited passes of 85; centered eight schools fails 5/5;
  `accel_gp` fails 2-3/5.
- P2: default has an off-reference `hmm_drive_0` chain on 1-2 of 5 seeds;
  best16 on 0 of 5; best16 passes `lotka_volterra` 5/5.
- P3: best16 credited passes exceed default's by 1 to 3.
- P4: best16 has zero hidden-mode cells.
- P5: best16 geomean ratio in [1.00, 1.15]. Init is at most 0.1 % of
  gradients; any gain comes from removing lottery cells.
- P6: median16 is indistinguishable from default: credited passes within +-1,
  geomean ratio in [0.97, 1.03], and still at least one off-reference
  `hmm_drive_0` seed.
- P7: funnel |z| <= 2 on all five seeds for all three arms.
- P8: best16's median start log density exceeds default's on all 17 models.
- P9: mechanical decision: best16 qualifies, median16 does not.

## Rules

All cells are reported. No result-driven reruns. Failures are results, and
nothing is tuned after seeing results. If the process crashes, it may be
relaunched, and only cells without a completed artifact are run; the
deviation is recorded. Walls are contended (nine sibling agents on 16 cores)
and are not evidence.
