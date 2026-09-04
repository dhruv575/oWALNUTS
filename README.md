# oWALNUTS

`owalnuts` is a Rust implementation of **WALNUTS**, the Within-orbit Adaptive
Leapfrog No-U-Turn Sampler (Bou-Rabee, Carpenter, Kleppe, Liu; *JMLR* 27,
2026). It is NUTS with a second time scale: every macro leapfrog step is
subdivided into micro-steps, and the number of micro-steps is chosen per
step so that the local energy error stays under a threshold `delta`. Fine
steps are spent only where the curvature demands them, which is what lets it
sample multi-scale targets such as Neal's funnel without the bias fixed-step
NUTS shows there. The kernel is derived from, and tested leaf-for-leaf
against, the Flatiron reference implementation
[`walnutpie`](https://github.com/flatironinstitute/walnutpie) (MIT); the
public API is a small builder, `owalnuts::sampler`, over a complete
facade, `owalnuts::walnutpie`. Version `0.2.0`; kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`.

## Quick start

```toml
[dependencies]
owalnuts = "0.2.0"
```

Implement `Target` (log density and gradient in one call, unconstrained
`f64` coordinates) and run the sampler at its defaults. This is
[`examples/readme_quick_start.rs`](examples/readme_quick_start.rs), which CI
runs:

```rust
use owalnuts::diagnostics::Summary;
use owalnuts::sampler::{Sampler, Target, TargetError};

struct Gaussian;
impl Target for Gaussian {
    fn dimension(&self) -> usize { 5 }
    fn log_density_gradient(&self, q: &[f64], grad: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in grad.iter_mut().zip(q) { *g = -x; }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

let posterior = Sampler::new()
    .warmup(1_000)
    .draws(1_000)
    .chains(4)
    .seed(0x5eed)
    .run_from_random_starts(&Gaussian)?;   // uniform(-2, 2) starts, retried until finite

let summary = Summary::from_output(posterior.inner(), None)?;
println!("{summary}");                     // mean, sd, MCSE, quantiles, ESS, R-hat, health
```

The defaults are tuned for funnel-shaped posteriors as well as ordinary
ones: eight refinement levels, which is what keeps the quick-start
configuration unbiased on Neal's funnel (see "Where it shines").
`Summary` prints a Stan-style table (rank-normalised split R-hat, bulk and
tail ESS, MCSE, 5/50/95 % quantiles; each estimator matches ArviZ to 1e-6)
followed by the sampler health per chain and pooled: divergences, invalid
evaluations, depth-cap stops, refinement exhaustions, mean tree depth, target
calls, step size. `posterior.draws()` iterates retained positions as
`&[f64]`; `posterior.chains()` gives per-chain draws, diagnostics, telemetry
and metadata; `.run(&target, &starts)` takes explicit starts, one per chain.

One line each for the other front doors:

- **CmdStan CSV**: `export::CmdStanCsv::new().with_log_density(&target).write_dir(posterior.inner(), "out", "chain")?`
  writes `out/chain-1.csv ...` that `arviz.from_cmdstan` loads directly.
- **Python**: `pip install maturin` then `maturin develop --release` in
  [`integrations/python`](integrations/python/README.md);
  `owalnuts.sample(logp_and_grad, dim=10, warmup=1000, draws=1000, seed=1).summary()`,
  with `from_jax`, `from_torch` and `from_pymc` adapters.
- **Stan models**: [`owalnuts-bridgestan`](integrations/bridgestan/README.md)
  wraps a BridgeStan-compiled model as a `Target`
  (`ReplicatedStanTarget::load(so, preload, data, seed, threads)` for
  multi-chain runs).
- **Rust autodiff**: [`owalnuts-autodiff`](integrations/autodiff/README.md)
  turns `fn log_density<S: Scalar>(&self, q: &[S]) -> S` into a `Target`
  with a reverse-mode tape, a few times the cost of a hand-written gradient.

## Where it shines

Every number below is from a preregistered, checksummed study in
[`STUDIES/`](STUDIES/); the Evidence list at the end links each one.

- **Neal's funnel is sampled without bias.** At the paper's tuning,
  4 x 50,000 draws give tail mass `P(omega < -5)` = **0.0474** against the
  exact 0.0478 (the reference implementation at identical tuning: 0.0477),
  with zero divergences; fixed-step NUTS is biased on this target, and so
  was the pre-`v9` kernel (0.0971). [E1] At the **sampler defaults**
  (adapted diagonal metric, dual averaging, `h0 = 0.5`) the tail mass is
  within `|z| <= 2` of exact on three fresh seeds (0.0412, 0.0346, 0.0897)
  because the default is eight refinement levels; at four levels it was
  half the exact value, and a one-level NUTS-like control never draws
  below `omega = -5` on two seeds. The pooled estimate is right but the
  funnel does not mix *well* at the defaults (one chain per seed adapts
  to `h ~ 0.01`, `omega` R-hat 1.01-1.04); `Tuning::new().max_error(0.5)`
  mixes better there at a 21 % cost on a 100-D Gaussian. [E11]
- **Long state-space paths mix at depth 3–4.** On an exact Gaussian
  state-space model at `T = 1000`, supplying the posterior-precision
  tridiagonal metric (`Metric::Structured`) gives ESS per target call
  **~1,000x** a prior-based metric and 4.8x the identity, at Monte-Carlo
  accuracy against the closed-form posterior. [E2]
- **Eight Schools throughput on a strict matched track.** Noncentered Eight
  Schools, 4 chains, 1,000/1,000, one thread: the conservative minimum over
  seven seeds and six functionals is **12,830 bulk / 10,346 tail ESS/s**
  against CmdStan 6,290 / 3,951, BlackJAX 5,645 / 4,195 and NumPyro
  5,241 / 4,050 on the same track. [E3]
- **Zero divergences where NUTS diverges.** In the posteriordb benchmark,
  oWALNUTS passes every gate on noncentered eight schools (3/3 seeds;
  CmdStan 1/3, nutpie 0/3) and `gp_pois_regr` (up to 3/3; CmdStan 0/3 with
  9–16 divergences, nutpie 0/3 with 120–822), with no divergence on
  either. [E4]

## Where it does not (yet)

The last breadth benchmark admitted by its preregistered release rule is
[`STUDIES/posteriordb_bench_v5`](STUDIES/posteriordb_bench_v5/README.md),
17 posteriordb posteriors, every sampler at its defaults, 4 chains,
1,000/1,000, three fresh seeds, gates rank R-hat <= 1.01, bulk and tail
ESS >= 400, zero divergences, CmdStan 2.39.0 and nutpie 0.16.8 rerun on the
same seeds. [E15] (v3 on the pre-WP31 defaults, kept as history: 35/51,
0.34x CmdStan per gradient [E4].)

WP33 subsequently made warmup restart-from-best chain rescue the default.
The then-current-default validation, `posteriordb_bench_v6`, passes **45/51**
cells against CmdStan 34 and nutpie 29 with no frozen chain, but did not meet
its frozen release rule: one passing `one_comp` cell has max |z| 4.023 and one
`sblrc` sampler subprocess exited without a result, leaving its fixed-16
efficiency gates unevaluable (observed 0.848x CmdStan per gradient over the 15
complete models). WP36 then mechanically selected `no_rescue`: its
preregistered completeness gate failed after seven process faults, and
`two_hit` failed its conjunctive efficacy, nuisance-reduction, funnel,
origin-safety and efficiency gates. That failure alone did not select
`no_rescue`; it advanced the mechanical rule to the `current` fallback check.
`current` had registered red lines in four origin-overwrite cells (five
events) plus unknown run history for HMM/92104, so the fallback selected
`no_rescue`. The final 0.2 default therefore returns to the plain multi-chain
warmup used by v5. The v5 numbers below remain the qualified headline; v6
remains the historical record of the temporary WP33 default and must be read
beside it. [E16, E17, E18]

> **Historical WP35 replay:** do not run
> `STUDIES/posteriordb_bench_v6` from the current tree and call it a WP35
> reproduction. Check out the recorded WP35 study revision `8d3a7b5` (source
> under test `aa4510f`) first. At current HEAD,
> `Adaptation::default()` intentionally means no rescue, whereas WP35 measured
> the temporary restart-from-best default.

- **More cells pass than CmdStan or nutpie.** oWALNUTS passes **42/51**
  cells; CmdStan 36, nutpie 28. Twelve models at 3/3 against ten and eight.
- **ESS per gradient is still below CmdStan on ordinary posteriors.**
  Geometric mean **0.82x** CmdStan over the 16 models where CmdStan is
  healthy, 0.67–0.95x per model with no exception; 1.07x over all 17 only
  because CmdStan and nutpie each lose two `arma11` seeds to a chain that
  never leaves its start (oWALNUTS 3/3 there). Against nutpie 0.84x per
  gradient. The residual is the kernel (reverse-coarser stops on refined
  leaves and orbit length, [E13]), not warmup.
- **Wall time and ESS per second are ahead.** Wall per gradient **0.80x**
  CmdStan's; ESS per second **1.40x** CmdStan's and **3.09x** nutpie's
  (above CmdStan on 8 of 17 models, above nutpie on 14 of 16).
- **What still fails.** The centered eight schools fails every sampler on
  every seed; `accel_gp` (66-d GP) fails every sampler at 0.47x CmdStan per
  gradient; `hmm_drive_0` can put one chain in a second mode from a uniform
  start (one seed each for oWALNUTS and CmdStan here); `one_comp` is 1/3
  for oWALNUTS and CmdStan; `diamonds` still hits the depth-10 cap on
  250–540 transitions per seed. Bad starts no longer stall a chain: no
  frozen chain, no step collapse (`sblrc` 0/3 -> 3/3), zero retained
  divergences on every oWALNUTS cell.
- **Refinement rarely engages on these posteriors.** A refinement level
  above zero is selected on 1–3 % of retained transitions, so on ordinary
  models the kernel runs as NUTS, and its endpoint U-turn rule then costs
  0.75–0.9x per gradient against Stan's momentum-sum rule on Gaussian
  targets. On the posteriordb set, swapping in Stan's rule alone
  (`UTurnRule::MomentumSum`) is a per-model coin (1.06–1.12x geometric
  mean) because the default metric regularisation floors small posterior
  variances at 0.01 and hides it; with Stan's regularisation
  (`DiagonalMetricRegularization::Stan`) the two together are 1.51x the
  default per gradient over the 17 models and pass 41 cells against 35.
  The preregistered flip rule failed on the two cells no option passes
  (`hmm_drive_0`'s second-mode draw, the centered eight schools); the
  pair was made the default afterwards as a post-hoc decision and
  validated on fresh seeds in `STUDIES/posteriordb_bench_v5` [E15].
  [E5, E6, E12, E13, E14]

The wins measured so far come from funnel-type targets, from structured
metrics, from gates (fewer failed cells than either NUTS implementation on
the posteriordb set) and from wall time; per gradient, an ordinary
regression that CmdStan already samples cleanly still costs oWALNUTS
1.05–1.5x the gradients.

## Defaults and opt-ins

`Sampler::new()` with no other calls runs:

| Setting | Default | Why |
|---|---|---|
| warmup / draws / chains | 1,000 / 1,000 / one per start | Stan's shape |
| `Tuning::max_depth` | 10 | ablation over nine posteriordb models: 1.45x ESS per gradient and 17/18 gates against depth 8 [E7] |
| `Tuning::step_size` (`h`) | 0.5 | initial macro step; dual averaging adapts it |
| `Tuning::max_refinement_levels` | 8 | micro-steps down to `h / 256`; four levels halve the funnel's tail mass at the adapted step, eight are exact and never engage on Eight Schools or a 100-D Gaussian [E11] |
| `Tuning::max_error` (`delta`) | 1 | energy-error threshold per macro step |
| `Tuning::kernel_options` U-turn rule | `UTurnRule::MomentumSum` (Stan's generalised criterion) | **post-hoc default change after WP31**, validated by WP32: with Stan's metric prior it is 1.51x the endpoint rule per gradient over 17 posteriordb models; the frozen `v10` endpoint rule is `KernelOptions::default()` [E14, E15] |
| `Adaptation` | dual averaging to acceptance 0.8 | 75 / 25, 50, 100, ... / 50 windows (`gamma` 0.05, `t_0` 10, `kappa` 0.75); warmup exhaustion rule `AcceptUnlessDivergent` [E10] |
| `Metric` | adapted diagonal | Welford, regularised with Stan's prior (`DiagonalMetricRegularization::Stan`, **post-hoc default change after WP31**; the `v10` `TowardUnit` prior floors small variances at 0.01 and collapsed the step on `sblrc` / `arma11`) [E14, E15] |
| warmup chain rescue | none (`DEFAULT_CHAIN_RESCUE = None`) | `two_hit` failed its conjunctive gates; `current` then hit registered red lines in four origin-overwrite cells (five events) plus unknown HMM/92104 run history, selecting the WP36 fallback; default telemetry has no rescue records [E18] |
| initial evaluation | cached | one gradient per transition saved, draws bit-identical [E6] |
| `Limits` | admit the exact worst case | the worst case is a bound the run cannot exceed, so admission costs nothing |

Opt-ins, each one builder call:

- `Adaptation::Paper(PaperAdaptationConfig::default())`: the JMLR Appendix C
  rules (`delta` from the K-quantile rule, `h` so a fraction of macro leaves
  needs no refinement). On Neal's funnel from `delta = 1, h = 0.1` it is
  unbiased and 1.41x / 1.61x (bulk / tail ESS per call) the paper's own fixed
  funnel tuning [E8]; on posteriordb it is at parity with dual averaging
  (geomean 0.995) and robust on the cells that froze under its v3 defaults
  [E4, E9]. See `examples/funnel_paper_adaptation.rs`.
- `Adaptation::Custom(WarmupConfig::stan_style(0.8))`: Stan's acceptance
  statistic, `init_stepsize`, metric prior and restart reference. 2.0x the
  default's ESS per gradient on correlated regressions but 12–16 % worse on
  three models and R-hat > 1.01 on two, so opt-in [E7].
- `Adaptation::Custom(WarmupConfig::new(0.8)?.with_chain_rescue(
  ChainRescueConfig::restart_from_best()))`: the WP33 immediate
  restart-from-best rescue remains an explicit bad-start robustness opt-in
  (25/27 cells against the plain driver's 21, including `lotka_volterra`
  0/3 -> 3/3). When it acts it copies another chain's state, invalidating the
  independent-start interpretation of ordinary R-hat; inspect
  `RunTelemetry::chain_rescues`. Observe-only, two-hit and pooling policies
  are explicit opt-ins through the same builder [E16, E18].
- **The pre-WP31 kernel rules** (the frozen `v10` endpoint U-turn rule and
  the unit-variance metric prior), for reproducing runs made before the
  default change:
  `Tuning::new().kernel_options(KernelOptions::default())`
  with
  `Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::TowardUnit))`.
  The current defaults (`UTurnRule::MomentumSum` + `DiagonalMetricRegularization::Stan`)
  are a **post-hoc decision**: `STUDIES/joint_default_v1` preregistered a
  flip rule and failed it on two cells no option passes (`hmm_drive_0`'s
  arm-dependent second-mode draw, the centered eight schools), while the
  pair was 1.51x the old default's minimum bulk ESS per gradient over the
  17 posteriordb models (earnings 3.7x, sblrc 9.1x, arma11 2.3x, kidiq
  2.0x, hmm_example 1.9x, nes2000 1.5x; nothing below 0.94x among the
  models the old default passes), 41 cells against 35, funnel tail mass
  exact at both tunings with zero divergences and 1.29x on the Eight
  Schools strict track [E14]. The flip was decided after that result and
  validated on fresh seeds against CmdStan and nutpie in
  `STUDIES/posteriordb_bench_v5` [E15]. The two rules go together: the
  U-turn rule alone is a per-model coin (1.06–1.12x geomean) [E12], and
  the Stan prior under the endpoint rule is unstable on `earnings` (0.08x,
  R-hat up to 1.6: the short endpoint-rule orbits leave the window variance
  at the prior's floor) [E14].
- **The v5 breadth benchmark** is the honest figure for the final 0.2.0
  no-rescue defaults: CmdStan and nutpie rerun on fresh seeds 87101–87103 with
  preregistered predictions, all five held; 42/51 vs 36 and 28; 0.82x
  CmdStan per gradient on the healthy models (1.07x over 17 with `arma11`),
  0.80x wall per gradient, 1.40x / 3.09x ESS per second; funnel exact at
  the defaults on every seed [E15].
- `Init::uniform()` (`run_from_random_starts`, `run_with_init`): Stan's
  uniform(-2, 2) starts redrawn until the log density and gradient are
  finite; `.run(&target, &starts)` uses your own.
- `Limits::new().max_target_evaluations(n)`, `.deadline(..)`, `.timeout(..)`,
  `.cancellation(..)`: an exact runtime evaluation ceiling and cooperative
  stopping; `.admit_conservative()` restores the 0.1 admission check.

## Structured metrics

`StructuredBlockMass` (`BidiagonalCholesky`, `ScaledAr1`; linear time),
`DenseMass`, `BlockDiagonalMass` and `LowRankArrowheadMass` are fixed momentum
covariances run from the `Sampler` through `Metric::Structured` and
`Metric::Dense`. For a Gaussian state-space path, the tridiagonal posterior
precision `Q_rw + diag(1/r_t)` as `M` whitens the whole path, so trajectories
U-turn at depth 3–4 at any `T` where a prior-based metric caps the tree
[E2]; `examples/state_space_path_metric.rs` shows it against the exact
posterior mean. When the right block depends on parameters being sampled,
`Metric::StructuredRefresh` rebuilds it from a caller-supplied
`StructuredMetricRefresh` at every completed slow warmup window and freezes it
before retention, with a typed `StructuredRefreshUpdate` per boundary.

## Oracle parity

Private test-only modules compare the kernel with pinned outputs of the
unmodified upstream headers (`cargo test oracle_tests`):

- `oracle/walnutpie/f5bba365`: 54 Gaussian macro-leaf, span, transition and
  transition-sequence units;
- `oracle/walnutpie/f5bba365_funnel_leaves`: 4,000 Neal's-funnel macro leaves
  across four tunings and `omega` in [-8, 4]: decision, level, endpoint,
  adaptation statistic and target calls agree to 1e-11 (kernel `v8`
  disagreed on 1,555);
- `oracle/walnutpie/f5bba365_invalid_leaves`: 4,000 leaves against a throwing
  wall target, pinning the `v10` rule that a recoverable failure refines like
  any over-tolerance micro-step.

Orbit-level parity on hard targets is covered statistically
(`STUDIES/funnel_bias_fix_v1`, `STUDIES/paper_funnel_reproduction_v1`), and
every `Sampler::run` path is bit-identical to the `walnutpie` entry point it
wraps (`tests/sampler_api.rs`).

## Known limitations

- The posteriordb gaps above: 0.34x CmdStan per gradient, no throughput win
  on ordinary regressions, single chains stalled by bad starts on three
  models [E4, E10].
- Paper adaptation runs on the diagonal and fixed-operator facades only; the
  dense-adaptive, projected and pooled facades reject it.
- The `sigma_x -> 0` state-space funnel (`sspd-10`) is not sampled by any
  Euclidean sampler tested, NumPyro NUTS included; it needs a
  reparameterisation, not a metric [E2].
- On an exactly whitened Gaussian a fixed macro step can alias the
  tree-doubling schedule; there is no step-jitter option.
- Seeds reproduce runs only under the same kernel revision, crate build, lock
  file, target architecture and thread-independent deterministic target.
- Cancellation and deadlines are cooperative; a callback that never returns
  cannot be interrupted. `ResourceLimits` are preflight ceilings for
  accounted allocations, not process memory.
- The Python, BridgeStan and autodiff crates are built from the tree, not
  published; the BridgeStan sampling tests need a locally compiled model.

## API stability

`owalnuts::sampler`, `owalnuts::diagnostics`, `owalnuts::export` and
`owalnuts::walnutpie` are public and follow semver from `0.1.0`.
Research-only items (`OuterOrbitSelection`, `ResearchTargetEvaluationLimit`,
`ResearchRestartReferenceMultiplier`,
`DualAveragingAcceptance::AcceptedTrajectory`, the `direct_original_q`
family, the projected and pooled arrowhead facades) are exported from
`walnutpie` only with `features = ["research"]` and may change between minor
versions. `sampler::Tuning::default()` is not `walnutpie::KernelTuning::default()`:
the facade keeps the frozen replay defaults so pinned fingerprints hold.

## Research record

- [`wiki/release-0.2.0.md`](wiki/release-0.2.0.md): this release's changes,
  validation tables and limitations; [`CHANGELOG.md`](CHANGELOG.md) for the
  upgrade notes.
- [`wiki/research-ledger-2026-08-31.md`](wiki/research-ledger-2026-08-31.md):
  one checksummed entry per study.
- [`wiki/research-program-2026-09-04.md`](wiki/research-program-2026-09-04.md):
  the 0.2 program — what shipped, why each default changed, what the
  posteriordb benchmark falsified, and the open lines;
  [`wiki/research-program-2026-08-31.md`](wiki/research-program-2026-08-31.md):
  the program that produced `0.1.0-beta.2`.
- [`STUDIES/`](STUDIES/): every preregistration, runner, artifact and
  checksum.

## Toolchain

Rust 1.88 or newer. CI runs GNU 1.88 on Linux and Windows plus Linux stable:
tests (including all oracles), strict Clippy, `fmt --check`, `-D warnings`
rustdoc, examples and `cargo package`.

## Support and license

See [SECURITY.md](SECURITY.md) for scope. MIT; see [LICENSE](LICENSE),
[NOTICE](NOTICE) and [THIRD_PARTY.md](THIRD_PARTY.md) for the walnutpie
provenance.

## Evidence

- [E1] Funnel tail mass 0.0474 vs 0.0478, reference 0.0477, `v8` 0.0971:
  [`STUDIES/funnel_bias_fix_v1`](STUDIES/funnel_bias_fix_v1/README.md)
  (ledger `WP6-FUNNEL-BIAS-FIX-V9`).
- [E2] State-space path metric, depth 3–4 at `T = 1000`, ~1,000x prior-based,
  4.8x identity; `sspd-10` unsampled:
  [`STUDIES/exact_state_space_ground_truth_v1`](STUDIES/exact_state_space_ground_truth_v1/README.md)
  (`WP4-ESSGT-V1`),
  [`STUDIES/real_target_path_metric_v1`](STUDIES/real_target_path_metric_v1/README.md)
  (`WP4B-REAL-TARGET-PATH-METRIC-V1`).
- [E3] Eight Schools strict track, 12,830 / 10,346 ESS/s vs CmdStan,
  BlackJAX, NumPyro (walls on a loaded machine):
  [`STUDIES/eight_schools_v9_rebench_v1`](STUDIES/eight_schools_v9_rebench_v1/README.md)
  (`WP8-EIGHT-SCHOOLS-V9-REBENCH-V1`).
- [E4] posteriordb v3 (fresh seeds, WP24 default), 35/51 vs 37 and 31,
  0.34x per gradient, 0.75x wall per gradient, 1.35x nutpie ESS/s, gate wins
  on noncentered eight schools and `gp_pois_regr`:
  [`STUDIES/posteriordb_bench_v3`](STUDIES/posteriordb_bench_v3/README.md)
  (`WP25-POSTERIORDB-BENCH-V3`); v2 before the rule, with the frozen
  chains and the paper arm at 0.995x dual averaging:
  [`STUDIES/posteriordb_bench_v2`](STUDIES/posteriordb_bench_v2/README.md)
  (`WP23-POSTERIORDB-BENCH-V2`).
- [E10] the freeze mechanism (two-sided energy check at the initial leaf
  from overflow starts) and the `AcceptUnlessDivergent` warmup rule that
  unfroze 12/12 `arma11` chains:
  [`STUDIES/freeze_mode_v1`](STUDIES/freeze_mode_v1/README.md)
  (`WP24-FREEZE-MODE-V1`).
- [E5] Refinement on 1–3 % of retained transitions; kernel-side 0.7–0.8x:
  [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E6] U-turn rule 0.75x on the isotropic Gaussian, 1.0x correlated;
  `MomentumSum` 0.81x -> 1.09x; cache one gradient per transition:
  [`STUDIES/kernel_efficiency_v1`](STUDIES/kernel_efficiency_v1/README.md).
- [E12] `MomentumSum` on the 17 posteriordb models, fresh seeds, funnel at
  both tunings, Eight Schools strict track; preregistered default decision
  (not flipped): [`STUDIES/uturn_default_v1`](STUDIES/uturn_default_v1/README.md)
  (`WP26-UTURN-DEFAULT-V1`).
- [E13] The gap decomposed at CmdStan's step, metric and starts on six
  posteriordb models: leaves per orbit 0.60x under the endpoint U-turn
  statistic, gradients per leaf 1.01x, no selection difference;
  `MomentumSum` 0.77x -> 0.90x of reference NUTS per gradient:
  [`STUDIES/kernel_gap_v1`](STUDIES/kernel_gap_v1/README.md)
  (`WP30-KERNEL-GAP-V1`).
- [E7] Depth 10 ablation, 1.45x, 17/18 gates; `stan_style` 2.0x with
  regressions: [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E8] Appendix C on the funnel, 1.41x / 1.61x vs fixed paper tuning:
  [`STUDIES/paper_funnel_adaptive_v2`](STUDIES/paper_funnel_adaptive_v2/README.md)
  (`WP9-PAPER-H-RULE-STABILISATION-V2`).
- [E9] Appendix C v4 robust on the 14 freeze cells, geomean 1.04 vs dual
  averaging:
  [`STUDIES/paper_adaptation_robust_v1`](STUDIES/paper_adaptation_robust_v1/README.md).
- [E14] `MomentumSum` + Stan's regularisation together on the 17
  posteriordb models, fresh seeds, funnel at both tunings, Eight Schools
  strict track; preregistered joint default decision (1.51x, 41 vs 35
  cells, funnel and Eight Schools safe; not flipped on the per-model floor;
  flipped afterwards as a post-hoc decision):
  [`STUDIES/joint_default_v1`](STUDIES/joint_default_v1/README.md)
  (`WP31-JOINT-DEFAULT-V1`).
- [E15] posteriordb v5: the post-hoc default change validated on fresh
  seeds against rerun CmdStan and nutpie, five preregistered predictions
  held; 42/51 vs 36 and 28, 0.82x CmdStan per gradient on the healthy
  models (1.07x over 17), 0.80x wall per gradient, 1.40x / 3.09x ESS per
  second, funnel exact at the defaults:
  [`STUDIES/posteriordb_bench_v5`](STUDIES/posteriordb_bench_v5/README.md)
  (`WP32-POSTERIORDB-BENCH-V5`).
- [E16] Warmup restart-from-best chain rescue: 25/27 cells against the plain
  driver's 21, `lotka_volterra` 0/3 -> 3/3 and `arma11` 2/3 -> 3/3; the
  preregistered default rule held, with the mode-hiding caveat recorded:
  [`STUDIES/chain_rescue_v1`](STUDIES/chain_rescue_v1/README.md)
  (`WP33-CHAIN-RESCUE-V1`).
- [E17] posteriordb v6: complete then-current WP33 defaults on fresh seeds, 45/51
  gates against CmdStan 34 and nutpie 29, no frozen chain, 30 recorded
  rescues and funnel tail-mass |z| <= 2 on every seed; the release rule did
  not pass because one passing cell reached max |z| 4.023 and one `sblrc`
  process errored:
  [`STUDIES/posteriordb_bench_v6`](STUDIES/posteriordb_bench_v6/README.md)
  (`WP35-POSTERIORDB-BENCH-V6`).
- [E18] chain rescue v2: all 288 one-shot cells launched, 281 process-valid,
  with six heap-corruption exits and one post-result timeout leaving six
  invalid triplets. Two-hit reduced nuisance unique-chain actions 35 -> 14
  but failed its conjunctive gates. The rule then tested `current`, whose
  registered red lines were four origin-overwrite cells (five events) plus
  unknown HMM/92104 run history; only that second step selected `no_rescue`.
  The classifier found pathological/frozen ARMA and Lotka-Volterra origins
  and zero HMM origins, so WP36 does not establish genuine posterior-mode
  destruction:
  [`STUDIES/chain_rescue_v2`](STUDIES/chain_rescue_v2/README.md)
  (`WP36-CHAIN-RESCUE-V2`).
- [E11] The sampler defaults on the funnel: four levels 0.0203 / 0.0242 /
  0.0625 (z -3.5 / -3.8 / +0.3), eight levels 0.0412 / 0.0346 / 0.0897
  (|z| <= 1.43) at 1.05x / 1.00x ESS per call on Eight Schools and a 100-D
  Gaussian; lower `delta` alone makes the four-level bias worse:
  [`STUDIES/funnel_defaults_v1`](STUDIES/funnel_defaults_v1/README.md)
  (`WP28-FUNNEL-DEFAULTS-V1`).
