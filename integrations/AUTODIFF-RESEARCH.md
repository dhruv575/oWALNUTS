# Autodiff research track

Status: opened 2026-08-31. Engineering evidence (measured, not preregistered).
Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, GNU Rust 1.88,
Windows 11, 16 cores; timings taken while other agents were running, so treat
wall numbers as upper bounds and per-call ratios as the robust figures.

Sections owned by WP15a: *Survey*, *BridgeStan*, *Enzyme and tapes*, *Facade
proposal*. WP15b appends a *Python* section below.

## Why this track exists

Every `owalnuts::walnutpie::Target` today needs a hand-written gradient. That is
the single largest adoption barrier relative to NumPyro (JAX), Stan (Stan
Math), and nutpie (BridgeStan / numba / JAX). "Winning at autodiff" means a
user writes a model once, in the language they already use, and gets the
oWALNUTS kernel with no gradient code and acceptable per-call overhead.

## Survey: routes to autodiff for a Rust HMC crate

| Route | Users served | Mechanism | Licence | Per-call overhead (expected → measured here) | Who uses it |
|---|---|---|---|---|---|
| (a) **BridgeStan** | Stan users; anyone willing to write Stan | Stan program → shared library with a C API (`bs_log_density_gradient`); Stan Math reverse mode | BSD-3 (Stan Math BSD-3) | µs-scale fixed cost + O(model) → **6.7 µs** (Eight Schools), **8.4 µs** (T=100), **38 µs** (T=1000) | nutpie (Stan backend), walnutpie (upstream reference has a BridgeStan shim) |
| (b) PyMC / numba | PyMC users | nutpie compiles the PyTensor graph with numba or JAX to a C ABI callback | Apache-2.0 | ~1–10 µs | nutpie |
| (c) JAX / PyTorch callback | JAX and PyTorch users | Python-side `value_and_grad` exposed through PyO3; per-call GIL or a compiled XLA callable | Apache-2.0 / BSD | ≥10 µs with GIL; ~µs with a jitted C-callable | NumPyro (native JAX), BlackJAX | 
| (d) **Enzyme** (`std::autodiff`) | Rust users | LLVM-level reverse mode of plain Rust `fn(&[f64]) -> f64`; nightly `-Zautodiff` | MIT/Apache (Rust), LLVM | ~1–3× hand gradient (LLVM optimises the adjoint) → **not measurable here** | Rust ML research; no MCMC crate yet |
| (d′) Tape crates | Rust users today | Wengert-list overloading (`reverse`, `numra-autodiff`, `stanwasm-autodiff`, `yscv-autograd`, …) | `reverse` MIT/Apache-2.0; `numra` non-commercial; others Apache/MIT | 10–100× hand gradient → **58–68×** with `reverse` 0.2.2 | small research crates |
| (e) Rust expression DSL (Stan-Math-style) | Rust users | A `Scalar` trait plus operator overloading over a reusable arena tape with fused lpdf primitives (normal, student_t, cumsum, …) | MIT (ours) | 2–5× hand gradient is the realistic target for a fused-primitive tape | Stan Math (C++) is the existence proof |

Competitor mapping: **NumPyro** = JAX autodiff, compiled per model (30 s–12 min
compile observed in this programme). **Stan/CmdStan** = Stan Math in C++,
compiled per model (~1–2 min). **nutpie** = BridgeStan for Stan models,
numba/JAX for PyMC models. None of them ask the user for a gradient.

### Enzyme status (checked 2026-08-31)

`rustup toolchain install nightly` gives `rustc 1.100.0-nightly (908501772
2026-08-30)` for `x86_64-pc-windows-msvc`; `-Zautodiff` is a recognised flag,
but compiling `#![feature(autodiff)]` fails with:

```
error: autodiff backend not found in the sysroot: failed to find a `libEnzyme-23`
folder in the sysroot candidates: … nightly-x86_64-pc-windows-msvc\lib
  = note: it will be distributed via rustup in the future
```

There is no `enzyme` rustup component on any target yet; Enzyme-enabled
rustc must be built from source with `llvm.enzyme = true`. Linux CI could do
that (hours of build time); it is not a path a downstream user can be asked to
take. `integrations/enzyme/probe/` is the minimal reproduction.

### Recommendation: the most valuable first integration

**BridgeStan first.** Reasons, in order:

