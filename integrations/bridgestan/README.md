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
`Threading::Serialised`. Off Windows,
`ReplicatedStanTarget::load(so, preload, data, seed, threads)` copies the
library to distinct paths and dispatches calls to free replicas. On Windows
it records the requested count but deliberately uses one effective owned
worker; `requested_replicas()` and `replicas()` expose both values.
Multi-worker Windows execution is out of scope until separately qualified.

## Native-library lifetime

On Windows, `StanTarget::load` creates one dedicated OS thread. Library and
symbol loading, model construction, metadata and names, gradients, native
error freeing, and model destruction occur only on that thread. Caller and
Rayon threads exchange bounded requests with it. Drop sends shutdown and
joins without propagating a worker panic; therefore model destruction and the
owner's native TLS teardown complete before drop returns. A disconnected or
panicked worker is a fatal target error.

Windows model and preload DLL handles remain process-resident, preventing TLS
callbacks from reaching unloaded code. A model is first copied into a
process-private cache whose identity is a freshly computed SHA-256 of its
contents; existing copies are rehashed before reuse. The source model is
closed after hashing/copying and is not kept mapped or locked. The cached
model and preload DLLs can remain locked, and native module memory remains
until process exit for each distinct model/preload loaded. Cache directories
hold an exclusive lease; later processes remove directories at least one hour
old only after acquiring the lease. Repeated same-content loads reuse one
cached path and resident module, so load/drop cycles do not create unbounded
files or mappings. On Linux and macOS direct calls, unload-on-drop behavior,
and per-target replica cleanup are unchanged.

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

## Error semantics (robustness fix after `STUDIES/posteriordb_bench_v1`)

A Stan exception, a `-inf`/`NaN`/`+inf` log density, and a finite log
density with a nonfinite gradient are all mapped to the recoverable
zero-density path (`map_evaluation`), which is what CmdStan and nutpie do
with such a proposal. Before this fix a `NaN` log density or gradient was
fatal and killed every `arma11` cell of the benchmark. Only a
position/gradient dimension mismatch remains fatal.
