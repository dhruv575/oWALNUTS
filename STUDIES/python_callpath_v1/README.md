# Python call paths v1 — what each Python entry point costs, and two bit-identical fixes (WP47)

Status: preregistered on `wt/python-callpath` (`91305996`, before any
evidence cell), amended five times before the cells each amendment governs
(`PREREGISTRATION.md` A1–A5, every one committed before the cells it
governs), executed 2026-10-24 on the shared 16-core Windows machine. Every
cell is recorded; failed cells are results and were not rerun.
Tables: `artifacts/results-table.md`; machine-readable: `artifacts/summary.json`.
**Every wall in this study is contended** (about ten agents shared the
machine). Use relative numbers within a phase, where arms were interleaved;
gradient counts, ESS, ESS per call and draw hashes do not depend on the
machine.

## Verdict

**Supported: the fix passes the frozen merge rule.** The fix build
(`06a551a7`) draws bit-identically to the 0.2.0 baseline in **102/102**
paired cells. `from_jax` gives **2.05x / 2.06x / 2.59x** ESS/s at threads=1
(gauss100 / eight / hier). Python callables at threads=4 give **1.14–1.90x**
(PyTorch 1.03–1.09x). `from_pymc(model, thread_safe=True)` at threads=4 goes
from **not finishing within 600 s** (one PyTensor compilation per callback)
to finishing in 1.5–9 s. No touched cell is below 0.9x.

The headline for users is the path you take, not the fix:

| path (in-sampler µs per call, gauss / eight / hier) | ESS/s vs nutpie 0.16.8 on the same PyMC model |
|---|---|
| hand-written numba `cfunc` (1.3 / 0.6 / 2.9) | 2.3–9.0x at 1 core, 4.0–16x at 4 (phase 1c vs phase 1, different times) |
| `from_pymc(model, gil_free=True)` (4.2 / 5.7 / 24) | 0.51–1.0x at 1 core, 0.47–0.93x at 4 |
| plain numpy callable (3.8 / 9.2 / 36) | 0.20–0.48x at 1 core |
| `from_pymc(model)` default (7.2 / 12 / 31) | **0.17–0.24x** at 1 core |
| `from_jax` (0.2.0: 45 / 42 / 82; fixed: 22 / 19 / 32) | 0.03–0.04x (0.2.0, phase 1) |
| `from_torch` (66 / 292 / 496) | 0.005–0.025x |

nutpie still gets **1.6–2.4x more ESS per gradient** than oWALNUTS on all
three models (0.0934 vs 0.0553, 0.0417 vs 0.0256 and 0.0087 vs 0.0037 min
bulk ESS per gradient). oWALNUTS beats nutpie on ESS/s only through a
cheaper evaluation: the hand-written cfunc against PyTensor's generated code.

## What the call paths are (source reading)

* `sample` releases the GIL for the whole run (`Python::detach`). At
  threads=1 the chains run **on the calling thread**. At threads > 1 they run
  on a run-local scoped Rayon pool.
* A **Python callable** (`PyTarget`) re-attaches the interpreter on every
  call. It allocates a fresh numpy array for the position, calls the
  function and parses the `(float, ndarray)` tuple. At threads > 1 this
  serialises the chains on the GIL. In 0.2.0 each call on a worker thread
  also created and destroyed a `PyThreadState`, because those threads had
  none (a probe counted 2,105 `threading.local` initialisations in 2,105
  callbacks). `wrap_callable` adds 0.0–0.3 µs.
* `from_cfunc` and `from_pymc(gil_free=True)` are a C ABI (`RawTarget`) and
  never touch the interpreter. The raw ABI is stricter than the callable
  path: a finite value with a nonfinite gradient is **fatal**.
* `from_jax` is a Python callable around `jax.jit(jax.value_and_grad)`. In
  0.2.0 it added a separate `jnp.asarray` dispatch (micro: 14.5 → 33 µs on
  gauss100, 50 → 218 µs on hier).
* `from_torch` is a Python callable around `torch.autograd.grad`, CPU,
  default intra-op threads (16 here).
