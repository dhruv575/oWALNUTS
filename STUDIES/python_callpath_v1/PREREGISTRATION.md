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

## Amendment A1 (frozen after the harness smoke test, before the first phase-1 cell)

The smoke cell `eight / pymc / threads=4` (seed 1) had not finished after
35 minutes. A diagnostic probe (`from_pymc(model, thread_safe=True)`, Eight
Schools, 4 chains x 30/30, threads=4, a counter on
`Model.logp_dlogp_function`) logged **349 PyTensor compilations on the same 4
OS threads in ~8 minutes**: the per-thread function cache of
`thread_safe=True` (a `threading.local`) is empty on almost every callback.
Mechanism (hypothesis, tested by the fix): at `threads > 1` the callbacks run
on Rayon worker threads that have no Python thread state, so every
`Python::attach` creates a fresh `PyThreadState` (`PyGILState_Ensure`) and
destroys it on release — and every `threading.local` value with it. At
`threads=1` the chains run on the calling (main) thread, whose thread state
persists, so the bug is invisible there. The same churn taxes every Python
callable at `threads > 1` (thread-state allocation per call, and any
framework thread-local state such as JAX's is rebuilt per call).

Consequences, fixed now:

1. The baseline `pymc` and `pymc-numba` cells at `threads=4` cannot complete
   (a full cell is ~10^5 callbacks at ~1 s each). They run for seed
   `4747001` only, with a 600 s cap (a timeout is recorded as the result);
   their other 12 cells are recorded as `not_run_amendment_A1`. Every other
   cell is unchanged. The child-process timeout now kills the whole process
   tree (the venv launcher spawns the interpreter).
2. New fix candidate **F6**: pin one Python thread state per Rayon worker
   thread for the duration of a callable run (created on the first callback
   on a thread that has none, released when the scoped worker exits). It
   changes no arithmetic, so draws are bit-identical by construction.
3. Added predictions: **P7** the six short baseline cells time out at 600 s.
   **P8** if F6 is selected: fixed `pymc` / `pymc-numba` at `threads=4`
   complete every cell; fixed/baseline paired ESS/s at `threads=4` for
   `py-numpy`, `py-njit`, `jax` and `torch` lies in [1.0, 1.6] (thread-state
   churn is a small part of a GIL-serialised callback); `threads=1` cells are
   unaffected (ratio in [0.9, 1.1]) and bit-identical.

The selection rule and decision rule are unchanged; F6 joins F1–F5. For the
`pymc` / `pymc-numba` t4 arms a baseline timeout counts as ESS/s = 0 (any
completing fix cell satisfies the 1.3x criterion), and the paired ratio is
reported for seed `4747001` only.

## Amendment A2 (post hoc; frozen after the first `hier / cfunc` cells failed, before any supplementary cell)

The phase-1 `hier / cfunc` cells fail at transition 0 with `raw target wrote
a nonfinite gradient element (NaN)`: the raw C ABI (`RawTarget`) treats a
finite log density with a nonfinite gradient as fatal, whereas the callable
transport's default `nonfinite="zero_density"` turns any nonfinite value or
gradient into a recoverable zero-density proposal (and `from_pymc(gil_free=True)`
guards its cfunc the same way). My cfunc wrapper did not guard. The failed
cells stand as results (a naive cfunc port of a callable that samples fine
can fail on the first diverging leapfrog — a usability finding the README
must state); they are not rerun.

Supplementary arm, run after phase 1 as phase `phase1b` (same seeds, same
cells, `baseline` build, interleaved with fresh `py-njit` and `cfunc` cells
for a contemporaneous wall reference): **`cfunc-guarded`** = the same njit
kernel in a cfunc that zeroes the gradient and returns `-inf` when the value
or any gradient element is nonfinite (exactly the callable path's default
policy). Predictions: `cfunc-guarded` ≡ `py-njit` (bit-identical) on every
target, seed and thread count, and ≡ `cfunc` wherever `cfunc` completes;
`cfunc-guarded` replaces `cfunc` as the compiled reference in P1/P5 and as
the untouched control arm of phase 2.

## Amendment A3 and the phase-2 addendum (frozen after phase 1, before phase 1b and phase 2)

**A3 (harness).** Phase-1 sampling walls include first-call lazy compilation
for the arms whose compiled code is built on first use (the numba dispatcher
behind `py-njit`, `jax.jit`, PyTorch's first call, PyTensor NUMBA): the
harness did not prime the target before the timed `sample` call, contrary to
the protocol's own metric. A diagnostic outside the evidence cells (4 x
300/300, gauss100, threads=1) puts the steady in-sampler cost at 4.0 µs/call
for `py-njit` and 50 µs/call for `jax`, versus the phase-1 16 and 100
µs/call. Phase-1 numbers are reported as measured, labelled "includes
first-call compilation". Phase 1b and phase 2 prime every target with one
evaluation at the zero vector before timing (counted as construction; a pure
function, so draws are unaffected).

**Phase-1 facts that drive the selection** (`artifacts/results-table.md`):
all six baseline `pymc` / `pymc-numba` threads=4 cells hit the 600 s cap (P7
held); a probe confirmed the A1 mechanism directly — at threads=1 the
callbacks run on the calling thread (one `threading.local` initialisation per
run), at threads=4 every one of 2,105 callbacks saw a fresh thread state
(2,105 initialisations). Micro decomposition of `from_jax`: the jitted
function costs 14.5 / 16.3 / 49.7 µs on a numpy argument but 33.3 / 35.9 /
218 µs through the adapter's `jnp.asarray` (gauss100 / eight / hier); the
PyMC `ValueGradFunction` → raw `trust_input` saving is 1.1–4.2 µs (F2:
predicted gain < 1.3x); `wrap_callable` costs 0.0–0.3 µs (F1: negligible).

**Selection (by the frozen rule).** F6 has the largest predicted gain
(baseline `pymc` / `pymc-numba` threads=4 ESS/s is 0: unbounded). F3 is the
largest candidate on an arm/thread F6 does not touch (`jax` threads=1:
predicted 1.4–3x). The fix build bundles **F6 + F3**; they act on disjoint
cells except `jax` threads=4 (reported as the joint effect, judged for
neither). F1, F2, F4, F5 are not implemented.

**Phase-2 arms.** `py-numpy`, `py-njit`, `jax`, `torch`, `pymc`, `pymc-numba`
(touched) and `cfunc-guarded` (untouched control), threads 1 and 4, three
seeds, `baseline` and `fix` builds alternating inside each arm/threads pair;
baseline `pymc` / `pymc-numba` threads=4 under the A1 rule (seed `4747001`
only, 600 s cap); every fix cell runs normally.

**Phase-2 predictions.** Q1: every fix cell is bit-identical to its baseline
cell (all arms, threads, seeds; baseline timeouts excepted). Q2 (F6): every
fix `pymc` / `pymc-numba` threads=4 cell completes, with ESS/s within
[0.3, 1.5]x the same arm at threads=1 (GIL-serialised but no longer
pathological). Q3 (F6, = P8): fix/baseline geomean ESS/s at threads=4 in
[1.0, 1.6] for `py-numpy`, `py-njit`, `torch`. Q4 (F3): `jax` threads=1
fix/baseline geomean ESS/s >= 1.3 on all three targets, largest on `hier`.
Q5: threads=1 cells of the F6-only arms and both thread counts of
`cfunc-guarded` have fix/baseline geomean in [0.9, 1.1]. Decision rule
unchanged.
