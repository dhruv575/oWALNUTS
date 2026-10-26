# WP86: is `from_pymc(gil_free=True)` deterministic across numba and PyTensor caches?

## Verdict

**Cause.** The cause is PyTensor's numba function, not the gil_free wrapper. It gives different
draws depending on whether it is compiled fresh (cold cache) or loaded from numba's file cache
(warm). This happens only under PyTensor's default numba fastmath.

- **The wrapper is faithful.** In all 310 processes, the cfunc's draws are bit-identical to the
  draws of the PyTensor function it wraps, called as a Python callable in the same process. Its
  log density and gradient are bit-identical at all 50 probe points (0 ulp).
- **Threads are not involved.** Threads 1 and 4 agree in all 60 thread-arm processes.
- **Cold and warm differ on the same three models.** On `ar1`, `simplex_bounded` and
  `data_dims_det`:
  - every cold process gives one draw hash;
  - every warm process gives another;
  - both gil_free and the plain callable show the same split.
- **The unaffected models.** `eight` and `logistic` give one hash in all 10 processes.

WP83's mismatches were cold processes compared against warm ones.

**Fix (frozen rule).** Two single-flag arms qualify: fastmath off (B) and the file cache off (E).
Both give one hash per model over 10 processes, and both keep the wrapper bit-identical everywhere.

**Proposed package change: arm B**, first in the registered order. Compile gil_free's function with
PyTensor's numba fastmath off:

```python
# integrations/python/python/owalnuts/__init__.py, _from_pymc_gil_free
import pytensor
with pytensor.config.change_flags(numba__fastmath=False):
    fn = frozen_model.logp_dlogp_function(
        grad_vars=[frozen_values[name] for name in names],
        initial_point=frozen_initial, ravel_inputs=True, mode="NUMBA",
    )
```

- **Cost.** Wall per gradient is the same as arm A: median 1.29 vs 1.28 us on `eight` and 4.83 vs
  4.84 on `simplex_bounded`. These are co-tenanted walls, so descriptive only.
- **Caching stays.** PyTensor keys its cache on the flag, so the fastmath-off code is still cached.
- **Side effect.** gil_free draws will no longer equal `from_pymc(model, mode="NUMBA")` callable
  draws, which keep the fastmath default. Within gil_free they become reproducible regardless of
  cache state.

The design and rule are in `PREREGISTRATION.md` and `protocol.json` (committed `82704a28`). Every
cell is in `artifacts/results-table.md`.

## Results (seed 8686001, 4 x 1,000/1,000, 310 processes, all ok)

| arm | affected models: gil_free hashes over 10 processes | unaffected | D2 (wrapper ≡ same fn, gradients bit-identical) |
|---|---|---|---|
| A, as is | **2** (one cold, one warm) | 1 | 50/50 |
| B, fastmath off | **1** | 1 | 50/50 |
| C, cfunc `error_model="numpy"` | 2 | 1 | 50/50 |
| D, cfunc with PyTensor's fastmath | 2 | 1 | 50/50 |
| E, numba cache off | **1** | 1 | 50/50 |
| T, as is, threads 1 and 4 | 2 (cold / warm) | — | 60/60; t1 = t4 60/60 |

- **Cache use.** The inner dispatcher showed a cache miss in every cold process and a hit in every
  warm one. Arm E missed in every process.
- **The affected models and the frozen graph.** WP83's control (`from_pymc(mode="NUMBA")` on a
  fresh model) matched gil_free in all 10 processes on `ar1`, `simplex_bounded`, `eight` and
  `logistic`. It matched in 0 of 10 on `data_dims_det`. That is the structural frozen-vs-shared
  graph difference WP83 identified, a different program and not a cache effect.

## Predictions

| prediction | outcome | note |
|---|---|---|
| H1: mismatches only cold; ≤ 4 ulp | held | trivially: no wrapper mismatch anywhere |
| H2: the plain callable is stable across processes | **failed** | it splits cold/warm exactly like gil_free; this locates the cause |
| H3: B fixes it | held | |
| H4: C and D do not remove the mismatches | False as computed | the code tests D2, and there were no D2 mismatches to remove; on the cross-process hashes C and D did not help (2 hashes, as in A) |
| H5: E gives one hash but fails D2 | **failed** | E passes D2 too |
| H6: t1 = t4 | held | |

The predicted mechanism, cfunc inlining, is refuted. The cfunc never differs from its own function.
What differs is the numba code of PyTensor's fastmath function when compiled fresh versus loaded
from the cache. The IR evidence could not show why: the cfunc's IR is the same size cold and warm,
and asm is not available.

## Caveat until the change ships

With default PyTensor flags, gil_free runs (and `mode="NUMBA"` callables) can differ in the last
bits between the first process that compiles a model and later processes that load it from the
cache. The draws then diverge. This was seen on 3 of 5 models. Each cache state is itself
reproducible. Workarounds:

- `PYTENSOR_FLAGS=numba__fastmath=False`, or `numba__cache=False`;
- or warm the cache once before runs that must reproduce.

## Run record

- Lane 2 (cores 4-7), co-tenanted, 2026-10-26. 310 processes, no reruns or amendments.
- `CHECKSUMS.sha256` covers 320 files.
- The smoke run on the non-study `poisson` is disclosed in the preregistration.
