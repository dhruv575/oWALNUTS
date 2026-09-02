# owalnuts-bridgestan

An `owalnuts::walnutpie::Target` over a BridgeStan-compiled Stan model: write
the model in Stan, get Stan Math reverse-mode gradients, sample with the
oWALNUTS kernel. Hand-written `libloading` FFI (no bindgen/libclang needed).

## Build a model

```powershell
cd ..                                   # integrations/
python -m venv .venv-bs
.\.venv-bs\Scripts\pip install bridgestan numpy
$env:MAKE = "mingw32-make"              # GNU make from the mingw-w64 toolchain
.\.venv-bs\Scripts\python -c "import bridgestan.compile as c; c.compile_model('bridgestan/models/eight_schools.stan', make_args=['STAN_THREADS=true']); c.compile_model('bridgestan/models/local_level.stan', make_args=['STAN_THREADS=true'])"
```

The first build compiles Stan Math (~2 min); later models take ~20 s.

## Recommended build configuration

**Do not pass `STAN_THREADS=true` on Windows (mingw-w64 GCC).** GCC on
mingw-w64 implements thread-local storage by emulation
(`__emutls_get_address` on every access) and Stan Math touches its
thread-local autodiff stack for every node it records, so a threaded build
costs 9-16x more per gradient than the default one on real models
(posteriordb arK 120 vs 12.8 us, hmm_example 445 vs 28 us, eight schools
6.2 vs 0.59 us; the default build matches CmdStan's own per-gradient cost).
Measurements: `STUDIES/posteriordb_bench_v1/artifacts/wall-gap/README.md`.

| setting | recommendation |
|---|---|
| `STAN_THREADS` | **unset** on Windows/mingw. On Linux/macOS (native TLS) it is cheap; measure with `cargo run --release --bin wallgap -- model.so data.json` before deciding. |
| `-O3` | the Stan makefiles' default (`O=3`); nothing to add |
| `CXXFLAGS_OPTIM=-march=native` | not recommended on Windows: no gain on arK, ~15% on hmm_example, and the eight-schools library segfaults at load (Eigen/AVX-512 stack alignment on mingw-w64) |
| `STAN_CPP_OPTIMS=true`, `STAN_NO_RANGE_CHECKS=true` | optional, 5-10%, within noise here; CmdStan does not set them by default either |

```powershell
.\.venv-bs\Scripts\python -c "import bridgestan.compile as c; c.compile_model('bridgestan/models/eight_schools.stan')"
```

A library built without `STAN_THREADS` has one global autodiff stack per
*loaded module*, so a single `StanTarget` serialises its evaluations through
a mutex (shared by every `StanTarget` loaded from the same file) and reports
`Threading::Serialised`. For multi-chain sampling use
`ReplicatedStanTarget::load(so, preload, data, seed, threads)`: it copies
the library to `threads - 1` distinct temporary paths (distinct paths are
distinct modules with their own autodiff stack), loads each, and dispatches
every call to a free replica (one uncontended `try_lock`, ~50 ns). With as
many replicas as calling threads no evaluation ever waits; measured
per-thread cost with 4 threads is within 5-10% of the single-thread cost.
The copies are deleted on drop.

## Use

```rust
let target = StanTarget::load(
    Path::new("models/eight_schools_model.so"),
    &default_preload(),               // tbb.dll on Windows
    Some(r#"{"J":8,"y":[...],"sigma":[...]}"#),
    1,
)?;
let out = sample_chains(&target, &starts, &DiagonalMass::identity(dim), &config, threads)?;

// Multi-chain with the recommended (non-STAN_THREADS) build:
let target = ReplicatedStanTarget::load(&so, &default_preload(), Some(data), 1, threads)?;
```

Semantics: unconstrained coordinates, `propto=false`, `jacobian=true`; a Stan
exception or `-inf` log density is a *recoverable* (zero-density) proposal,
which kernel v10 refines through exactly like the walnutpie reference.

## Verify and measure

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release     # skips if models are not built
cargo +1.88.0-x86_64-pc-windows-gnu run --release --bin bench
cargo +1.88.0-x86_64-pc-windows-gnu run --release --bin wallgap -- model.so data.json [calls] [threads]
```

`wallgap` prints the us per `bs_log_density_gradient` call through
`StanTarget`, through the raw function pointer, with `threads` threads on
one instance, and with `threads` threads on a `ReplicatedStanTarget`.

Results and interpretation: `../AUTODIFF-RESEARCH.md` and
`artifacts/bridgestan-benchmark.json`.

## Facade note (WP18)

`StanTarget` deliberately stays a direct `Target` implementation rather than
routing through the facade's new `RawTarget`: the BridgeStan call is already
GIL-free, and the direct impl preserves Stan's error-message slot
(recoverable domain errors keep their message; fatal messages now also
appear in the facade `Error`'s `Display`). With the new `?Sized` support a
loaded model can be held as `Box<dyn Target>`. All tests pass unchanged
against facade commit `3b14d64`.
