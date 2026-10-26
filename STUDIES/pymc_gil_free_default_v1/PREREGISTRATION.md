# Preregistration — pymc_gil_free_default_v1 (WP83)

Frozen 2026-10-26 on `wt/gil-free-default` (base `aa7160bd`) before the
first evidence cell. `protocol.json` is authoritative. Ledger id
`WP83-PYMC-GIL-FREE-DEFAULT-V1`.

## Question

Should `gil_free=True` become `from_pymc`'s default? WP47 and WP78 measured
it on three models: 1.2–4.0x a native Rust target per gradient and 8–22x the
default's ESS/s at 4 threads (WP78). A default must hold on the models users
actually write.

## How gil_free works (source at `aa7160bd`)

`_from_pymc_gil_free` snapshots `pm.Data` and mutable dims with PyMC's
`freeze_dims_and_data` when the graph has shared inputs, rejects remaining
shared inputs, checks that the frozen model keeps the unconstrained layout
and initial point, compiles `logp_dlogp_function(mode="NUMBA")`, wraps its
`vm.jit_fn` in a `numba.cfunc` with the raw ABI (nonfinite value or gradient
becomes `-inf`, gradient zeroed), and verifies it once against the compiled
function at `q0`. It returns a `CFuncTarget`, not a callable, so `target(q)`
and `refresh=` do not work on it. Known limitation: on PyMC >= 5.28 a model
with `pm.Data` *and* explicit `initval`s cannot be snapshotted; the adapter
raises `NotImplementedError` (the xfailed
`test_from_pymc_gil_free_snapshots_data_and_dimensions_without_mutation`).
The default `from_pymc(model)` uses the PyTensor **C** backend, so gil_free
changes the compiled code, not only the transport.

## Design

Eleven PyMC models (`models.py`): noncentred Eight Schools and the 157-D
hierarchical regression (WP47), logistic and Poisson GLMs, an AR(1) series
with `rho ~ Uniform(-1, 1)`, a bounded/transformed model (Dirichlet simplex,
Beta, Uniform scale; Multinomial and Binomial likelihoods), a model with
`pm.Data`, coords/dims on the observed and Deterministics, explicit initvals
without `pm.Data`, explicit initvals with `pm.Data` (the known limitation),
a `pm.Potential`, and a StudentT robust regression. Arms: default (t1),
`mode="NUMBA"` callable (t1; the same compiled function as gil_free, the
bit-identity control), gil_free (t1 and t4). 4 x 1,000/1,000, seeds
8383101–8383103; 132 breadth cells. Robustness: 50 separate gil_free runs at
threads=4, seed 8383500, on eight, hier and logistic (150 child processes).
Strictly sequential, one child per cell, every process under
`taskset -c 12-15`, on a shared box with other lanes active (walls pinned,
co-tenanted; hashes, gates and fault counts unaffected). Failures are
results; nothing is rerun.

## Predictions (P1–P8 in `protocol.json`)

P1 gil_free ≡ numba bit for bit everywhere both run. P2 gil_free t1 ≡ t4.
**P3 gil_free ≢ the C default on most models** (at most 3 of 10 identical):
the brief expected identity; WP47 and WP78 say the backends differ, so I
predict the opposite and record both. P4 gil_free t1 / default t1 wall per
gradient in [0.1, 0.9]. P5 means agree within |z| <= 5 wherever both pass.
P6 gil_free passes at least the default's gate cells per model. P7 only
`initvals_data` errors, at gil_free construction, with `NotImplementedError`.
P8 0 faults, 0 non-identical results in 150 robustness runs.

## Decision rule (frozen)

Propose gil_free as the default iff **R1** no model where gil_free errors
where the default succeeds, other than the known initval + `pm.Data`
limitation, which must fail closed before sampling with
`NotImplementedError` and be documented with a fallback; **R2** no model
where gil_free differs where the default succeeds (differs = not identical
to the numba control, fewer gate passes than the default, or max |z| > 5 on
>= 2 of 3 seeds); **R3** robustness 0 faults and 0 non-identical. Identity
with the C default is reported, not a clause (a backend change alters draws
by construction). API compatibility (`CFuncTarget` is not callable) is
reported as a requirement for any default change. No default changes here.

## Seeds

8383101–8383103, 8383500, data seeds 8383001–8383008; checked by exact-word
`git grep` over every local branch before the freeze.
