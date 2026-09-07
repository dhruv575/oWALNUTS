# Orbit construction, selection and the U-turn rule

## State of knowledge

The orbit machinery of oWALNUTS is exact and, on ordinary posteriors, its
per-gradient efficiency is decided almost entirely by how long the orbit is
allowed to grow before the U-turn rule ends it. Selection is not the problem:
the biased-progressive outer join is a measured 1.75x win over exact
multinomial selection, and a NUTS-inside-oWALNUTS control matches a
clean-room reference NUTS to within 5 %. The problem was the endpoint U-turn
statistic, which ended orbits at about 0.60x the leaves of Stan's
momentum-sum rule under a correct metric. Switching to `MomentumSum` closed
most of that gap, but only once the diagonal metric regularisation was fixed
at the same time, because the two options interact through the warmup
windows. The kernel itself no longer allocates per call and every efficiency
change was accepted only if retained draws stayed bit-identical.

## Timeline of evidence

- **WP3-1** (`STUDIES/outer_selection_bps_vs_multinomial_v1`, 2026-08-31).
  Reverse ablation of the outer join on the strict noncentered Eight Schools
  track, three seeds. Biased-progressive over exact normalised multinomial:
  geomean bulk ESS per retained call 1.7453 (rule 1.10), min tail ratio 1.44,
  zero divergences or depth caps in all 24 chains. Self-retention 0.39 %
  versus 10.74 %, lag-1 autocorrelation lower by about 0.3 on every
  functional, mean depth 3.77 versus 3.67. The mechanism is selection, not
  trajectory length. This closed the "progressive selection" clue from the
  NextStat 0.10.1 clean-room study (`nextstat-0.10.1-clean-room-study.md`):
  oWALNUTS already used the winning join, so it could not explain the
  NextStat public-API gap.
- **adaptation_parity_v1** (`STUDIES/adaptation_parity_v1`, 0.2 programme).
  Raising the sampler default maximum depth from 8 to 10 gave 1.45x ESS per
  gradient and 17/18 gates, and fixed `diamonds` and `earnings`, whose step
  had collapsed to about 0.003 with 85–90 % depth-8 caps in the first
  posteriordb run (WP22). WP23 confirmed on the full protocol: `diamonds`
  0/3 to 3/3 on every oWALNUTS arm (8x ESS per gradient), `earnings` 0/3 to
  2/3 (12x).
- **WP30 kernel_efficiency_v1 / kernel-gap** (`STUDIES/kernel_efficiency_v1`,
  `STUDIES/kernel_gap_v1`, 2026-09-02). Per-transition workspaces, in-place
  gradient writes, an `Rc<State>` ring reused across leaves and one removed
  re-validation took allocations per target call from 8.5–14.4 to 0.19–1.27
  and kernel overhead per call from 480 / 2002 / 889 ns to 131 / 557 / 320 ns
  on the funnel, a 100-D Gaussian and Eight Schools, with every retained draw
  bit-identical. The driver had also been re-evaluating the current state
  every transition; caching the initial evaluation removed one target call
  per transition, again bit-identical. Optimisations that would have changed
  floating-point operation order were measured and rejected.
- **WP30** (`STUDIES/kernel_gap_v1`). Matched-condition instrumentation on six
  posteriordb models at CmdStan's own adapted step, inverse metric and
  starts, no warmup, against a clean-room reference NUTS. The default kernel
  was 0.77x the reference per gradient, decomposed as 0.46x ESS per orbit
  times 1.66 orbits per gradient, with leaves per orbit 0.60x (0.26x on
  `earnings`, 0.49x `kidiq`, up to 0.92x `arK`) and gradients per leaf 1.01x;
  41–69 % of orbits ended in the recursive endpoint U-turn. `delta = 1000`,
  one level and the accepting exhaustion rule were within 1 % of the default,
  so refinement was not the cause. `MomentumSum` restored leaves per orbit to
  0.97x and ESS per gradient to 0.90x (0.84–0.96); `earnings` went from 40 to
  151 leaves per orbit against the reference's 158. The one-level plus
  momentum-sum control reached 0.95x with the same selected-state
  displacement as the reference, so selection is not different. The residual
  0.90 to 0.95 is refinement's reverse-coarser orbit stops (3–7 % of orbits).
  `EndpointsWithCross` was 0.69x.
- **WP26** (`STUDIES/uturn_default_v1`, 2026-09-02). `MomentumSum` alone as
  the sampler default on the v3 posteriordb protocol: geomean 1.064x (rule
  1.10), worst models centered eight schools 0.78, `diamonds` 0.80,
  `gp_pois_regr` 0.846 (rule 0.85), gates 37 versus 38, per model 0.78–2.14x.
  Rejected under the preregistered rule. The funnel at the paper tuning was
  safe under every rule, and the Eight Schools strict track was 1.077x. The
  study also found the sampler-default funnel biased under every U-turn rule
  (z −3 to −11 over three seeds), which led to WP28. Its reading that "the
  per-gradient gap to CmdStan on healthy models is not the U-turn rule
  (0.434x to 0.462x)" was later shown by WP30 to be an artefact of the
  warmup: the unit-floored metric and the depth cap hid the rule's effect on
  the other eleven models.
