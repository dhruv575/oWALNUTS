# Preregistration — python_callpath_v1 (WP47)

Frozen 2026-10-24 on `wt/python-callpath` (base `3583d130`) before the first
evidence cell. `protocol.json` is the machine-readable copy. Setup work done
before the freeze and not counted as evidence: building the baseline wheel,
and one value/gradient agreement check of the hand-written targets against
PyMC at three random points (it also warmed PyTensor's compile cache). No
timing and no sampler run was made before the freeze. After the freeze and
before phase 1, the harness is smoke-tested end to end in a throwaway phase
`smoke` (seed 1, outside the evidence seeds); its outputs are deleted and not
used. PyTensor compiles into a private compiledir (`protocol.json`), because
the shared per-user one is lock-contended by sibling agents (the setup check
blocked ~50 minutes on it).

## Question

Since 2026-09-04 the project's goal is large-scale usability, and most users
arrive through `pip install owalnuts` with a Python log density. What does
each Python call path cost per target evaluation, and how does end-to-end
minimum-bulk-ESS per second compare with nutpie on the same models?

Paths: (1) a plain Python callable `logp_and_grad(q) -> (float, ndarray)`;
(2) a numba `cfunc` (`from_cfunc`); (3) `from_jax` (jitted); (4)
`from_torch`; (5) `from_pymc`, which is implemented two ways — the default is
a **Python callable** around PyMC's compiled `logp_dlogp_function` (PyTensor C
backend on this machine), re-entering the interpreter on every call;
`gil_free=True` wraps PyTensor's NUMBA `jit_fn` in a `numba.cfunc` and never
touches the interpreter.

GIL facts from the source (`integrations/python/src/lib.rs`): `sample`
releases the GIL for the whole run (`Python::detach`); each `PyTarget` call
re-attaches (`Python::attach`) from whichever Rust worker thread runs that
chain, allocates a fresh `PyArray1` for the position, calls the callable,
parses the returned tuple and copies the gradient. So a Python callable
serialises all chains on the GIL except for whatever the callable itself
releases (numpy on large arrays, XLA execution, PyTorch ops). Python-side,
`sample` additionally wraps every callable in `wrap_callable` (one extra
Python frame, `float`, `np.ascontiguousarray`, `reshape`). The README
currently says "use `threads=1` for Python targets".

## Targets (`callpath_targets.py`)

All share PyMC's unconstrained layout (value-variable creation order, log
transform for scales), so a position means the same thing in every path.

* `gauss100`: 100-D standard normal.
* `eight`: noncentered Eight Schools `(mu, tau_log__, z[8])`, HalfCauchy(5).
* `hier`: hierarchical regression, 50 groups x 20 observations, intercept +
  two covariates with varying coefficients, noncentered:
  `(mu_beta[3], tau_log__[3], z[50,3], sigma_log__)`, 157 coordinates; data
  simulated once from seed `4747900`.

The numpy / numba / JAX / torch densities drop additive constants; PyMC keeps
them. Gradients agree to rounding.

## Arms

`py-numpy` (idiomatic numpy callable), `py-njit` (plain Python callable around
the numba njit kernel shared with the cfunc arm: isolates transport cost and
is the bit-identity control for `cfunc`), `cfunc`, `jax`, `torch`, `pymc`
(default), `pymc-numba` (`from_pymc(mode="NUMBA")`: same compiled function as
`gil_free`, bit-identity control), `pymc-gilfree`, and `nutpie` (numba
backend, external reference). PyMC callable arms at `threads=4` use
`thread_safe=True` (the documented rule for `threads > 1`). Threads 1 and 4
(nutpie `cores` 1 and 4).

## Protocol

* **Builds.** `baseline` = wheel of `3583d130` (`maturin build --release`,
  GNU 1.88 toolchain) installed non-editable in a private venv whose other
  packages are the shared harness venv's (numpy 2.4.6, numba 0.67.0, JAX
  0.10.2, torch 2.13.0+cpu, PyMC 5.28.5, PyTensor 2.38.2, nutpie 0.16.8,
  Python 3.11.16). `fix` = the same for the fix commit, in a second venv.
* **(a) Micro.** For each target x path: build, prime 128 calls, then 10^4
  individually timed calls (`perf_counter_ns`) through the Python surface
  (cfunc arms through ctypes — labelled, ctypes adds its own cost), median
  reported. Decomposition: `wrap_callable(adapter)`; the njit kernel called
  from Python and inside an njit loop; JAX `jit(value_and_grad)` on a numpy
  argument vs `jnp.asarray`; PyMC `ValueGradFunction.__call__` vs the raw
  PyTensor function vs the raw function with `trust_input=True`.
  In-sampler per-call cost = Rust wall / total target calls at threads=1.
* **(b) Sampler.** `owalnuts.sample` at its defaults, 4 chains x
  1,000/1,000, `init=None`, seeds `4747001, 4747002, 4747003` (exact-word
  verified unused in main and every `wt/*` branch), threads 1 and 4. Wall
  is **contended** (ten agents share 16 cores) and labelled so; arms are
  interleaved (seed outer, target, then the arm x threads list rotated per
  cell block), one child process per cell, strictly sequential. ESS/s = min
  bulk ESS over every unconstrained coordinate (+ theta for `eight`) divided
  by the `sample` wall (construction/compilation reported separately).
