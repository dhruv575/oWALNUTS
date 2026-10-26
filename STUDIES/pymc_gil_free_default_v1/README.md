# Should `gil_free=True` be `from_pymc`'s default? (WP83)

Status: preregistered at `a1bb05bd` (base `aa7160bd`) before any cell;
executed 2026-10-26 on lane 4 (cores 12-15) of the shared Linux box, pinned,
co-tenanted. 132/132 breadth cells and 150/150 robustness runs recorded;
none rerun. Tables: `artifacts/results-table.md`, `artifacts/summary.json`.

## Verdict

**Not proposed (frozen rule: R2 fails).** gil_free never failed where the
default ran, passed every gate the default passed (30/30 runnable cells at
both thread counts), was 0.13–0.46x the default's wall per gradient at one
thread and 0.03–0.13x its wall at four, agreed with it in posterior means
(max |z| 4.4), and had 0 faults and 0 non-identical results in 150
four-thread runs. But its draws were not reproducible on three models:
gil_free differed from the same numba function called as a callable on
`ar1` (1/3 seeds), `simplex_bounded` (1/3) and `data_dims_det` (3/3), and
on `data_dims_det` one seed gave different draws at threads 1 and 4. The
known `pm.Data` + `initval` limitation fails closed before sampling with
`NotImplementedError` naming `gil_free=False`.

| model | ≡ numba | t1 ≡ t4 | ≡ C default | gates def/numba/gf1/gf4 | wall/grad gf ÷ def | max \|z\| | error |
|---|---|---|---|---|---:|---:|---|
| eight | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.13 | 1.7 | — |
| hier | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.46 | 4.4 | — |
| logistic | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.43 | 1.8 | — |
| poisson | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.19 | 1.8 | — |
| ar1 | **2/3** | 3/3 | 0/3 | 3/3/3/3 | 0.17 | 1.3 | — |
| simplex_bounded | **2/3** | 3/3 | 0/3 | 3/3/3/3 | 0.18 | 1.8 | — |
| data_dims_det | **0/3** | **2/3** | 0/3 | 3/3/3/3 | 0.14 | 2.3 | — |
| initvals | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.13 | 0.9 | — |
| initvals_data | — | — | — | 3/3/0/0 | — | — | NotImplementedError (fails closed) |
| potential | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.13 | 2.1 | — |
| student_t | 3/3 | 3/3 | 0/3 | 3/3/3/3 | 0.21 | 2.3 | — |

Robustness (gil_free, threads=4, 50 processes each): eight, hier, logistic
0 faults, 0 non-identical.

## Predictions

Held: P3 (gil_free ≢ the C default: 0/10 models identical, as predicted
against the brief's "identical"), P4 (wall 0.13–0.46), P5, P6, P7, P8.
Failed: P1 (≡ numba control: 3 models) and P2 (t1 ≡ t4: `data_dims_det`
seed 8383101).

## Reading

* `data_dims_det` ≢ numba on every seed is expected in hindsight: gil_free
  compiles the **frozen** (`freeze_dims_and_data`) graph, the numba arm the
  graph with shared `pm.Data`; they are different numba programs.
* The single-seed mismatches on `ar1` and `simplex_bounded`, and the
  `data_dims_det` t1 ≢ t4 seed, are unexplained. Every one is in the first
  seed block, the first process to compile that model in a fresh numba and
  PyTensor cache; a first-compile versus cache-loaded code difference is the
  leading hypothesis, not tested here (no reruns).
* A default change would also break the API: gil_free returns a
  `CFuncTarget`, which is not callable (`target(q)`) and does not support
  `refresh=`; the default returns a callable.

## Recommendations

1. Keep `gil_free=False` as the default; keep recommending
   `gil_free=True` with `threads=4` in the docs (WP78) — every gate and
   posterior agreed here.
2. Follow-up study: determinism of gil_free across fresh and warm numba /
   PyTensor caches (same model, seed and thread count, cache cleared vs
   warm), before any default change.
3. Any future default change needs a callable wrapper around `CFuncTarget`
   and a fallback to the callable path on `NotImplementedError`.

## Limits

Three seeds; walls pinned but co-tenanted; PyTensor's C backend found no
BLAS on this venv (affects the default's `hier` cost). The extension was
rebuilt into the WP78 lane venv from `aa7160bd`.
