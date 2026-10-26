# WP86 preregistration: determinism of `from_pymc(gil_free=True)` across numba / PyTensor caches

This was frozen before any evidence process. `protocol.json` is the machine-readable form and
wins on any discrepancy. The ledger id is `WP86-PYMC-GIL-FREE-DETERMINISM-V1`, as assigned by the
coordinator. The base is main `3efdc7ba`.

## Question

WP83 found that gil_free draws did not reproduce those of the numba callable on three models:

| model | reproduced (seeds) |
|---|---|
| `data_dims_det` | 0/3 |
| `ar1` | 2/3 |
| `simplex_bounded` | 2/3 |

It also found that `data_dims_det` once differed between 1 and 4 threads. Every mismatch was in
the first process to compile the model. Here I test that cold-versus-warm-cache hypothesis
directly, isolate the responsible flag, and ask whether one flag or cache step makes gil_free
bit-identical.

## What the code does (read before the freeze)

- **The wrapper.** `_from_pymc_gil_free` compiles `logp_dlogp_function(mode="NUMBA")` on the
  model, which is the frozen model when there is `pm.Data` or a mutable dim. It takes the
  PyTensor function's numba dispatcher `vm.jit_fn` (`inner`) and wraps it in
  `@numba.cfunc(sig, nopython=True)`. That cfunc uses numba's defaults (`error_model="python"`,
  no fastmath) and calls `inner`, so numba links `inner`'s library into the cfunc. The result is
  checked once against `fn` to 1e-8.
- **PyTensor 2.38.** Its numba functions are `numba.njit(cache=True)` with fastmath
  `{arcp, contract, afn, reassoc, nsz}` (`numba__fastmath=True`). They are cached in
  `<base_compiledir>/numba` under a PyTensor key that includes the fastmath flag
  (`numba__cache=True`).
- **The smoke run.** It showed the inner dispatcher as a cache **miss** in a cold process and a
  **hit** in a warm one.
- **WP83's control** was `from_pymc(model, mode="NUMBA")`, compiled in a *different* process from
  the gil_free cell. For `data_dims_det` it compiled the *unfrozen* graph, a different program.

## Design

- **Models.** Five models from WP83's `models.py` (copied verbatim): the three affected
  (`data_dims_det`, `ar1`, `simplex_bounded`) and two unaffected (`eight`, `logistic`).
- **Run.** Seed 8686001, 4 chains x 1,000/1,000 at sampler defaults.
- **Processes.** Each process is a fresh `python -I` child, strictly sequential. Processes
  alternate:
  - **cold** (even index): before it starts, the parent deletes `NUMBA_CACHE_DIR` and PyTensor's
    `base_compiledir`;
  - **warm** (odd index): it runs on the cache left by the preceding cold process of the same arm
    and model.
- **Recorded in every process:**
  - the gil_free t1 draw hash;
  - the draw hash of **the same `fn` object gil_free wraps**, called as a Python callable with
    `from_pymc`'s wrapper code at t1. This is the primary control, now same process and same
    graph;
  - a 50-point gradient probe, cfunc (through ctypes) against `fn`: bit identity, ulps, and
    |diff| <= 1e-15 x max(1, |g|). The points are q0 + 0.5 N(0, I), rng 86;
  - the inner dispatcher's cache hits and misses;
  - the cfunc's LLVM IR (size, hash, calls, fast-flag and fma counts).
- **Arm A** also records WP83's control.

| arm | change (nothing else) | models x processes |
|---|---|---|
| A | none: the package as is | 5 x 10 |
| B | PyTensor `numba__fastmath=False` | 5 x 10 |
| C | cfunc `error_model="numpy"` | 5 x 10 |
| D | cfunc with PyTensor's fastmath set | 5 x 10 |
| E | PyTensor `numba__cache=False` | 5 x 10 |
| T | none; gil_free at threads 1 **and** 4 in every process | 3 affected x 20 |

Arms C and D patch `numba.cfunc` with `functools.partial` in the child, before `from_pymc`
runs. The package is not edited. That is 310 processes in total.

## Criteria

| id | criterion |
|---|---|
| D2 | wrapper fidelity: in a process, the gil_free t1 draws equal the same-`fn` callable's draws, and the gradient probe is bit-identical at all 50 points |
| D1 | cross-process: one gil_free t1 draw hash for an (arm, model) over all its processes |
| D3 | threads: gil_free t4 equals t1 in the same process |

## Predictions

- **H1.** In arm A, on the affected models, D2 fails only in cold processes. The unaffected models
  pass D2 everywhere. Gradient differences are <= 4 ulp.
- **H2.** In arm A, the same-`fn` callable's draws are identical across all 10 processes. Only the
  cfunc varies.
- **H3.** Arm B (fastmath off) passes D1 and D2 on all 5 x 10.
- **H4.** Arms C and D do not remove the cold mismatches.
- **H5.** Arm E (no cache) passes D1 but fails D2 on the affected models in every process.
- **H6.** In arm T, D3 holds in all 60 processes, and D2 fails only cold.
- **Mechanism.** On a cold compile the cfunc links `inner`'s fresh LLVM IR, inlines it and
  re-optimises it under PyTensor's per-instruction fastmath (contraction and reassociation). On a
  warm process it links the cached object code. The recorded IR tests this descriptively.

## Fix rule (frozen)

- **Qualifying.** A single-flag arm (B, C, D or E) qualifies iff D2 holds in all 50 of its
  processes and D1 holds for every model.
- **One or more qualify.** Propose the qualifying flag as a package change in
  `from_pymc(gil_free=True)`, behind nothing, as a correctness fix. If several qualify, the order
  of preference is:
  1. C or D (local to the wrapper);
  2. B, as `pytensor.config.change_flags(numba__fastmath=False)` around gil_free's compile;
  3. E.

  Report its wall per gradient against arm A.
- **None qualifies.** Document the caveat precisely in the docstring and docs.
- **Cache warming** (arm A restricted to warm processes) is reported descriptively. The package
  cannot guarantee a warm cache, so it is not a shippable fix.

## Environment (disclosed)

- **Lane:** lane 2 of the shared c7a.4xlarge box, cores 4-7, `taskset -c 4-7` on every process,
  with other lanes active. Walls are pinned, co-tenanted and descriptive.
- **Venv:** a lane venv with WP78's pins: numpy 2.4.6, numba 0.67.0 (llvmlite 0.49.0), pymc
  5.28.5, pytensor 2.38.2, jax 0.10.2, nutpie 0.16.8, arviz 0.23.4, maturin 1.15.0.
- **Extension:** built with `maturin develop --release` from the frozen commit.

## Smoke run (disclosed, infrastructure)

- **What ran.** One cold and one warm process for every arm, on the **non-study** model `poisson`,
  into the lane's `smoke/`.
- **Result.** Every process was ok and D2 held in all 12, with gradient bits identical and t1 = t4.
- **Dispatcher.** The inner dispatcher missed the cache when cold and hit it when warm. Arm E
  missed both times.
- **IR.** The cfunc IR carries PyTensor's fast flags, except under B.
- **Code change after the smoke.** `numba.CFunc` has no `inspect_asm` in this numba, so only the
  LLVM evidence is recorded. No code changed.

## Rules

PREREGISTRATION.md and protocol.json are committed before the first evidence process.

- **Reporting:** every process is reported; failures and timeouts are results; no reruns and no
  tuning after seeing results.
- **Missing records:** a process with no record may be rerun once, recorded as a deviation.
- **Amendments:** only for processes not yet run, committed before them.