* **(c) nutpie** 0.16.8 on the PyMC model, same chains/draws, one run per seed
  per cores setting, interleaved with the owalnuts arms.
* Bit identity: sha256 of the retained draws.
* Every cell is reported; failures are results; nothing is rerun.

## Predictions (frozen)

P1 per-call (micro median through the Python surface; ranges, all targets
unless stated):

| path | gauss100 | eight | hier |
|---|---|---|---|
| py-numpy | 2–8 µs | 8–25 µs | 25–80 µs |
| py-njit | 0.5–3 µs | 0.5–3 µs | 2–8 µs |
| cfunc (in-sampler wall/call, t1) | < 1 µs | < 1 µs | < 5 µs |
| jax | 10–60 µs | 10–60 µs | 15–80 µs |
| torch | 50–400 µs | 100–400 µs | 150–600 µs |
| pymc (C) | 4–15 µs | 4–15 µs | 8–40 µs |
| pymc-gilfree (in-sampler, t1) | < 2 µs | < 2 µs | < 6 µs |

P1b: the transport overhead of the callable path (in-sampler wall/call at t1
minus the micro median of `wrap_callable(adapter)` minus the cfunc in-sampler
wall/call) is 1–5 µs per call.

P2 threads: `threads=4` does **not** help the plain Python path — the
geometric mean (over seeds) ESS/s ratio t4/t1 is <= 1.1 for `py-numpy` and
`py-njit` on every target (and below 1.0 on at least two targets); also <= 1.2
for `jax` and the PyMC callable arms. PyTorch is the exception I expect: its
ops release the GIL, t4/t1 in [0.8, 2.0]. Compiled paths: `cfunc` and
`pymc-gilfree` t4/t1 >= 2.0 on every target (contention caps the ideal 4x).

P3 nutpie: `from_pymc` default ESS/s / nutpie ESS/s (geomean over seeds) is
in [0.1, 0.5] at matched threads=1/cores=1 and in [0.03, 0.3] at 4/4;
`pymc-gilfree` at 4 threads is in [0.6, 1.6] of nutpie cores=4 on every
target.

P4 bit identity: `py-njit` ≡ `cfunc` and `pymc-numba` ≡ `pymc-gilfree` for
every target, seed and thread count; every arm is identical between threads
1 and 4. `py-numpy` ≢ `py-njit` on `gauss100` (BLAS `q @ q` vs sequential
sum) — the difference is rounding only.

P5 ESS per target call agrees across owalnuts arms within Monte-Carlo noise
(each arm within 0.8–1.25x the cfunc arm, geomean over seeds); nutpie's ESS
per leapfrog step within [0.6, 1.6]x owalnuts cfunc.

P6 health: every owalnuts cell R-hat <= 1.01, zero divergences, min bulk and
tail ESS >= 400.

## Fix phase (rule frozen now; the fix itself is chosen from phase-1 data)

Candidate fixes, each required to keep the API backward compatible:

* **F1** callable transport: drop the Python `wrap_callable` frame when the
  return is already `(float, contiguous float64 ndarray)` (coerce in Rust,
  falling back to the Python coercion otherwise).
* **F2** `from_pymc` fast callable: call the compiled PyTensor function
  directly with `trust_input=True` instead of `ValueGradFunction.__call__`
  (same compiled function, so bit-identical by construction).
* **F3** `from_jax` glue: pass the numpy position straight to the jitted
  function and fetch value and gradient in one transfer.
* **F4** `from_torch` glue (avoid the input copy).
* **F5** GIL convoy at `threads > 1`: serialise Python-callback evaluations
  behind a Rust lock so waiting worker threads do not contend for the GIL.
* (Making `gil_free=True` the `from_pymc` default is excluded: it changes the
  compiled backend, hence the draws, and the return type.)

Selection rule: from phase-1 data, pick the candidate with the largest
predicted ESS/s gain on any (path, target, threads) cell, computed as
in-sampler wall/call divided by (wall/call minus the per-call time the
candidate removes, as measured by the micro decomposition, or for F5 the t1
vs t4 gap). Candidates that act on disjoint arms may be bundled into one fix
build; each is judged on its own arms. A phase-2 addendum naming the fix and
the phase-2 arm list (touched arms + `cfunc` control) is committed before
phase 2 runs.

Phase 2: same seeds, same cells, `baseline` and `fix` builds alternating
inside each arm/threads pair (paired under the same contention).

**Decision rule (from the task):** a fix is worth merging iff (i) its draws
are bit-identical to `baseline` on every cell of every touched arm, (ii) the
geometric mean over seeds of the paired fix/baseline ESS/s ratio is >= 1.3 on
at least one target for at least one touched arm/threads, and (iii) no
touched arm/threads/target has that geometric mean below 0.9. The README's
performance guidance is rewritten to match the measurements either way.
