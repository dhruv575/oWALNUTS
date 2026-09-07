# Decisions register: every default, with its evidence

Each row is a change to what a user gets without asking. The frozen
`walnutpie` defaults (`RunConfig`, `KernelTuning`, `ALGORITHM_REVISION`
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`) never changed during
the 0.2 programme; every row below is in `owalnuts::sampler` unless marked
kernel. Full evidence for each study is in the
[ledger](research-ledger-2026-08-31.md).

## Kernel corrections (affect every path)

| revision | change | study | why |
|---|---|---|---|
| v9 | leaf acceptance on the endpoint energy error only, as upstream, not the path-wide maximum | WP6 `funnel_bias_fix_v1` | v8 accepted non-reversible leaves and put twice the correct mass in the funnel neck; 4,000-leaf oracle now agrees to 1e-11 |
| v10 | a recoverable target failure is a zero-density point (`-inf`, zero gradient) that refinement continues through, as upstream | WP10 `invalid_evaluation_parity_v1` | v9 stopped the transition and counted it as a divergence; Stock-Watson had 16.5 % recoverable calls and no-op transitions |
| paper adaptation v2 | unrefined fraction over built leaves only; leafless transitions contribute no step update; step bounded to 1e3 x initial | WP9 `paper_funnel_adaptive_v2` | all-invalid transitions read as 1.0 and drove h to the 1e6 ceiling (found by WP2b) |
| paper adaptation v3 | `ContinueThroughLocalErrorInstall` is the paper-mode default | WP9 | restarting dual averaging at every delta install gave per-window h swings of 10 to 30x |
| paper adaptation v4 | robust rule (delta floor, delayed first installation) | `paper_adaptation_robust_v1` | v3 installed delta near 0 from uniform starts and froze 9 of 17 posteriordb models (WP22) |

## Sampler defaults, in the order they changed

| change | study | rule met? | why |
|---|---|---|---|
| max depth 8 to 10 | `adaptation_parity_v1` | yes | 1.45x ESS per gradient, 17 of 18 gates; `diamonds` and `earnings` were capping at depth 8 |
| cache the initial evaluation | WP30 `kernel_efficiency_v1` | bit-identical | the driver re-evaluated the current state every transition |
| `Limits::admit_worst_case()` | usability | n/a | the sampler's own defaults were rejected by the conservative preflight ceiling |
| `ExhaustionRule::AcceptUnlessDivergent` in warmup only | WP24 `freeze_mode_v1`, confirmed WP25 | yes | the two-sided leaf test froze `arma11` chains from astronomically bad starts; retained-phase use loses the funnel neck (z -7), so warmup only |
| refinement levels 4 to 8 | WP28 `funnel_defaults_v1`, cost confirmed WP29 | yes | four levels halve the funnel tail mass; eight are exact and never selected on posteriordb |
| `UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan` | WP31 `joint_default_v1` (rule failed on C2), flipped post hoc, validated WP32 `posteriordb_bench_v5` | **post hoc**; validation predictions 5/5 held | 1.508x per gradient, 41 vs 35 gates, `sblrc` 9x, `earnings` recovered; C2 failed only on the two fail-everywhere cells (`hmm_drive_0` mode lottery, centered eight schools). Documented as post hoc in CHANGELOG, README, release notes |
| chain rescue `restart_from_best` | WP33 `chain_rescue_v1` | yes | 25 of 27 cells vs 21; `lotka_volterra` 0/3 to 3/3 |
| chain rescue back to none | WP36 `chain_rescue_v2` | mechanical fallback | `two_hit` failed its conjunctive gates; `current` hit its mapped-origin-overwrite red lines; the registered fallback is `no_rescue` |

## Candidates measured and not adopted

| candidate | study | result | reason |
|---|---|---|---|
| Appendix C (paper) adaptation as default | WP22, WP23 | froze 9 of 17 (v3 rule); v4 parity 0.995x DA | safe after v4 but not better; opt-in with `Delta` as the knob |
| `MomentumSum` alone | WP26 `uturn_default_v1` | 1.064x, worst 0.78x | per-model coin under the unit-floored metric; the gain appears only with Stan regularisation |
| Stan regularisation alone | WP27, WP29 | `sblrc` 7.8 to 9.7x, `earnings` 0.35x | endpoint U-turn orbits too short at the corrected metric; five gates lost |
| lower `delta` (0.5, 0.25) | WP28 | funnel bias worse | more exhaustions at four levels |
| `stan_style` warmup preset | WP23, WP24, WP25, WP28 | 29 to 32 gates; funnel biased; freezes like the baseline | two-sided rule; `delta = 1000` fast phase errors on the funnel |
| fixed `delta = 2` | WP34 (`da-d2` 1.070x), WP37A | not qualified | `accel_gp` 0.68x; funnel gross-safety gates F3/F4 fail |
| step-raising arms (`da06`, `paper06`, `stanacc`) | WP34 | 0.60 to 0.83x | the leaf-error distribution is one smooth population; raising the step moves all of it |
| chain pooling at boundaries | WP33 | 23 of 27, `lotka_volterra` 0.42x | never moves a frozen chain |
| two-consecutive-hit rescue | WP36 | failed conjunctive gates | nuisance sample too small, funnel signed tail z failed |
| per-window structured-metric refresh | WP16 | 2/3, 0.25 to 0.52x arm P | early windows underestimate a slow global's variance |
| canonical-v3 full scale non-centering | WP17 | falsified for oWALNUTS and NumPyro | relocates the funnel; likelihood curvature sigma_x^2 T^2 |
| coarsest-first reverse check order | WP37B | paused; descriptive reverse calls 1.086x against it | no evidence it is cheaper |
| `ReverseCoarserPolicy::ZeroWeightBeyond` | WP39 | 0.981x | step confound: zero-weight leaves diluted the statistic, h +3 to 30 % |
| `ZeroWeightBeyondAdaptSelected` | WP39B | 0.878x; fixed-step 0.908x on targets | the untruncated orbit pays only on the noncentered eight schools |
| `NonfinitePositionPolicy::RejectLeaf` | WP38 | not qualified | health gate measured the target, not the policy |
| warmup-only untruncated orbits, skip single-leaf statistic, descent bound, NUTS initial phase, Stan step search | WP40 `warmup_gap_diag_v1` | best combination 1.05x overall, 0.78x on targets | every arm that saves warmup gradients ends at a larger step |
| acceptance target 0.85 or 0.9 with the skip statistic | WP40 addendum | 0.90 to 0.96x, `accel_gp` 0.52 to 0.65x | the higher target costs sampling efficiency on every model and does not restore the targets |
| floored single-leaf crash statistic (0.3, 0.5, 0.8) | WP40 addendum 2 | best 1.014x on the nine-model screen, `gp_pois_regr` 0.73, `accel_gp` 0.63 | the GP targets need the smaller step the crash gives them |
| resident DLL + joined Rayon workers (Windows) | `bridgestan_lifetime_v1` | 8/180 faults | rejected under the zero-fault gate |

## Documented opt-ins that are recommended for specific targets

- `Tuning::funnel()` and the paper tuning (delta 0.21, h 0.36) for Neal-type
  funnels; the defaults are unbiased there but slow.
- `levels8 + delta 0.5` is the funnel-efficient setting (WP28) and has not
  been re-measured on posteriordb.
- The posterior-precision tridiagonal path block for state-space paths
  (WP12, WP16: 2.2 to 2.7x, confirmed at 4 x 4,000).
- `ChainRescueConfig::restart_from_best()` for one-bad-chain start failures,
  reading the rescue telemetry on multimodal targets.
- `owned-one-worker` BridgeStan backend on Windows GNU (only qualified
  configuration there).