1. It covers the largest population of people who already have a model with
   no gradient (every Stan user, plus everyone who can write 20 lines of
   Stan), and it is what nutpie ships — so the comparison is apples to apples.
2. It is done: `integrations/bridgestan` implements `Target` over the C API
   in ~250 lines, agreement with hand-written densities is at floating-point
   precision, exception → zero-density mapping matches kernel v10 and the
   walnutpie reference, and `STAN_THREADS=true` gives real multi-chain
   concurrency.
3. Its overhead is Stan's own gradient cost; that is the cost nutpie and
   CmdStan pay too, so oWALNUTS's kernel efficiency advantage (ESS per
   gradient) survives intact and the wall-clock gap to CmdStan/nutpie on the
   same Stan program becomes a fair contest.

The second integration is the Python callable (WP15b), because it serves JAX,
PyTorch and PyMC users with one mechanism. Enzyme is the long-term answer for
Rust-native models and should be revisited when the component ships; until
then the honest Rust-native option is (e), and the numbers below say why the
off-the-shelf tapes are not it.

## BridgeStan: `integrations/bridgestan`

Build (once per model, ~2 min the first time while Stan Math compiles; ~17 s
after):

```powershell
python -m venv .venv-bs; .\.venv-bs\Scripts\pip install bridgestan numpy
$env:MAKE = "mingw32-make"
.\.venv-bs\Scripts\python -c "import bridgestan.compile as c; c.compile_model('bridgestan/models/eight_schools.stan', make_args=['STAN_THREADS=true'])"
```

Toolchain used: BridgeStan 2.9.0 sources (auto-downloaded to
`~/.bridgestan/bridgestan-2.9.0`), mingw-w64 g++ 16.1.0 (the same compiler as
the WP6/WP10 oracle drivers), TBB from Stan Math. No libclang on this machine,
so the official `bridgestan` Rust crate (bindgen build-dependency) cannot be
built here; the six needed symbols are bound by hand with `libloading` instead.
On Windows `tbb.dll` must be resident before the model library loads
(`default_preload()` handles it).

### Agreement (20 random unconstrained points)

| model | dim | max |Δ log density| | max |Δ gradient| | note |
|---|---:|---:|---:|---|
| Eight Schools (v38 noncentered) | 10 | 1.4e-14 | 2.9e-16 | identical up to constants |
| Local level T=100 | 100 | 265.1 (constant) | 2.3e-13 | Stan includes −½log 2π − log σ terms the hand density omits; gradient identical |
| Local level T=1000 | 1000 | 2680.8 (constant) | 4.5e-13 | same |

### Per-call gradient cost (release, single thread)

| model | hand-written Rust | BridgeStan | ratio |
|---|---:|---:|---:|
| Eight Schools | 40 ns | 6.68 µs (0.59 µs without `STAN_THREADS`, see note) | 167× |
| Local level T=100 | 201 ns | 8.39 µs | 42× |
| Local level T=1000 | 2.88 µs | 38.1 µs | 13× |

> **Note (2026-09-02):** the BridgeStan numbers in this document were measured
> on libraries built with `STAN_THREADS=true`, which on mingw-w64 GCC uses
> emulated TLS for Stan's autodiff stack and costs 9-16x per gradient. Built
> without `STAN_THREADS` the eight-schools gradient is 0.59 µs (15x the hand
> gradient, not 167x). See
> `STUDIES/posteriordb_bench_v1/artifacts/wall-gap/README.md` and
> `bridgestan/README.md` (recommended build configuration).

The ratio shrinks with model size because Stan Math's fixed per-evaluation
cost (arena setup, exception frame, Eigen temporaries, the C call) is a few
microseconds; the model work itself is competitive.

### Paired sampling (same seeds, starts, settings; Eight Schools 4 chains ×
1,000/1,000, sequential)

| config | seed | hand ESS/s (log τ) | BridgeStan ESS/s | calls | trajectories |
|---|---:|---:|---:|---:|---|
| v38 (accept .95) | 82001 | 12,536 | 1,224 | 129,871 = 129,871 | bit-identical |
| v38 | 82002 | 14,434 | 1,462 | 104,669 ≈ 104,672 | identical to rounding |
| v38 | 82003 | 12,264 | 1,246 | 117,452 = 117,452 | bit-identical |
| paper adaptation (Δ=2) | 82001 | 38,569 | 3,425 | 70,547 ≈ 70,828 | same ESS/call |
| paper adaptation | 82002 | 34,513 | 2,618 | 68,272 = 68,272 | bit-identical |
| paper adaptation | 82003 | 28,537 | 2,503 | 66,936 = 66,936 | bit-identical |