* `from_pymc(model)` is a **Python callable** around PyMC's compiled
  `logp_dlogp_function`, with the PyTensor C backend by default. Its
  `ValueGradFunction` layer costs 0.4–4 µs over the raw function with
  `trust_input`. `gil_free=True` wraps PyTensor's NUMBA `jit_fn` in a
  `numba.cfunc`.

## Evidence

**Bit identity (machine-independent).**

* Pairs of paths that call the same compiled function give identical draws:
  `py-njit` ≡ `cfunc` (12/12 on gauss/eight), `py-njit` ≡ `cfunc-safe`
  (18/18, including hier), `pymc-numba` ≡ `pymc-gilfree` (9/9). Every path
  completing at both thread counts is identical at threads 1 and 4.
* Priming the target before timing changes no draw (phase 1 ≡ phase 1b).
* PyMC's C and numba backends agree on gauss100 (3/3) but not on eight or
  hier (0/3 each). numpy, JAX and torch never match the njit kernel
  bit-for-bit (rounding only: ESS per call agrees within 0.8–1.25x).
* Fix ≡ baseline in 102/102 cells.

**Phase 1** (baseline, 24 micro cells and 162 sampler cells: 138 completed,
6 A1 timeouts, 12 A1 not run, 6 cfunc errors). The default `from_pymc` reaches 0.21 / 0.24 / 0.17x
nutpie's ESS/s at one core. At four threads, every Python callable is
slower than at one: t4/t1 ESS/s is 0.29–0.54 for numpy and njit callables,
0.55–1.23 for JAX, 0.56–1.30 for torch, and timeouts for the PyMC callables.
Compiled paths scale 2.2–3.3x (eight `pymc-gilfree` t4 is an outlier: one
seed took 9.0 s against 0.11–0.16 s for the other two). Phase-1 walls of the
lazily compiled arms include first-call JIT compilation (amendment A3). The
primed rerun of `py-njit` (phase 1b) puts it at 3.6 / 2.4 / 5.9 µs per call,
not the 16 / 12 / 18 of phase 1.

**Usability failures found (results, not rerun).**

1. `from_pymc(thread_safe=True)` at threads > 1 never finishes in 0.2.0
   (A1): 6/6 timeouts in phase 1 and 6/6 in phase 2.
2. A straightforward numba cfunc port of a callable that samples fine fails
   at transition 0 on hier (A2, A5), in 12 cells for `cfunc` and
   `cfunc-guarded`. Numba's default `error_model="python"` raises
   `ZeroDivisionError` when `sigma` underflows. The exception cannot cross
   the C ABI, and the run dies with "raw target wrote a nonfinite gradient
   element". `error_model="numpy"` plus a nonfinite guard (`cfunc-safe`)
   fixes it, and the result is bit-identical to the callable path.

**Phase 2** (fix vs baseline, builds interleaved per cell, primed):

* F3 (`from_jax`): jax at threads=1 gains 2.05 / 2.06 / 2.59x (micro 40 →
  18 µs on gauss100); jax at threads=4 gains 2.11–2.18x (joint with F6).
* F6 (thread-state pinning) at threads=4: `py-numpy` 1.64 / 1.43 / 1.14x,
  `py-njit` 1.90 / 1.70 / 1.63x, `torch` 1.09 / 1.03 / 1.06x.
  `pymc` / `pymc-numba` go from timing out to 3,002 / 970 / 83 and
  2,790 / 874 / 108 ESS/s.
* Untouched cells: threads=1 cells of the F6-only arms are 0.95–1.13x and
  the control (`cfunc-guarded`) is 0.95–1.03x. Decision rule: (i) 102/102
  identical, (ii) ≥ 1.3x on several targets, (iii) nothing below 0.9:
  **merge**.

## Predictions