- **WP31** (`STUDIES/joint_default_v1`, 2026-09-03). `MomentumSum` plus
  `DiagonalMetricRegularization::Stan` as one candidate, four arms. C1 held
  at 1.508x (rhosum alone 1.116, stanreg alone 1.257); gates 41 versus 35;
  funnel and Eight Schools (1.294x) safe; `earnings` 3.69x and 3/3, `sblrc`
  9.12x, `kidiq` 1.98x, `nes2000` 1.50x. The interaction: `stanreg` alone on
  `earnings` is 0.08x and 0/3 because under the endpoint rule at the
  corrected metric the short orbits leave the window variance at the floor
  and the metric overshoots, while under `MomentumSum` the window measures
  the variance and installs CmdStan's value. C2 (no model below 0.85x)
  failed on `hmm_drive_0` (0.005, a second-mode start draw that any change to
  the first warmup transitions perturbs) and on the centered eight schools
  (0.79, failing in every arm), so the flip was made post hoc and labelled as
  such.
- **WP32** (`STUDIES/posteriordb_bench_v5`, 2026-09-03). Fresh-seed
  validation of the post-hoc default against rerun CmdStan and nutpie: 42/51
  gates versus 36 and 28, 0.822x CmdStan per gradient on the sixteen models
  without `arma11` (1.069x over 17), 3.085x nutpie ESS per second, funnel
  exact, no regression against v3 beyond seed noise. All five predictions
  held. The healthy-model figure of 0.67–0.95x per model is the honest
  residual.

## What worked

| change | study | result | why |
|---|---|---|---|
| Biased-progressive outer join over exact multinomial | WP3-1 `outer_selection_bps_vs_multinomial_v1` | 1.745x bulk ESS per call, tail 1.44x, health clean | near-zero self-retention (0.39 % vs 10.74 %) and lower lag-1 autocorrelation; selection, not orbit length |
| Maximum depth 8 to 10 | `adaptation_parity_v1`, WP23 | 1.45x ESS per gradient; `diamonds` 0/3 to 3/3, `earnings` 0/3 to 2/3 | the depth-8 cap bound at the collapsed step on the regressions |
| Allocation-free kernel and cached initial evaluation | WP30 `kernel_efficiency_v1` | allocations per call 8.5–14.4 to 0.19–1.27; one fewer target call per transition | bit-identical draws pinned by `tests/kernel_fingerprint.rs` |
| `UTurnRule::MomentumSum` together with Stan metric regularisation | WP31 `joint_default_v1`, validated by WP32 `posteriordb_bench_v5` | 1.508x per gradient, 41 vs 35 gates; on fresh seeds 42/51 vs CmdStan 36 | longer orbits let the slow windows measure the variance the corrected metric needs; either alone fails |

## What did not work

| change | study | result | why |
|---|---|---|---|
| `MomentumSum` alone as default | WP26 `uturn_default_v1` | 1.064x geomean, worst 0.78, one gate fewer; rejected | under the unit-floored metric and depth cap the longer orbit is a per-model coin |
| Stan regularisation alone | WP29 `posteriordb_bench_v4`, WP31 | `sblrc` 7.76x but `earnings` 0.35x and 0/3, five gates lost | short endpoint orbits at the corrected metric leave the window variance at the floor; feedback collapse |
| `EndpointsWithCross` | WP30, WP26 | 0.69x reference; 0.811x on the posteriordb set, collapses on `lotka_volterra` 0.26 and `accel_gp` 0.34 | ends orbits even earlier than the endpoint rule |
| Floating-point-reordering optimisations | WP30 `kernel_efficiency_v1` | rejected | they changed retained draws; the fingerprint rail is non-negotiable |

## Current default

`Tuning::default()` in `owalnuts::sampler`: maximum depth 10,
`UTurnRule::MomentumSum`, biased-progressive outer selection, cached initial
evaluation, `Limits::admit_worst_case()`; `Adaptation::default()` with
`DiagonalMetricRegularization::Stan`. The frozen `walnutpie::KernelTuning`
and `RunConfig` defaults (depth 3, `Endpoints`, `TowardUnit`) are unchanged so
every oracle and fingerprint still holds. Details in the
[ledger](../research-ledger-2026-08-31.md) and `release-0.2.0.md`.

## Open questions

- `diamonds` is depth-capped in every arm at `h` about 0.003–0.005 (246–539
  caps per seed in v5); it is not a metric-floor case, so the depth cap
  itself is the next item there.
- The `hmm_drive_0` second-mode draw is a start property that any change to
  the first warmup transitions perturbs; a cross-chain mode check at the end
  of warmup (`ChainDisagreement`) is the right instrument before it decides
  a gate.
- The 0.90 to 0.95 residual against reference NUTS at a matched step is the
  reverse-coarser stop on refined leaves; see
  `refinement-and-reverse-coarsening.md`.
- The healthy-model figure against CmdStan is 0.67–0.95x per gradient
  including warmup; WP40 traced the remainder to warmup rather than to the
  orbit ([step-size-adaptation](step-size-adaptation.md)).