Local level (4 chains × 500/2,000, depth 8, 3 levels, dual-averaged step,
adapted diagonal):

| T | threads | hand ESS/s | BridgeStan ESS/s | ratio | BridgeStan 4-thread speed-up |
|---:|---:|---:|---:|---:|---:|
| 100 | 1 | 13,849 | 2,935 | 4.7× | — |
| 100 | 4 | 35,676 | 9,770 | 3.7× | 3.3× |
| 1000 | 1 | 1,193 | 526 | 2.3× | — |
| 1000 | 4 | 3,454 | 1,366 | 2.5× | 2.6× |

Zero recoverable failures in 1.16 M Stan calls; posterior means agree.

### What the numbers mean

* On a tiny model the gradient is no longer the bottleneck for the hand-written
  target (40 ns), so the 6.7 µs Stan gradient dominates and the Eight Schools
  throughput crown (12–15k ESS/s vs NumPyro 5.2k, CmdStan 6.3k) would be
  **lost** through BridgeStan (1.2–1.5k at v38 settings, 2.5–3.4k with paper
  adaptation). That is not an oWALNUTS-specific loss — nutpie and CmdStan pay
  the same gradient — but it means the public speed claim must say "hand-written
  target" or be re-measured through BridgeStan against CmdStan on the same
  `.stan` file. That re-measurement is the natural next study.
* At T=1000 the kernel's own O(d) work is already ~19 µs per target call
  (296 k calls in 6.5 s with a 2.9 µs gradient), so a 38 µs Stan gradient
  costs only 2.3–2.5× in ESS/s. For real state-space models BridgeStan is a
  perfectly usable path today.
* `STAN_THREADS=true` scaling (2.6–3.3× on 4 threads) confirms one model
  instance can back the parallel facade entry points.

## Enzyme and tapes: `integrations/enzyme`

`probe/` documents the Enzyme failure above. The crate itself measures the
off-the-shelf fallback: the local-level log density written **once**, generic
over a `Scalar` trait, evaluated with `f64` or with `reverse::Var`.

| T | hand ns/call | `reverse` tape ns/call | ratio | gradient agreement |
|---:|---:|---:|---:|---:|
| 10 | 21.5 | 1,254 | 58× | 1.1e-13 |
| 100 | 157 | 10,739 | 68× | 2.3e-13 |
| 1000 | 1,446 | 88,276 | 61× | 4.5e-13 |

Paired sampling (4 × 500/2,000, seed 84101): ESS/s hand vs tape 50,639 vs
11,844 at T=100 (4.3×) and 7,268 vs 650 at T=1000 (11×). Correct, but a fresh
`RefCell<Vec<Node>>` tape per call with two-parent nodes and no fused
primitives is 60× the hand gradient — slower than BridgeStan at every size.
`numra-autodiff` is non-commercial-licensed; `stanwasm-autodiff` is an
internal crate of a Stan-to-wasm project (Apache-2.0, struct-of-arrays tape)
and is the most interesting design to study for route (e). Conclusion: no
existing crate makes Rust-native autodiff competitive; route (e) would have to
be built (arena tape reused across calls, fused `normal_lpdf`/`cumsum`
primitives, no per-node allocation) and is a 2–4 week project for a first
useful subset.

## Facade proposal (no `src/` changes made)

1. **Object safety.** Every entry point is `fn f<T: Target>(target: &T, …)`.
   Add `?Sized` (`T: Target + ?Sized`) so `&dyn Target` works; autodiff-backed
   targets are naturally dynamically typed (a loaded library, a Python
   callable). Zero cost for existing callers.
