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
[`walnutpie`](https://github.com/flatironinstitute/walnutpie) (MIT). The public
API is the single module `owalnuts::walnutpie`; the kernel itself is private.

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
use std::num::NonZeroUsize;
use owalnuts::walnutpie::{DiagonalMass, KernelTuning, RunConfig, WarmupConfig, sample_chains};

let nz = |n| NonZeroUsize::new(n).unwrap();
// h = 0.5, depth 8, 1 minimum micro-step, up to 4 refinement levels, delta = 1.0
let tuning = KernelTuning::new(0.5, nz(8), nz(1), nz(4), 1.0)?;
let config = RunConfig::new(500, nz(2_000), 0x5eed)          // discarded, retained, seed
    .with_tuning(tuning)
    .with_warmup(WarmupConfig::new(0.8)?);                     // dual-averaged step + diagonal mass
let output = sample_chains(&target, &starts, &DiagonalMass::identity(nz(dim)), &config, nz(4))?;
for chain in output.chains() {
    let draws = chain.samples();          // flat [draw][parameter]
    let work  = chain.telemetry().total(); // exact target-call accounting
}
```

Three worked examples:

| Example | Shows |
|---|---|
| `cargo run --release --example gaussian` | the full facade on a 2-D Gaussian: single/multi-chain, telemetry, determinism |
| `cargo run --release --example funnel_paper_adaptation` | Neal's funnel with the paper's Appendix C warmup; prints the tail mass `P(omega<-5)` against the exact 0.0478 |
| `cargo run --release --example state_space_path_metric` | a T=200 state-space path with the posterior-precision tridiagonal metric versus identity, against the exact posterior mean |

### Hard targets: the paper's adaptation

For funnel-like or stiff targets, opt into the JMLR Appendix C rules instead of
acceptance-driven dual averaging:

```rust,ignore
use owalnuts::walnutpie::{PaperAdaptationConfig, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, sample_chains_with_target_budget};

let tuning = KernelTuning::new(0.1, nz(10), nz(1), nz(8), 1.0)?;   // conservative start
let warmup = WarmupConfig::default()
    .with_mass_adaptation(false)
    .with_paper_adaptation(PaperAdaptationConfig::default());     // Delta = 2, p_a = 0.95, Gamma = 0.8
let config = RunConfig::new(2_000, nz(20_000), seed).with_tuning(tuning).with_warmup(warmup);
// Deep refinement × deep trees exceeds the conservative admission ceiling;
// admit the run with its exact worst-case evaluation count instead.
let worst = config.worst_case_target_evaluations(nz(4))?;
let output = sample_chains_with_target_budget(&target, &starts, &mass, &config, nz(4),
    TargetEvaluationAdmissionLimit::new(nz(worst)), &TargetEvaluationBudget::new(nz(worst)))?;
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
covariances `M` (kinetic energy `p'M⁻¹p/2`). For a Gaussian state-space path,
supplying the tridiagonal posterior precision `Q_rw + diag(1/r_t)` as `M`
(its Cholesky factor is bidiagonal) whitens the whole path: trajectories
U-turn at depth 3–4 at any `T`, whereas a prior-based metric collapses the
step and caps the tree at `T = 1000` (`WP4-ESSGT-V1`). The versioned
`sample_direct_original_q` family runs the same metrics directly in target
coordinates (`DIRECT_ORIGINAL_Q_REVISION`).

## Validated results (2026-08-31)

| Target | Result | Ledger entry |
|---|---|---|
| Neal's funnel, paper tuning (δ=0.21, h=0.36, depth 10), 4×50k | P(ω<−5) **0.0474** vs exact 0.0478; var(ω) 9.04 vs 9; 0 divergences/invalid/exhaustions. The reference at identical tuning: 0.0477. Kernel `v8` gave 0.0971 (bias, fixed in `v9`). | WP6-FUNNEL-BIAS-FIX-V9 |
| Neal's funnel, Appendix C warmup from δ=1, h=0.1 | unbiased; final-step spread ≤1.27× across chains; 1.41×/1.61× ESS/call vs fixed paper tuning | WP9-PAPER-H-RULE-STABILISATION-V2 |
| Noncentered Eight Schools, strict matched track (4 chains, 1,000/1,000, target .95, depth 8, adapted diagonal, one thread) | conservative minimum over 7 seeds × 6 functionals **12,830 bulk / 10,346 tail ESS/s**; CmdStan 6,290/3,951, BlackJAX 5,645/4,195, NumPyro 5,241/4,050 on the same track. ESS per target call unchanged by the `v9` fix (0.96/0.99). Walls measured on a loaded machine; NextStat is faster on a non-strict public-API track. | WP8-EIGHT-SCHOOLS-V9-REBENCH-V1 |
| Eight Schools, outer-selection ablation | biased progressive selection (default) 1.75× ESS/call over exact multinomial, no tail penalty | WP3-1 |
| Exact Gaussian state space, T=100/1000 | posterior-precision path metric mixes at depth 3–4 at Monte-Carlo accuracy; ESS/call 4.8× identity, ~1,000× prior-based | WP4-ESSGT-V1 |
| Polyscope canonical-v2 state-space posterior, T=1000, regular fixture | passes every gate NumPyro NUTS passes; posterior-precision path block 2.8× ESS/call over adapted diagonal (12 s vs NumPyro 47 s, different work units) | WP4B-REAL-TARGET-PATH-METRIC-V1 |
| Stock–Watson SV (simulated, one seed per arm) | Appendix C arm passes all gates, 2.0× ESS/call vs fixed paper tuning; the paper's energy-error contrast did not reproduce on this series | WP2b-SW-REPRO-V1 |

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
- Stock–Watson evidence is one seed per arm; the paper's real inflation
  series was not available.
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

Only `owalnuts::walnutpie` is public. Items documented as *research-only*
(`OuterOrbitSelection`, `ResearchTargetEvaluationLimit`,
`DualAveragingAcceptance::AcceptedTrajectory`, the projected/pooled arrowhead
facades) may change or disappear between minor versions. Everything else
follows semver from `0.1.0`.

## Research-only evaluation ceiling

Production runs retain a conservative `113_000_000` target-evaluation
preflight ceiling. A bounded experiment that needs a larger conservative
preflight estimate must explicitly construct `ResearchTargetEvaluationLimit`
and attach it with `RunConfig::with_research_target_evaluation_limit`; this
raises only that ceiling, up to `RESEARCH_MAX_TARGET_EVALUATIONS`, and records
`TargetEvaluationLimitProvenance::ExplicitResearchOptIn` in `RunMetadata`. It
does not raise dimension, chain, transition, or memory caps and does not relax
cancellation checks. Alternatively, `sample_chains_with_target_budget` admits a
run against an explicit `TargetEvaluationAdmissionLimit` and a runtime
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