| id | prediction | outcome |
|---|---|---|
| P1 | per-call ranges (21 cells) | **13/21 held.** Misses: numpy gauss was faster than predicted (1.5 µs); compiled paths were slower in the sampler (cfunc 3.8 / 1.5 µs in phase 1, though 1.3 / 0.6 µs once primed in 1c; `gil_free` 4.2 / 5.7 / 24 µs, because PyTensor's generated numba code is itself 4–20 µs); JAX hier was 240 µs; torch hier 607 µs. |
| P1b | callable transport overhead 1–5 µs | Phase 1 unevaluable (compile-contaminated, A3). Primed phase-2 baseline: 0.5–2.5 µs. |
| P2 | threads=4 does not help plain Python | **Held** (0.29–0.54; primed 0.14–0.26). JAX ≤ 1.2 missed on hier (1.23). Torch [0.8, 2] held on 2/3. Compiled ≥ 2 held, except the eight `gil_free` outlier (0.76). |
| P3 | `from_pymc` vs nutpie: [0.1, 0.5] at 1/1; [0.03, 0.3] at 4/4; `gil_free` [0.6, 1.6] at 4/4 | 1/1 **held** (0.17–0.24). 4/4 **failed**: the baseline never finished. `gil_free` held on 1/3 (0.93; 0.47, 0.55). |
| P4 | bit identity | **Held** on every evaluable comparison. |
| P5 | ESS/call within 0.8–1.25x of cfunc; nutpie ESS per gradient in [0.6, 1.6]x | First held. Second **failed**: nutpie is 1.63–2.35x. |
| P6 | health | **Failed** on 4 cells: hier `py-numpy` seed 4747003 R-hat 1.014 and hier `torch` seed 4747002 R-hat 1.011, at both thread counts. No divergences anywhere. |
| P7 | the 0.2.0 thread_safe cells time out | **Held**, 6/6 (and 6/6 in phase 2). |
| Q1 | fix bit-identical | **Held**, 102/102. |
| Q2 | fixed PyMC t4 within [0.3, 1.5]x of t1 | 5/6 (eight `pymc-numba` 0.28). |
| Q3 | F6 t4 gain in [1.0, 1.6] | 5/9: the gain was larger than predicted for `py-njit` (1.63–1.90) and gauss `py-numpy` (1.64). |
| Q4 | F3 ≥ 1.3x on all targets, largest on hier | **Held** (2.05, 2.06, 2.59). |
| Q5 | untouched cells within [0.9, 1.1] | 18/19 (gauss torch t1 1.13; one seed 1.52, torch noise). |

## Recommendations

1. **Merge `06a551a7`** (Python extension only; no kernel or `walnutpie`
   change, fingerprints untouched; README, CHANGELOG and docstrings updated
   in this branch).
2. **README performance guidance** is now the measured table above: Python
   callables at threads=1; `gil_free=True` or a numba `cfunc` for speed;
   numba `error_model="numpy"` plus a nonfinite guard for `from_cfunc`.
3. Follow-ups (not done):
   * a guarded option for `from_cfunc` (nonfinite → zero density, as the
     callable path does);
   * making `gil_free=True` the documented first choice for PyMC (it changes
     the backend, so draws change; that is excluded here);
   * a kernel study of why nutpie gets 1.6–2.4x more ESS per gradient on
     these models (warmup and metric adaptation are the obvious suspects).
4. The three `gil_free` freeze tests fail on PyMC 5.28.5, which has no
   `pymc.model.transform.freeze_dims_and_data`. They fail identically on the
   baseline wheel, and the compatibility fix is pending.

## Anomalies and limits

* Wall contention: the torch threads=1 per-seed ratio reached 1.52 in an
  untouched cell. The eight `gil_free` threads=4 seed 4747001 took 9.0 s.
* Phase-1 walls of `py-njit`, `jax`, `torch` and `pymc-numba` include
  first-call compilation (A3); the comparisons that drive conclusions use
  the primed phases.
* Amendments A2, A3 and A5 are post hoc. They add arms and priming, and
  every one was committed before the cells it governs.
* `F6` went through two implementations, rejected in pre-phase-2 probes,
  before the committed one (A4): main-thread deletion is unsafe on Python
  3.12+, and an unsynchronised TLS release exited with code 127. The
  committed version was tested only on Windows / CPython 3.11 here, so
  Linux/macOS and 3.12+ wait on CI.
* nutpie ran once per seed and cores setting in phase 1 only. Cross-phase
  ESS/s ratios against it compare different times of day.