2. **Per-thread model instances.** Not every backend is thread-safe on one
   instance (BridgeStan without `STAN_THREADS`, any Python callable). Add
   ```rust
   pub trait TargetFactory: Send + Sync {
       type Target: Target;
       fn dimension(&self) -> usize;
       fn instantiate(&self, chain: usize) -> Result<Self::Target, TargetError>;
   }
   pub fn sample_chains_per_chain<F: TargetFactory>(factory: &F, …) -> Result<MultiChainOutput, Error>;
   ```
   with the existing `T: Target` functions unchanged (a blanket `impl<T: Target + Clone> TargetFactory for T` covers today's targets).
3. **Error mapping contract.** Document that backends must map a *domain*
   exception (Stan `std::domain_error`, JAX `nan` at an out-of-support point)
   to `TargetError::recoverable`, and a *programming* error to `TargetError::new`
   (fatal) — exactly what `StanTarget` does — and expose
   `TransitionDiagnostics::zero_density_evaluations()` in the Python
   diagnostics so users see refinement-through-failure at work.
4. **Coordinate conventions.** State in the `Target` docs that positions are
   the backend's unconstrained coordinates and that the density must include
   the log-Jacobian (`jacobian = true` in BridgeStan; `transform` in
   NumPyro); add `fn parameter_names(&self) -> Option<Vec<String>>` with a
   `None` default so diagnostics and sample export can be labelled
   (`bs_param_unc_names` provides them).
5. **Batched evaluation (later).** For JAX/vectorised backends a
   `fn log_density_gradient_batch(&self, positions: &[f64], values: &mut [f64], gradients: &mut [f64])`
   default that loops over `log_density_gradient` would let a future kernel
   evaluate the two ends of a doubling in one call; not needed for BridgeStan.

## Next steps

1. Same-`.stan`-file study: oWALNUTS-via-BridgeStan vs CmdStan vs nutpie on
   Eight Schools and on the T=1000 local-level model (preregistered; this is
   the honest public throughput comparison once gradients are equalised).
2. Land facade items 1, 3, 4 (small, additive) so `owalnuts-bridgestan` can be
   published as a crate with the official `bridgestan` crate as an optional
   backend where libclang exists.
3. Track `rustup component add enzyme`; re-run `probe/` when it appears.

## Python callable targets (WP15b)

Package: `integrations/python` — `owalnuts` (PyO3 0.28 + maturin, editable
build verified on Python 3.11/Windows, GNU 1.88 toolchain,
`pyo3/generate-import-lib`). Kernel v10, extension `0.1.0b2`. 10 pytest
adapter/behaviour tests pass; strict Clippy and `fmt --check` clean.

### Design

* Lowest common denominator: `owalnuts.sample(logp_and_grad, dim, ...)` with
  `f(q: float64[dim]) -> (float, float64[dim])`; adapters `from_jax`
  (`jit(value_and_grad)`, x64 forced), `from_torch` (autograd, float64),
  `from_pymc` (`model.logp_dlogp_function(ravel_inputs=True)` + an `unravel`
  helper), `from_numpy`.
* GIL: the Python thread `detach`es for the whole run; each kernel callback
  re-`attach`es from the Rust worker. Python targets are therefore
  GIL-serialised: `threads=4` on a numpy target was *slower* than
  `threads=1` (measured attach-fraction 3.4 = workers queueing), while the
  built-in native targets scale ~2.9× at `threads=4`.
* Error mapping: exceptions in {`ZeroDensityError`, `FloatingPointError`,
  `OverflowError`, `ZeroDivisionError`, `ValueError`} and `-inf`/NaN outputs
  → `TargetError::recoverable` (deterministic zero-density contract, v10
  refine-through semantics; verified by a truncated-Gaussian moment test with
  zero `invalid_evaluation` stops); other exceptions and
  `nonfinite="fatal"` → fatal, with the Python message carried into the
  raised error (the facade `Error` itself does not transport it — see
  proposals). Structured metrics exposed as block dicts plus
  `tridiagonal_precision_mass(diag, off)`; ArviZ `InferenceData` export with
  depth/stops/divergences/refinement-level sample_stats.

### Measured overhead (BENCH.md; fresh seeds 93001–93003, shared machine)

Per fused call: native ~0.6–0.8 µs; PyMC compiled ~6 µs; numpy ~10–13 µs;
JAX jit dispatch ~26–84 µs (dimension-dependent); PyTorch ~170–290 µs.
ESS per call is backend-independent (same kernel; last-bit gradient
differences de-synchronise chains without changing quality; all agreement
z ≤ 2.44). Geomean min-bulk-ESS/s over three seeds:

| target | native | numpy | jax | torch | pymc | NumPyro NUTS (warm) |
|---|---:|---:|---:|---:|---:|---:|
| Eight Schools (v38 settings) | 15,226 (44,749 @4 threads) | 1,029 | 414 | 50 | **1,439** | 897 |
| Local level T=100, identity | 11,272 | 2,582 | 405 | 130 | — | 2,245 |
| Local level T=100, precision metric | 28,199 | **9,712** | 1,777 | 572 | — | — |
| Local level T=1000, identity | 927 | 471 | 151 | — | — | 720 |
| Local level T=1000, precision metric | 3,293 | **2,455** | 801 | 428 | — | — |

Zero divergences/caps everywhere; worst R-hat 1.0061.

### Verdict: when does the Python package beat NumPyro?

* **On NumPyro's own ground (JAX log density): no.** JAX dispatch (~26–64 µs
  × ~15 calls/transition) leaves oWALNUTS+`from_jax` at ~0.2–0.5× NumPyro,
  whose whole transition stays inside one XLA program.
