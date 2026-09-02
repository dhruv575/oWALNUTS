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

The first build compiles Stan Math (~2 min); later models take ~20 s. Always
pass `STAN_THREADS=true` so one model instance can serve the parallel facade
entry points; without it `StanTarget` serialises evaluations through a mutex.

## Use

```rust
let target = StanTarget::load(
    Path::new("models/eight_schools_model.so"),
    &default_preload(),               // tbb.dll on Windows
    Some(r#"{"J":8,"y":[...],"sigma":[...]}"#),
    1,
)?;
let out = sample_chains(&target, &starts, &DiagonalMass::identity(dim), &config, threads)?;
```

Semantics: unconstrained coordinates, `propto=false`, `jacobian=true`; a Stan
exception or `-inf` log density is a *recoverable* (zero-density) proposal,
which kernel v10 refines through exactly like the walnutpie reference.

## Verify and measure

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release     # skips if models are not built
cargo +1.88.0-x86_64-pc-windows-gnu run --release --bin bench
```

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
