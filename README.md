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
  was the pre-`v9` kernel (0.0971). [E1]
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

The breadth benchmark is the honest picture of the crate at its defaults on
ordinary Stan models: [`STUDIES/posteriordb_bench_v2`](STUDIES/posteriordb_bench_v2/README.md),
17 posteriordb posteriors, every sampler at its defaults, 4 chains,
1,000/1,000, three seeds, gates rank R-hat <= 1.01, bulk and tail ESS >= 400,
zero divergences. [E4]

- **Fewer cells pass than CmdStan.** oWALNUTS passes **32/51** cells;
  CmdStan 35, nutpie 27.
- **ESS per gradient is well below CmdStan.** Geometric mean **0.23x**
  CmdStan over all 17 models; **0.45x** over the 15 models where every
  oWALNUTS chain moves. On the healthy models it is 0.4–0.9x with no
  exception.
- **Wall time is competitive, per gradient and against nutpie.** Wall per
  gradient is **0.77x** CmdStan's and ESS per second **1.1x** nutpie's
  (9 of 16 models won); ESS per second against CmdStan is 0.31x.
- **Two models freeze from uniform starts.** On `arma11` (0/3) and
  `lotka_volterra` (1/3) chains adapt `h -> 0` because every leaf from the
  start fails at every refinement level; NUTS's reject-and-shrink moves from
  the same starts. Fixing this needs a kernel rule, not a setting.
- **Refinement rarely engages on these posteriors.** A refinement level
  above zero is selected on 1–3 % of retained transitions, so on ordinary
  models the kernel runs as NUTS, and its endpoint U-turn rule then costs
  0.75–0.9x per gradient against Stan's momentum-sum rule; the opt-in
  `UTurnRule::MomentumSum` reaches reference-NUTS parity on the targets
  measured. [E5, E6]

The wins measured so far come from funnel-type targets and from structured
metrics, not from throughput on the posteriordb set. If your model is an
ordinary regression that CmdStan already samples cleanly, CmdStan or nutpie
will use fewer gradients.

## Defaults and opt-ins

`Sampler::new()` with no other calls runs:

| Setting | Default | Why |
|---|---|---|
| warmup / draws / chains | 1,000 / 1,000 / one per start | Stan's shape |
| `Tuning::max_depth` | 10 | ablation over nine posteriordb models: 1.45x ESS per gradient and 17/18 gates against depth 8 [E7] |
| `Tuning::step_size` (`h`) | 0.5 | initial macro step; dual averaging adapts it |
| `Tuning::max_refinement_levels` | 4 | micro-steps down to `h / 16` |
| `Tuning::max_error` (`delta`) | 1 | energy-error threshold per macro step |
| `Adaptation` | dual averaging to acceptance 0.8 | 75 / 25, 50, 100, ... / 50 windows (`gamma` 0.05, `t_0` 10, `kappa` 0.75) |
| `Metric` | adapted diagonal | Welford, regularised |
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
- `Tuning::new().kernel_options(KernelOptions { u_turn: UTurnRule::MomentumSum, ..Default::default() })`:
  Stan's generalised U-turn criterion; 0.81x -> 1.09x reference NUTS on a
  100-D Gaussian, neutral elsewhere, funnel tail mass preserved [E6].
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

- The posteriordb gaps above: 0.23x CmdStan per gradient, two models frozen
  from uniform starts, no throughput win on ordinary regressions [E4].
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
  one checksummed entry per study;
  [`wiki/research-program-2026-08-31.md`](wiki/research-program-2026-08-31.md):
  the program and why.
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
- [E4] posteriordb v2, 32/51 vs 35 and 27, 0.23x / 0.45x per gradient,
  0.77x wall per gradient, 1.1x nutpie ESS/s, `arma11` and `lotka_volterra`
  freezes, gate wins on noncentered eight schools and `gp_pois_regr`, paper
  arm geomean 0.995:
  [`STUDIES/posteriordb_bench_v2`](STUDIES/posteriordb_bench_v2/README.md)
  (`WP23-POSTERIORDB-BENCH-V2`).
- [E5] Refinement on 1–3 % of retained transitions; kernel-side 0.7–0.8x:
  [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E6] U-turn rule 0.75x on the isotropic Gaussian, 1.0x correlated;
  `MomentumSum` 0.81x -> 1.09x; cache one gradient per transition:
  [`STUDIES/kernel_efficiency_v1`](STUDIES/kernel_efficiency_v1/README.md).
- [E7] Depth 10 ablation, 1.45x, 17/18 gates; `stan_style` 2.0x with
  regressions: [`STUDIES/adaptation_parity_v1`](STUDIES/adaptation_parity_v1/README.md).
- [E8] Appendix C on the funnel, 1.41x / 1.61x vs fixed paper tuning:
  [`STUDIES/paper_funnel_adaptive_v2`](STUDIES/paper_funnel_adaptive_v2/README.md)
  (`WP9-PAPER-H-RULE-STABILISATION-V2`).
- [E9] Appendix C v4 robust on the 14 freeze cells, geomean 1.04 vs dual
  averaging:
  [`STUDIES/paper_adaptation_robust_v1`](STUDIES/paper_adaptation_robust_v1/README.md).