* **With a compiled non-JAX gradient: yes.** PyMC-compiled and plain numpy
  targets beat warm NumPyro at equal settings (1.4–1.6× Eight Schools,
  1.15–3.4× local level), and the structured precision metric — which
  NumPyro cannot express — is 3.4× NumPyro at T=1000 even from Python.
* **Against nutpie on PyMC models: not yet.** nutpie (numba `cfunc`, no GIL,
  4 cores) reached 17,844–25,043 ESS/s vs our 1,298–2,120 (1 core,
  GIL-bound); per-gradient efficiency is comparable (0.028–0.039 exact vs
  0.041–0.048 proxy). The entire gap is callback transport + parallelism,
  not the sampler.

### Facade/package proposals (no `src/` changed by WP15b)

1. `TargetError` message propagation: `Error` should carry the originating
   target message (currently a generic "target evaluation failed"); the
   wrapper works around it with a side channel.
2. A GIL-free raw entry point — `unsafe fn(dim, *const f64, *mut f64) -> f64`
   or a `RawTarget` trait object — so numba/Cython `cfunc` and PyMC's
   compiled functions can be called from parallel chains without attaching.
   This is the single change that closes the nutpie gap; everything else is
   already in place.
3. Optional: free-threaded CPython (3.13t) build and a per-chain
   subprocess/shared-memory mode as fallbacks where (2) is impossible.

Artifacts: `integrations/python/bench/artifacts/{summary.json,pymc-compare.json}`
(quick-run duplicate under `artifacts-quick/`), full log `bench/artifacts-full.log`.

## GIL-free transport (WP18)

Facade commit `3b14d64` landed the autodiff surface proposed above:
`RawTarget`/`RawTargetFn` (C-ABI fused callback; `-inf` → recoverable
zero-density, other nonfinite output fatal), `&dyn`/`Box`/`Arc` targets,
fatal target messages in `Error`'s `Display`, and
`Target::parameter_names`. The package exposes `owalnuts.from_cfunc`
(numba signature in `RAW_CFUNC_SIGNATURE`) and
`from_pymc(model, gil_free=True)`, which wraps PyTensor's NUMBA-mode
`vm.jit_fn` in a `numba.cfunc` — the same transport nutpie uses — and
verifies it against the ordinary compiled path through ctypes before use.

### Rebench (preregistered in BENCH.md; fresh seeds 96001–96003)

Eight Schools PyMC model, 1,000/1,000, 4 chains, accept .95. Geometric-mean
min-bulk ESS/s (range), all cells zero divergences, max R-hat ≤ 1.0041,
means agreeing across cells:

| cell | ESS/s | ESS/work (kind) |
|---|---:|---|
| owalnuts from_pymc GIL, t1 | 2,261 [1,997–2,478] | 0.0336 (fused exact) |
| owalnuts cfunc, t1 | 9,979 [8,892–10,911] | 0.0338 (fused exact) |
| **owalnuts cfunc, t4** | **30,982 [29,560–32,533]** | 0.0338 (fused exact) |
| nutpie cores=4 | 27,754 [21,726–36,208] | 0.0431 (leapfrog proxy) |
| nutpie cores=1 | 12,537 [10,829–13,657] | 0.0431 (leapfrog proxy) |
| NumPyro | 1,857 [1,411–2,334] | 0.0427 (leapfrog proxy) |

