# oWALNUTS

`owalnuts` is a Rust implementation of **WALNUTS** — the Within-orbit Adaptive
Leapfrog No-U-Turn Sampler (Bou-Rabee, Carpenter, Kleppe, Liu; *JMLR* 27,
2026). WALNUTS keeps the NUTS architecture (stochastic doubling, biased
progressive selection, U-turn stopping) and adds a second time scale: each
macro leapfrog step is subdivided into micro-steps whose count is chosen
adaptively so the local energy error stays below a threshold `delta`. Fine
steps are spent only where curvature demands them, which is what lets it
sample multi-scale targets such as Neal's funnel without the bias fixed-step
NUTS shows there.

The numerical kernel is derived from, and tested leaf-for-leaf against, the
Flatiron reference implementation
[`walnutpie`](https://github.com/flatironinstitute/walnutpie) (MIT). The
recommended API is `owalnuts::sampler` (a builder over the complete facade in
`owalnuts::walnutpie`); the kernel itself is private.

**Status: release candidate (`0.1.0-beta.2`).** The kernel is at revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. What is and is not
validated is listed below; every number links to a preregistered, checksummed
study in `STUDIES/` and an entry in `wiki/research-ledger-2026-08-31.md`.

## Quick start

```toml
[dependencies]
owalnuts = "0.1.0-beta.2"
```

Implement `Target` (log density and gradient in one call, unconstrained `f64`
coordinates), then sample:

```rust,ignore
use owalnuts::sampler::{Metric, Sampler, Target, TargetError};

struct Gaussian;
impl Target for Gaussian {
    fn dimension(&self) -> usize { 2 }
    fn log_density_gradient(&self, q: &[f64], grad: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in grad.iter_mut().zip(q) { *g = -x; }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

let posterior = Sampler::new()
    .warmup(1_000)                 // discarded, adapts step size and metric
    .draws(2_000)                  // retained per chain
    .seed(0x5eed)
    .metric(Metric::diagonal())    // adaptive diagonal mass (the default)
    .run(&Gaussian, &[vec![0.1, -0.2], vec![-0.3, 0.4]])?;   // one start per chain
for draw in posterior.draws() {    // &[f64], chain by chain
    let _ = draw[0];
}
let work = posterior.total_target_calls();       // exact target-call accounting
let chain = &posterior.chains()[0];              // draws, diagnostics, telemetry, metadata
```

`Sampler` also takes `.chains(n)` (replicates a single start), `.threads(n)`
(output is independent of the thread count), `.adaptation(..)`, `.tuning(..)`
(step size, depth, refinement levels, `delta`), and `.limits(..)`
(target-evaluation budget, deadline, cancellation). Every path is a thin
wrapper over one `walnutpie` entry point and produces bit-identical draws to
calling it directly; `walnutpie` remains public for the full contract.

Three worked examples:

| Example | Shows |
|---|---|
| `cargo run --release --example gaussian` | the `Sampler` builder on a 2-D Gaussian: single/multi-chain, telemetry, determinism |
| `cargo run --release --example funnel_paper_adaptation` | Neal's funnel with the paper's Appendix C warmup; prints the tail mass `P(omega<-5)` against the exact 0.0478 |
| `cargo run --release --example state_space_path_metric` | a T=200 state-space path with the posterior-precision tridiagonal metric versus identity, against the exact posterior mean |

### Hard targets: the paper's adaptation

For funnel-like or stiff targets, opt into the JMLR Appendix C rules instead of
acceptance-driven dual averaging:

```rust,ignore
use owalnuts::sampler::{Adaptation, Limits, Metric, PaperAdaptationConfig, Sampler, Tuning};

let posterior = Sampler::new()
    .warmup(2_000)
    .draws(20_000)
    .seed(seed)
    .metric(Metric::Identity)                                    // only delta and h adapt
    .adaptation(Adaptation::Paper(PaperAdaptationConfig::default())) // Delta = 2, p_a = 0.95, Gamma = 0.8
    .tuning(Tuning::new().step_size(0.1).max_depth(10).max_refinement_levels(8).max_error(1.0))
    // Deep refinement x deep trees exceeds the conservative admission ceiling;
    // admit the run with its exact worst-case evaluation count instead.
    .limits(Limits::new().admit_worst_case())
    .run(&target, &starts)?;
```

`delta` (`max_error`) follows the K-quantile rule
`delta = Delta / max(1, q_{p_a}(K))` with `K = (H_max − H_min)/delta` per orbit;
`h` (`step_size`) is dual averaged so that a fraction `Gamma` of built macro
leaves needs no refinement. Both are frozen before the first retained draw and
reported through `RunTelemetry::paper_adaptation_updates`. On Neal's funnel
from `delta = 1, h = 0.1` this is unbiased and 1.41×/1.61× (bulk/tail ESS per
target call) more efficient than the paper's own fixed funnel tuning
(`WP9-PAPER-H-RULE-STABILISATION-V2`). `PaperRestartPolicy` and
`PaperStepStatistic` expose the alternatives that were tested and rejected.

### Structured metrics

`StructuredBlockMass` (`BidiagonalCholesky`, `ScaledAr1`; linear time),
`DenseMass`, `BlockDiagonalMass`, and `LowRankArrowheadMass` are fixed momentum
covariances `M` (kinetic energy `p'M⁻¹p/2`); `Metric::Structured` and
`Metric::Dense` run them from the `Sampler`. For a Gaussian state-space path,
supplying the tridiagonal posterior precision `Q_rw + diag(1/r_t)` as `M`
(its Cholesky factor is bidiagonal) whitens the whole path: trajectories
U-turn at depth 3–4 at any `T`, whereas a prior-based metric collapses the
step and caps the tree at `T = 1000` (`WP4-ESSGT-V1`). The versioned
`sample_direct_original_q` family (research feature) runs the same metrics
directly in target coordinates (`DIRECT_ORIGINAL_Q_REVISION`).

When the right block depends on parameters that are themselves being sampled
(for a state-space path, the innovation scale and observation noise),
`Metric::StructuredRefresh` (`sample_chains_structured_refresh`) rebuilds the
`StructuredBlockMass` from a caller-supplied `StructuredMetricRefresh` at every
completed slow warmup-window boundary and freezes it before retention. Installations never
change the position or its cached evaluation, failed candidates keep the
previous metric, and every boundary emits a typed `StructuredRefreshUpdate`
(`STRUCTURED_REFRESH_REVISION`).

## Diagnostics

`owalnuts::diagnostics` gives Stan/ArviZ-style summaries without Python:
rank-normalised folded split R-hat, bulk and tail ESS, MCSE of the mean, and
5/50/95% quantiles per parameter (Vehtari et al. 2021, validated against
`az.rhat`/`az.ess`/`az.mcse` to 1e-6 from a committed fixture), plus
sampler-health counts read from the telemetry (divergences, invalid
evaluations, depth-cap and refinement-level exhaustions, mean tree depth,
step size) per chain and pooled. `owalnuts::export` writes CmdStan-format
CSVs that `arviz.from_cmdstan` loads directly.

```rust,ignore
use owalnuts::{diagnostics::Summary, export::CmdStanCsv};

let names = target.parameter_names();
let summary = Summary::from_output(&output, names.as_deref())?;
println!("{summary}");                       // aligned table + health block
let worst_rhat = summary.parameters.iter().map(|p| p.rhat).fold(f64::NAN, f64::max);

// One CSV per chain: lp__ (recomputed from the target), stepsize__,
// treedepth__, n_leapfrog__ (fused target calls), divergent__, energy__, draws.
let paths = CmdStanCsv::new()
    .with_parameter_names(names.as_deref().unwrap_or(&[]))
    .with_log_density(&target)
    .write_dir(&output, "out", "chain")?;   // out/chain-1.csv ... out/chain-K.csv
// Python: az.from_cmdstan(posterior=["out/chain-1.csv", ...])
```

The per-parameter estimators also accept plain `&[&[f64]]` chain views
(`diagnostics::rhat`, `ess_bulk`, `ess_tail`, `ess_quantile`, `mcse_mean`),
so draws from any sampler can be summarised. `accept_stat__` is not exported:
the kernel records its acceptance statistic only during warmup.

## Validated results (2026-08-31)

| Target | Result | Ledger entry |
|---|---|---|
| Neal's funnel, paper tuning (δ=0.21, h=0.36, depth 10), 4×50k | P(ω<−5) **0.0474** vs exact 0.0478; var(ω) 9.04 vs 9; 0 divergences/invalid/exhaustions. The reference at identical tuning: 0.0477. Kernel `v8` gave 0.0971 (bias, fixed in `v9`). | WP6-FUNNEL-BIAS-FIX-V9 |
| Neal's funnel, Appendix C warmup from δ=1, h=0.1 | unbiased; final-step spread ≤1.27× across chains; 1.41×/1.61× ESS/call vs fixed paper tuning | WP9-PAPER-H-RULE-STABILISATION-V2 |
| Noncentered Eight Schools, strict matched track (4 chains, 1,000/1,000, target .95, depth 8, adapted diagonal, one thread) | conservative minimum over 7 seeds × 6 functionals **12,830 bulk / 10,346 tail ESS/s**; CmdStan 6,290/3,951, BlackJAX 5,645/4,195, NumPyro 5,241/4,050 on the same track. ESS per target call unchanged by the `v9` fix (0.96/0.99). Walls measured on a loaded machine; NextStat is faster on a non-strict public-API track. | WP8-EIGHT-SCHOOLS-V9-REBENCH-V1 |
| Eight Schools, outer-selection ablation | biased progressive selection (default) 1.75× ESS/call over exact multinomial, no tail penalty | WP3-1 |
| Exact Gaussian state space, T=100/1000 | posterior-precision path metric mixes at depth 3–4 at Monte-Carlo accuracy; ESS/call 4.8× identity, ~1,000× prior-based | WP4-ESSGT-V1 |
| Polyscope canonical-v2 state-space posterior, T=1000, regular fixture | adapted diagonal in centered coordinates passes every gate NumPyro NUTS passes, **confirmed on 3/3 fresh seeds**; the posterior-precision path block agrees with both on every seed and is 2.7× more efficient per call, but passed the strict conjunctive gate on 2/3 seeds (one R-hat of 1.0102 on `beta`), so it is not yet confirmed | WP4B-REAL-TARGET-PATH-METRIC-V1, WP12-SSPD11-CONFIRMATION-V1 |
| Stock–Watson SV (simulated) | Appendix C arm passes all gates on 2/3 fresh seeds at 4×2,000 (the miss is R-hat 1.0101 with clean health) and is 2.0× ESS/call vs fixed paper tuning; the paper's energy-error contrast did not reproduce on this series | WP2b-SW-REPRO-V1, WP12-SSPD11-CONFIRMATION-V1 |

## Oracle parity

Private test-only modules compare the kernel with pinned outputs of the
unmodified upstream headers (`cargo test oracle_tests`):

- `oracle/walnutpie/f5bba365`: 54 Gaussian macro-leaf, span, transition, and
  transition-sequence units;
- `oracle/walnutpie/f5bba365_funnel_leaves`: 4,000 Neal's-funnel macro leaves
  across four tunings and ω ∈ [−8, 4] — decision, level, endpoint, adaptation
  statistic, target calls agree to 1e-11 (kernel `v8` disagreed on 1,555);
- `oracle/walnutpie/f5bba365_invalid_leaves`: 4,000 leaves against a throwing
  wall target, pinning the `v10` rule that a recoverable failure refines like
  any over-tolerance micro-step.

Orbit-level parity on hard targets is covered statistically
(`STUDIES/funnel_bias_fix_v1`, `STUDIES/paper_funnel_reproduction_v1`), not by
pinned orbit fixtures.

## Known limitations

- Paper adaptation is supported by the diagonal and fixed-operator facades
  only; the dense-adaptive, projected and pooled facades reject it.
- The σ_x → 0 funnel cell of the state-space family (`sspd-10`) is not
  sampled by any Euclidean sampler tested, NumPyro NUTS included; it needs a
  reparameterisation, not a metric.
- Stock–Watson evidence is simulated data at 4×2,000 draws (2/3 seeds pass
  the strict R-hat gate); the paper's real inflation series was not
  available.
- On an exactly whitened Gaussian a fixed macro step can alias the
  tree-doubling schedule (see `examples/state_space_path_metric.rs`); there is
  no step-jitter option.
- Seeds reproduce runs only under the same kernel revision, crate build, lock
  file, target architecture and thread-independent deterministic target.
- Cancellation and deadlines are cooperative; a callback that never returns
  cannot be interrupted (isolate untrusted targets in a killable process).
- `ResourceLimits` are preflight ceilings for accounted allocations, not
  process memory.

## API stability

`owalnuts::sampler` and `owalnuts::walnutpie` are public and follow semver
from `0.1.0`. Research-only items (`OuterOrbitSelection`,
`ResearchTargetEvaluationLimit`, `ResearchRestartReferenceMultiplier`,
`DualAveragingAcceptance::AcceptedTrajectory`, the `direct_original_q`
family, and the projected/pooled arrowhead facades) are exported from
`walnutpie` only with the `research` Cargo feature
(`owalnuts = { version = "...", features = ["research"] }`) and may change or
disappear between minor versions. The `STUDIES/` crates and the Python
integration enable it.

## Research-only evaluation ceiling

Production runs retain a conservative `113_000_000` target-evaluation
preflight ceiling. With the `research` feature, a bounded experiment that
needs a larger conservative preflight estimate may construct
`ResearchTargetEvaluationLimit` and attach it with
`RunConfig::with_research_target_evaluation_limit`; this raises only that
ceiling, up to `RESEARCH_MAX_TARGET_EVALUATIONS`, and records
`TargetEvaluationLimitProvenance::ExplicitResearchOptIn` in `RunMetadata`. It
does not raise dimension, chain, transition, or memory caps and does not relax
cancellation checks. Without the feature, `Limits::max_target_evaluations` /
`Limits::admit_worst_case` (`sample_chains_with_target_budget`) admit a run
against an explicit `TargetEvaluationAdmissionLimit` and a runtime
`TargetEvaluationBudget`.

## Research record

- `wiki/research-program-2026-08-31.md` — the program that produced this
  release and why.
- `wiki/research-ledger-2026-08-31.md` — one checksummed entry per study.
- `wiki/sampler-path-ledger.md` — implementation milestones and invariants.
- `wiki/release-0.1.0-beta.2.md` — release summary and erratum.
- `STUDIES/` — every preregistration, runner, artifact and checksum.

## Toolchain

Rust 1.88 or newer. CI runs GNU 1.88 on Linux and Windows plus Linux stable:
tests (including all oracles), strict Clippy, `fmt --check`, `-D warnings`
rustdoc, examples, and `cargo package`.

## Support and license

See [SECURITY.md](SECURITY.md) for scope. MIT; see [LICENSE](LICENSE),
[NOTICE](NOTICE), and [THIRD_PARTY.md](THIRD_PARTY.md) for the walnutpie
provenance.
