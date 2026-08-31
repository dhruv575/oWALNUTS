# oWALNUTS

`owalnuts` is a minimal Rust crate exposing the reviewed fixed-diagonal oWALNUTS facade.

> **Internal beta:** this is a frozen, non-adaptive kernel for deterministic smooth densities in unconstrained `f64` coordinates. It is not a generally supported or broadly validated production sampler. Heavy-tailed, constrained, hierarchical, and real-model targets are outside the current support scope.

The public API is `owalnuts::walnutpie`. Legacy weighted samplers, NUTS APIs, Python bindings, benchmarks, and prototype APIs are intentionally absent. Numerical implementation modules are private.

## Example

```console
cargo run --example gaussian
```

The facade documentation defines target requirements, resource limits, telemetry, reproducibility, cancellation, and failure behavior. Discarded transitions perform no adaptation.

## Research-only evaluation ceiling

Production runs retain a conservative `113_000_000` target-evaluation
preflight ceiling. A bounded warmup experiment that needs a larger conservative
preflight estimate must explicitly construct `ResearchTargetEvaluationLimit`
and attach it with `RunConfig::with_research_target_evaluation_limit`. This
raises only that one ceiling, up to the hard absolute
`RESEARCH_MAX_TARGET_EVALUATIONS` value.

The opt-in does not raise dimension, chain, transition, result-memory, or
working-memory caps. It does not disable or relax cancellation and deadline
checks. Successful output records both the effective ceiling and
`TargetEvaluationLimitProvenance::ExplicitResearchOptIn` in `RunMetadata`.
This mechanism is for controlled research experiments, not a production-default
change or a guarantee that a target callback can be forcibly interrupted.

## Oracle parity

Private test-only modules validate pinned upstream fixtures without exposing prototype APIs:

```console
cargo test oracle_tests
```

See `oracle/walnutpie/f5bba365/README.md` for provenance and focused commands.

## Direct original-coordinate metrics

The versioned `sample_direct_original_q` family accepts
`DirectOriginalQMass::{Dense, BlockDiagonal, StructuredPath,
LowRankArrowhead}` and executes Hamiltonian dynamics directly in target
coordinates. Its execution identity is `DIRECT_ORIGINAL_Q_REVISION`.

These APIs are mathematically equivalent to the corresponding fixed
Cholesky-coordinate formulation: momentum has covariance `M`, velocity is
`M^-1 p`, and kinetic energy is `p' M^-1 p / 2`. They intentionally make no
bit-identity promise relative to legacy wrappers. Matrix solves, drift updates
and dot products occur in a different floating-point order and can therefore
produce last-bit differences while representing the same transition kernel.
Legacy public fixed-metric APIs retain their existing wrappers and revision.

## Experiment ledger

- **2026-08-29 — Neal funnel health pilot v1:** authorized bounded pilot,
  seeds `2026090101`--`2026090103`, 12 frozen cells. All cells completed under
  callback and wall caps with zero corrected divergences, but no setting met
  the rank R-hat/bulk ESS/tail ESS eligibility gates across all seeds. No
  setting was selected and confirmation is not authorized. See
  `STUDIES/neal_funnel_health_pilot_v1/README.md`; decision-bearing summary
  SHA-256 is
  `7049a5a843fde48ea6bf3ca04c391c84684b59b99111763e99ef123b487d3d39`.

## Toolchain

Rust 1.88 or newer is required. CI pins Rust 1.88 GNU on Linux and Windows.

## Support

This release is for evaluation of the documented internal-beta facade only. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [THIRD_PARTY.md](THIRD_PARTY.md).