Per-call: PyMC GIL 5.69 µs → cfunc 1.25 µs. Predictions 1, 2, 3, 5 held
(4.4× from removing the GIL attach; 3.1× thread scaling; **parity with
nutpie**, not merely within 2×); prediction 4 held (per-gradient efficiency
comparable, exact-vs-proxy caveat unchanged). The WP15b conclusion is
therefore closed: the nutpie gap was transport, and one facade change plus
~100 lines of adapter removed it. owalnuts-cfunc-t4 had the smallest
seed-to-seed spread of the fast cells.

Local-level T=1000 with the tridiagonal posterior-precision metric via a
numba cfunc: 6,072–6,196 ESS/s at t1 (WP15b numpy cell: 2,455; same-run
numpy control: 4,302) and 20,791–22,471 at t4 — ≈ 29× NumPyro's identity-
metric 720 from WP15b, on a metric NumPyro cannot express. Zero divergences,
R-hat ≤ 1.0028, ESS/call identical across transports (same kernel).

### BridgeStan under the new facade

Not switched to `RawTarget`: `bs_log_density_gradient` is already GIL-free
and direct; a `RawTargetFn` shim would add an indirection and drop the
model's error-message slot (Stan exceptions currently map to
`TargetError::recoverable` with the real message, which the new `Error`
`Display` now surfaces for fatal cases). The crate's 4 tests pass unchanged
against the new facade. The `?Sized`/`Box<dyn Target>` impls let a loaded
Stan model be stored dynamically, which the README now notes.

### Remaining gaps (honest)

* nutpie's numbers remain leapfrog proxies; a same-`.stan`-file strict
  three-way (WP15a next-step 1) is still the publishable comparison.
* `from_pymc(gil_free=True)` snapshots shared-variable values at compile
  time (documented); models mutating `pm.Data` between runs must recompile.
* Free-threaded CPython and per-chain subprocess fallbacks (proposal 3)
  are now unnecessary for numba-capable models and were not built.

## Route (e): fused-primitive tape (`integrations/autodiff`)

