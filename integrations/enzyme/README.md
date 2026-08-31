# owalnuts-autodiff-tape (and the Enzyme probe)

`probe/` is the minimal `#![feature(autodiff)]` program. On the distributed
nightly (`rustc 1.100.0-nightly 2026-08-30`, Windows) it fails with
`autodiff backend not found in the sysroot: … libEnzyme-23 … it will be
distributed via rustup in the future`. Re-run when an `enzyme` rustup component
exists:

```powershell
cd probe; $env:RUSTFLAGS = "-Zautodiff=Enable"; cargo +nightly run
```

The crate itself is the honest fallback measurement: the WP4 Gaussian
local-level log density written once, generic over a `Scalar` trait, and
differentiated by the `reverse` 0.2.2 Wengert tape. Gradients agree with the
hand-written ones to 1e-13; the tape costs 58–68× the hand gradient per call
and 4–11× in ESS/s (see `artifacts/tape-benchmark.json` and
`../AUTODIFF-RESEARCH.md`).

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release
cargo +1.88.0-x86_64-pc-windows-gnu run --release --bin bench
```
