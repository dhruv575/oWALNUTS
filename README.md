# oWALNUTS

`owalnuts` is a minimal Rust crate exposing the reviewed fixed-diagonal oWALNUTS facade.

> **Internal beta:** this is a frozen, non-adaptive kernel for deterministic smooth densities in unconstrained `f64` coordinates. It is not a generally supported or broadly validated production sampler. Heavy-tailed, constrained, hierarchical, and real-model targets are outside the current support scope.

The public API is `owalnuts::walnutpie`. Legacy weighted samplers, NUTS APIs, Python bindings, benchmarks, and prototype APIs are intentionally absent. Numerical implementation modules are private.

## Example

```console
cargo run --example gaussian
```

The facade documentation defines target requirements, resource limits, telemetry, reproducibility, cancellation, and failure behavior. Discarded transitions perform no adaptation.

## Oracle parity

Private test-only modules validate pinned upstream fixtures without exposing prototype APIs:

```console
cargo test oracle_tests
```

See `oracle/walnutpie/f5bba365/README.md` for provenance and focused commands.

## Toolchain

Rust 1.88 or newer is required. CI pins Rust 1.88 GNU on Linux and Windows.

## Support

This release is for evaluation of the documented internal-beta facade only. See [SECURITY.md](SECURITY.md).

## License

MIT. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [THIRD_PARTY.md](THIRD_PARTY.md).