Crate `owalnuts-autodiff` (pure Rust, stable 1.88 GNU, `#![forbid(unsafe_code)]`,
one dependency: `libm` for `lgamma`). A model is one generic function
`fn log_density<S: Scalar>(&self, q: &[S]) -> S`; `AutodiffTarget<M>`
implements `Target` by evaluating it with `S = Var` on a reusable
thread-local arena tape. Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`,
same machine as the sections above; per-call figures are best-of-5 rounds
of 4k-200k calls over 16 random points; other agents were running, so treat
the ratios as the robust figures.

### Tape design (what made it 3-4x instead of 60x)

1. `Var { value: f64, index: u32 }` (16 bytes, `Copy`) carries its value, so
   an operation never reads the tape: it appends one node. Inputs are the
   indices `1..=n` with no stored node; constants are index 0 (their adjoint
   goes to a dummy slot, so nothing branches on "is this a constant").
2. Scalar nodes are an enum with inline operand indices and partials
   (`Unary`/`Binary`/`Ternary`, 40 bytes; no boxed closures, no per-node
   allocation). `Var + f64` / `Var - f64` reuse the operand's index.
3. Fused primitives (`normal_lpdf`, `normal_lupdf`, `student_t`, `cauchy`,
   `lognormal`, `exponential`, `gamma`, `half_normal`, `bernoulli_logit`,
   `poisson_log`, `dot`, `sum`, `log_sum_exp`, the constraining transforms)
   record one node per call, made of one *segment* per operand. A segment
   over a contiguous run of tape indices stores partials only and its
   reverse sweep is an `axpy`; any sub-slice of the inputs is detected as
   contiguous in O(1) by address; scattered operands store index/partial
   pairs; broadcast scalars accumulate into one entry. Operand wrappers
   `Const`, `Data`, `Shifted(&x, c)` and `Linear::new(a, b, &x)` (elements
   `a + b x_i`) let data, drift terms and linear predictors enter a
   primitive with no extra nodes; `normal_lupdf` drops the `ln sigma` and
   constant terms when `sigma` is data (Stan `~` semantics).
4. `cumsum` / `cumsum_affine(x, scale, shift)` over a contiguous input is one
   *block* node spanning its `T` outputs whose reverse sweep is a single
   reverse scan (the noncentered local level is 6 real nodes at any `T`).
5. The same elementwise kernel produces the value and the partials on both
   paths, so `f64` and `Var` evaluation are bit-identical by construction.

Iterations measured on the way (Eight Schools fused form / local level
T=1000 `lupdf`): closure-free enum tape with (index, partial) pairs for every
fused entry: 362 ns / 19.2 us; segmented nodes with contiguous `axpy`
sweeps and implicit input leaves: 240 ns / 5.1 us; O(1) contiguity check and
no re-entrant thread-local access inside the fused drivers: 206 ns / 3.9 us.
Thread-local access itself measured 0.9 ns (a `Cell`) to 2 ns (`RefCell<Vec>`
push) per operation, so it is not the bottleneck; a scalar node costs ~5 ns
(the reverse sweep is a store-to-load chain through the adjoint buffer) and a
call ~25 ns fixed (two borrows, reset, input setup, adjoint buffer, gradient
copy) plus ~1 ns per input.

### Agreement (16 random points per model, 50 in the tests)

| model | values | max rel. gradient diff |
|---|---|---:|
| Eight Schools, term-by-term form (57 nodes) | bit-identical to the v38 density | 1.2e-16 |
| Eight Schools, fused form (9 nodes, `normal_lupdf` likelihood) | differ by the constant `sum_j (0.5 ln 2pi + ln se_j)` (spread 2.5e-14) | 1.8e-16 |
| Neal's funnel 10-D | bit-identical to `examples/funnel_paper_adaptation.rs` | 3.1e-16 |
| Local level T=100 / 1000, `normal_lpdf` | bit-identical to a hand density with the same terms | 2.9e-14 |
| Local level T=100 / 1000, `normal_lupdf` vs the WP4 hand form | 5e-11 / 2.8e-9 absolute (different formula for the same quantity) | 1.1e-13 |
| Noncentered local level T=100 / 1000 (`cumsum_affine`) | bit-identical | 7.2e-14 |

Every primitive is also checked against central finite differences (1e-6
relative) in `tests/gradients.rs`, including broadcast, `Data`, `Shifted`,
`Linear`, scattered-versus-contiguous layouts and the cumsum block versus
its chain fallback.

### Per-call gradient cost (release, single thread)

| model | hand-written | value-only `f64` path | autodiff | ratio | tape |
|---|---:|---:|---:|---:|---|
| Eight Schools, term-by-term (bit-identical) form | 31 ns (const data) / 51 ns (struct data) | 68 ns | 407-430 ns | 14x / 8.0x | 57 nodes |
| Eight Schools, fused form | 27 ns (const data) / 51 ns (struct data) | 27 ns | 206 ns | **7.6x / 4.1x** | 9 nodes, 18 partials, 2 indices |
| Neal's funnel 10-D | 7.6 ns | 7.0 ns | 104 ns | 13.7x | 11 nodes, 18 partials |
| Local level T=100, `lupdf` vs WP4 hand | 144 ns | 118 ns | 435 ns | **3.0x** | 5 nodes, 298 partials |
| Local level T=100, `lpdf` vs full hand | 244 ns | 352 ns | 914 ns | 3.7x | 5 nodes, 298 partials |
| Local level T=1000, `lupdf` vs WP4 hand | 1.38 us | 1.18 us | 3.93 us | **2.8x** | 5 nodes, 2998 partials |
| Local level T=1000, `lpdf` vs full hand | 2.39 us | 3.42 us | 8.93 us | 3.7x | 5 nodes, 2998 partials |
| Noncentered local level T=100 | 255 ns | 371 ns | 1.22 us | 4.8x | 106 (6 + 100 fillers) |
| Noncentered local level T=1000 | 2.55 us | 3.62 us | 11.7 us | 4.6x | 1006 (6 + 1000 fillers) |

For comparison, the same three models through BridgeStan cost 6.7 us,
8.4 us and 38 us, and the `reverse`-crate tape 10.7 us (T=100) and 88 us
(T=1000).

Targets: **<= 3x on the T=1000 state space: met (2.8x)**, and 3.0x at T=100.
**<= 5x on Eight Schools and the funnel: not met against the repository's
hand gradients**, for two reasons that the numbers isolate. (i) The study
densities keep the data as compile-time constants, so the compiler folds
`ln(se_j)` and `1/se_j^2` away; a hand gradient that reads its data from a
struct costs 51 ns, against which the fused form is 4.1x. (ii) The funnel
hand gradient is a 10-flop loop at 7.6 ns, below the ~25 ns fixed cost of any
tape call (thread-local borrow, reset, adjoint buffer, gradient copy) plus
~5 ns per scalar node; 11 nodes and a 9-element `dot` give 104 ns. Shrinking
this further needs either compile-time expression templates (no tape at all,
i.e. the Enzyme route once it ships) or a fused-call overhead below ~10 ns;
the remaining per-fused-call cost (~17 ns: two `Vec` resizes, a segment
push, the reverse-sweep segment loop) is where the next 20-30% would come
from. The value-only `f64` path of the fused form equals the hand cost, so
the whole overhead is tape recording and the reverse sweep.

### Paired sampling (same seeds, starts, settings; `artifacts/bench.json`)

Eight Schools, v38 settings (4 chains x 1,000/1,000, accept .95), hand target
= the verbatim v38 density:

| seed | threads | hand wall | autodiff wall | wall ratio | ESS/call hand = autodiff | draws |
|---:|---:|---:|---:|---:|---|---|
| 82001 | 1 | 0.106 s | 0.163 s | 1.53x | 0.01089 = 0.01089 (129,871 calls both) | differ from draw 0 |
| 82001 | 4 | 0.047 s | 0.062 s | 1.34x | same | |
| 82002 | 1 | 0.093 s | 0.144 s | 1.55x | 0.01442 vs 0.01445 (104,669 vs 104,644 calls) | |
| 82002 | 4 | 0.034 s | 0.045 s | 1.36x | same | |
| 82003 | 1 | 0.104 s | 0.155 s | 1.49x | 0.01162 = 0.01162 (117,452 calls both) | |
| 82003 | 4 | 0.041 s | 0.050 s | 1.21x | same | |
| fused form, 82001-82003 | 1 | 0.093-0.120 s | 0.114-0.163 s | 1.23-1.35x | identical to 4 digits | |

Local level (4 chains x 500/2,000, depth 8, 3 levels, hand = WP4 form,
autodiff = `normal_lupdf` form):

| T | threads | hand wall | autodiff wall | wall ratio | calls hand / autodiff | divergences |
|---:|---:|---:|---:|---:|---|---|
| 100 | 1 | 0.620 s | 0.733 s | 1.18x | 241,804 / 248,125 | 0 / 0 |
| 100 | 4 | 0.193 s | 0.239 s | 1.24x | same | |
| 1000 | 1 | 4.54 s | 5.52 s | 1.21x | 296,366 / 300,895 | 2 / 2 |
| 1000 | 4 | 1.17 s | 1.57 s | 1.34x | same | |

Draws are **not** bit-identical: the log-density values are, but the
gradients differ in the last bits (a hand gradient factors the algebra
differently from a reverse sweep), and after a few leapfrog steps the chains
de-synchronise, exactly as observed for the Python backends in WP15b. Two of
the three Eight Schools seeds nevertheless make the same number of target
calls with the same ESS/call to four digits, posterior means agree, and
divergence counts match. Single-functional batch-means ESS is noisy across
de-synchronised chains (T=1000 shows autodiff "ahead" on ESS/s while its wall
time is 1.21x longer), so the wall-time ratio is the honest end-to-end cost:
1.2-1.5x on Eight Schools, 1.2-1.3x on the state space, versus the 4.7-11x
of the `reverse` tape and the 2.3-10x of BridgeStan in the sections above.

### What this means for the facade

Route (e) is now the Rust-native answer while Enzyme is unavailable: a
20-line model, no gradient code, 3-4x per-call cost on realistic models and
1.2-1.5x end to end, with per-thread tapes so the existing parallel entry
points work unchanged. The crate implements `Target` directly (nothing in
`src/` changed). Follow-ups in order of value: (1) point users at
`last_tape_stats` in the docs so they see when a loop should be a fused
call; (2) a fused-call fast path with the segment inline in the node for the
single-contiguous-operand case (most of the remaining 17 ns); (3) a
multivariate normal / Cholesky primitive for the structured-metric studies;
(4) re-measure against Enzyme when `rustup component add enzyme` exists.
