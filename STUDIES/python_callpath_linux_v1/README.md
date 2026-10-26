# Python call paths on Linux (WP78)

Status: preregistered at `aaaae69a` (A1 `91e68119`, before any cell), base
`55e5a0aa`; executed 2026-10-26 on the shared Linux box, lane 4 (cores
12-15), pinned, co-tenanted. 126/126 sampler cells and 18/18 micro cells
completed; none rerun. Tables: `artifacts/results-table.md`; machine-readable
`artifacts/summary.json`.

## Verdict

**The compiled paths cost what a native Rust target costs; the nutpie gap
persists on Linux.** `from_cfunc` runs at 0.98–1.15x the pure-Rust wall per
gradient (threads 1 and 4), and its draws are bit-identical to the Rust
target and to the njit callable on every cell. `from_pymc(gil_free=True)` is
1.2 / 2.2 / 4.0x Rust (PyTensor's generated code, not transport). Python
callables add 1.4–1.6 µs per call (njit callable), 5–30 µs (`from_pymc`
default) and 21–40 µs (`from_jax`) and get slower at threads=4 (0.39–0.82x).
nutpie's ESS per gradient lead is 1.71 / 1.44 / 1.88x, pooled **1.67x**
(Windows WP58: 1.70x), identical across every oWALNUTS arm (1.61–1.74x).

| path (µs/gradient, gauss100 / eight / hier) | threads=1 | vs Rust | threads=4 | t4/t1 ESS/s |
|---|---|---|---|---|
| Rust target | 1.57 / 0.57 / 3.84 | 1 | 0.44 / 0.17 / 1.02 | 3.4–3.8 |
| `from_cfunc` | 1.70 / 0.66 / 3.76 | 0.98–1.15 | 0.45 / 0.19 / 1.00 | 3.4–3.8 |
| `from_pymc(gil_free=True)` | 1.85 / 1.27 / 15.3 | 1.2–4.0 | 0.52 / 0.40 / 3.94 | 3.2–3.8 |
| njit callable | 3.12 / 1.99 / 5.26 | 1.4–3.5 | 5.96 / 5.08 / 6.52 | 0.39–0.82 |
| `from_pymc` (C backend) | 6.72 / 9.95 / 33.7 | 4.3–17 | 10.6 / 22.0 / 42.2 (thread_safe) | 0.45–0.80 |
| `from_jax` | 22.6 / 22.4 / 43.8 | 11–39 | 49.4 / 49.0 / 65.0 | 0.46–0.68 |
| nutpie 0.16.8 | 1.62 / 1.60 / 15.0 | 1.0–3.9 | 0.71 / 0.77 / 4.01 | 2.1–3.7 |

ESS/s vs nutpie at matched cores: gil_free 0.51–0.78x (1) and 0.53–1.21x
(4); `from_pymc` 0.11–0.24x (1); cfunc 0.53–1.92x (1), 0.80–2.74x (4).
nutpie fails the gates on eight 3/3 (12 divergences); every oWALNUTS arm
passes 9/9 at threads=1 except `from_jax` (8/9, hier R-hat 1.0101).

## Predictions

P3 (threads), P4 (bit identity 44/44, including rust ≡ cfunc ≡ py-njit and
t1 ≡ t4 everywhere, nutpie cores 1 ≡ 4, starts 90/90), P5, P6 (gap persists),
P8 (completion, F6 on CPython 3.12 Linux: every thread_safe threads=4 cell
finished) **held**. P1 17/18 (gil_free eight 1.27 µs, below range). P2 9/12:
gil_free was cheaper relative to Rust than predicted (1.2 / 2.2x on gauss /
eight). P7 18/24: nutpie on gauss100 is faster than predicted (cfunc 0.53x,
rust 0.90x at 4, jax 0.04x), and on eight gil_free t4 (1.21x) and
`from_pymc` t4 (0.024x) left their ranges.

## Decision rule outcome (frozen; documentation only)

* R1: gil_free t4 is 8.3–22x `from_pymc` t1 with all gates → **recommend
  `from_pymc(model, gil_free=True)`, `threads=4`, first for PyMC on Linux.**
* R2: nutpie faster on gauss100 (1.42x) and hier (1.88x); on eight nutpie
  fails the gates 3/3 (state the failure).
* R3: cfunc t4 is 5.3–10x the njit callable at t1 and within 1.5x
  (0.98–1.12x) of native Rust → recommend `from_cfunc`.
* R4: njit callable, `from_jax`, `from_pymc`: keep "use threads=1".
* R5: gap **persists on Linux** (1.71 / 1.44 / 1.88, pooled 1.67).
* R6: `from_jax` at 0.09–0.14x the njit callable → JAX dispatch dominates
  (22–44 µs per gradient).

## Proposed README guidance (integrations/python)

PyMC: use `from_pymc(model, gil_free=True)` with `threads=4` (8–22x the
default callable on Linux; ESS/s 0.5–1.2x nutpie). nutpie remains 1.4–1.9x
faster per second on smooth and large hierarchical models because it needs
1.4–1.9x fewer gradients per ESS (adaptation, not transport), and fails the
gates on noncentred Eight Schools where oWALNUTS passes. Hand-written
densities: `from_cfunc` (numba `error_model="numpy"` + guard) costs the same
as a native Rust target and scales 3.4–3.8x on 4 threads. Python callables,
the default `from_pymc` and `from_jax`: `threads=1`; JAX adds ~20 µs per
gradient.

## Anomalies and limits

* Walls are pinned but co-tenanted; three seeds. CPython 3.12.3 here, 3.11
  in WP47.
* The first artifact sync was truncated; metrics were resynced and the raw
  draws hashed on the box (`artifacts/draws.sha256`); draws are not
  committed. The run itself had completed (`artifacts/run.log`).
* Smoke-time Rust plumbing gap and one unpinned 2 s grep: disclosed in the
  preregistration.
