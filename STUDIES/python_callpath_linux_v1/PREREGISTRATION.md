# Preregistration — python_callpath_linux_v1 (WP78)

Frozen 2026-10-25 on `wt/python-linux` (base `55e5a0aa`, main at the freeze)
before the first evidence cell. `protocol.json` is the machine-readable copy
and wins on any discrepancy (arm definitions, order, statistics, prediction
ranges, decision rule). Ledger id `WP78-PYTHON-CALLPATH-LINUX-V1`.

## WP number

WP64–WP77 are taken (lanes and sibling studies); this study is **WP78**.

## Question

WP47 (`STUDIES/python_callpath_v1`) measured on a contended Windows machine
what each Python call path of the package costs per target evaluation, and
how its ESS per second compares with nutpie 0.16.8 on three PyMC models.
WP58 (`STUDIES/nutpie_per_gradient_gap_v1`) reproduced the nutpie
per-gradient lead on the same models (1.66 / 1.42 / 2.10x, pooled 1.70x on
the Python path) and decomposed it; wiki open question 13 records that the
gap remains unexplained after WP71 and WP73.

On Linux, with no Windows machine in the loop: **(a)** what does each Python
call path cost per gradient relative to a pure-Rust target, and **(b)** does
the nutpie gap on those PyMC models persist?

"No Windows serialisation" here means: none of these paths touches the
Windows-only BridgeStan owned worker, but WP47's walls were taken on a
Windows machine shared by about ten agents. This study runs pinned on
dedicated (co-tenanted) cores, so the per-gradient costs can be stated
against a native target measured in the same lane.

## Paths and what they are (source reading at `55e5a0aa`)

* `sample` releases the GIL for the whole run (`Python::detach`); at
  `threads=1` the chains run on the calling thread, at `threads > 1` on a
  run-local scoped Rayon pool.
* A **Python callable** (`PyTarget`: `py-njit`, `jax`, `pymc`) re-attaches on
  every call (`Python::attach`), allocates a fresh `PyArray1`, calls, parses
  the tuple and copies the gradient. Since WP47's F6 each worker thread keeps
  one pinned `PyThreadState` for the run; F6 was tested only on Windows /
  CPython 3.11 (WP47 anomalies). This study runs CPython 3.12 on Linux.
* `from_cfunc` and `from_pymc(gil_free=True)` are the C ABI (`RawTarget`) and
  never touch the interpreter.
* `from_pymc(model)` is a Python callable around PyMC's compiled
  `logp_dlogp_function` (PyTensor C backend); `thread_safe=True` compiles one
  function per worker thread (required for `threads > 1`).
* `from_jax` is a Python callable around `jax.jit(jax.value_and_grad)`
  called on the numpy position (WP47's F3).
* `init=None` is the Rust `Init::best_of(16)` for every target kind (WP58
  follow-up), so every oWALNUTS arm, including the Rust one, starts from the
  same candidates for a given seed.

## Arms (`protocol.json` `arm_definitions`)

`rust` (pure-Rust reference: `rust/` harness, WP58's native densities, the
sampler at its defaults configured as the package configures it, the
extension's release profile), `cfunc` (the documented `from_cfunc` recipe:
numba `error_model="numpy"` plus the nonfinite guard, WP47's `cfunc-safe`),
`py-njit` (plain callable around the same njit kernel: the transport
control), `pymc-gilfree`, `pymc` (default; `thread_safe=True` at
`threads=4`), `jax`, and `nutpie` (`compile_pymc_model`, numba backend).
Threads 1 and 4 (nutpie `cores` 1 and 4); 4 chains in every cell. No
`from_torch` or plain-numpy arm (not asked; WP47 measured both).

Models: WP47's `gauss100` (100-D standard normal), `eight` (noncentered Eight
Schools, 10-D) and `hier` (157-D noncentered hierarchical regression, data
seed 4747900); `callpath_targets.py` is copied verbatim from WP47 (identical
in WP58) and `models/hier_data.json` verbatim from WP58. These are also
WP58's three PyMC models.

## Environment (disclosed before running)

* AWS EC2 c7a.4xlarge, 16 dedicated AMD EPYC cores (no SMT), 32 GB, Ubuntu
  24.04, Rust 1.88.0, GCC 13.3.
* **The study runs core-pinned on a shared box with three other lanes
  active** (shared L3 and memory bandwidth). Lane 4 = cores 12-15; every
  build, driver, child, nutpie and JAX process runs under `taskset -c 12-15`
  (children inherit the affinity) with `RAYON_NUM_THREADS=4`,
  `OMP_NUM_THREADS=1`. All walls and latencies are therefore **pinned,
  co-tenanted**. ESS per gradient, gate counts and bit identity are
  unaffected by co-tenancy.
* Files live only under `~/lanes/python_callpath_linux_v1/` (own clone of this
  branch, own venv, PyTensor compiledir, numba cache, `TMPDIR`). The shared
  `~/infra`, `~/venv` and `~/owalnuts` are read only.
* Lane venv on CPython 3.12.3 (Ubuntu's interpreter; WP47 used 3.11.16) with
  WP47's package versions: numpy 2.4.6, numba 0.67.0 (llvmlite 0.49.0),
  jax/jaxlib 0.10.2 (CPU), PyMC 5.28.5, PyTensor 2.38.2, nutpie 0.16.8,
  arviz 0.23.4, maturin 1.15.0. Exact freeze in
  `artifacts/build-manifest.json`.
* Extension: `maturin develop --release` in `integrations/python` of the box
  clone at the freeze commit, `taskset -c 12-15`, 4 build jobs. The Rust arm
  is `cargo build --release` of `rust/` with the same toolchain and the
  extension's release profile (opt-level 3, LTO, one codegen unit).

## Protocol

* **(a) per-gradient cost.** For every model x path x threads: in-sampler
  wall per gradient = Rust-side sampling wall (`SampleResult.wall_seconds`;
  the harness's `Sampler::run` wall) / kernel target calls, median over the
  three seeds. Reported relative to `rust` at the same thread count, and at
  `threads=1` as the difference in µs. Micro cells (one child each): 10^4
  individually timed calls through the Python surface (cfunc and gil_free
  via ctypes, labelled) with WP47's decomposition; `rust` gets 10^4
  `Instant`-timed native evaluations, a loop mean, and the timer overhead.
  Every target is primed once at the zero vector before the timed run
  (WP47 A3).
* **(b) sampler.** 4 chains x 1,000 / 1,000 at the defaults, fresh seeds
  7878101, 7878102, 7878103; every arm at threads 1 and 4; one child process
  per cell; strictly sequential in the frozen order (micro first; then seeds
  outer, models, the arm x threads list rotated per block). 126 sampler cells
  and 18 micro cells.
* **Statistics.** ESS/s = min bulk ESS over every unconstrained coordinate
  (+ the eight thetas) / wall of the `sample` call (compilation reported
  separately). ESS per gradient = min bulk ESS / (kernel target calls +
  best-of-16 start evaluations; Python arms count the latter after the run,
  untimed; nutpie: `n_steps` warmup + draws). Gates (WP58's): rank R-hat
  ≤ 1.01, bulk and tail ESS ≥ 400, zero retained divergences. Ratios are
  geometric means over seeds of per-seed ratios at matched threads/cores.
  nutpie gap = nutpie ESS/grad / arm ESS/grad (threads/cores 1 cells,
  geomeans over seeds), primary arm `pymc` (WP58's Python path), pooled =
  geomean over the three models.
* Bit identity: sha256 of the retained `(chains, draws, dim)` float64 draws.
* Every cell is reported; failures are results; nothing is rerun.
* **Smoke (not evidence).** After this freeze and before the first evidence
  cell, the full harness runs once on `eight` only, seed 1, 4 x 50/50, 200
  micro calls, with `WP78_ART` outside `artifacts/`; its outputs are deleted.
  It checks plumbing only. Setup checks before the smoke: value/gradient
  agreement of every path against the numpy density at 5 points per model.

## Predictions (frozen; ranges in `protocol.json`)

Windows reference values: WP47 in-sampler µs per call at threads=1 (primed)
cfunc-safe 1.32 / 0.59 / 2.86, gil_free 4.2 / 5.7 / 24, njit callable
3.0 / 1.8 / 4.2, `from_pymc` 7.2 / 12 / 31, `from_jax` (fixed) 22 / 19 / 32;
`from_jax` 2.05–2.59x ESS/s over 0.2.0; ESS/s vs nutpie: `from_pymc`
0.17–0.24x at 1 core, gil_free 0.51–1.0x (1) and 0.47–0.93x (4), cfunc
2.3–9.0x (1) and 4.0–16x (4); nutpie's per-gradient lead 1.69 / 1.63 / 2.35
(WP47) and 1.66 / 1.42 / 2.10, pooled 1.70 (WP58).

**What I expect to change on Linux.** (i) Absolute walls drop and their
noise falls (pinned cores instead of ~10 agents on 16), so WP47's
cross-phase spread (e.g. the 9 s eight gil_free outlier) should not recur;
the machine-portable quantities are the path/rust ratios. (ii) Nothing about
the GIL is Windows-specific: callables at `threads=4` stay slower than at
`threads=1`. (iii) The nutpie per-gradient gap is algorithmic (adaptation;
WP58), so it persists; libm differences only reshuffle draws. (iv) The
compiled paths scale near 3x at 4 threads, capped by the slowest chain
(WP45). (v) The compiled cfunc path costs about what the native Rust target
costs: same kernel, same arithmetic, one indirect call.

* **P1** In-sampler wall per gradient at threads=1, every seed (µs,
  gauss100 / eight / hier): rust and cfunc 0.3–2.0 / 0.15–1.5 / 1.5–5.0;
  py-njit 1–5 / 0.8–4 / 2.5–8; gil_free 1.5–8 / 2–10 / 10–40; `from_pymc`
  3–15 / 5–20 / 15–50; `from_jax` 8–40 / 8–40 / 12–60.
* **P2** Relative to rust (ratio of medians, same threads): cfunc 0.8–1.5x
  at threads 1 and 4 on every model; gil_free at threads=1 2–8x (gauss100),
  4–20x (eight), 4–15x (hier); the callable transport (py-njit − cfunc at
  threads=1) costs 0.5–3 µs per call.
* **P3** threads=4 / threads=1 ESS/s on every model: rust, cfunc, gil_free
  2.0–3.9; py-njit and jax ≤ 1.0; `from_pymc` (thread_safe) 0.15–1.0.
* **P4** Bit identity: rust ≡ cfunc ≡ py-njit on every model, seed and thread
  count (same arithmetic in Rust and numba, same glibc `exp`/`log1p`, same
  best-of-16 starts); every oWALNUTS arm identical at threads 1 and 4;
  nutpie identical at cores 1 and 4; `from_pymc` ≢ gil_free on eight and
  hier (C vs NUMBA backends; WP47). The Python arms' start-evaluation counts
  equal the Rust arm's.
* **P5** ESS per gradient of every oWALNUTS arm within 0.8–1.25x of rust
  (threads=1, geomean over seeds), every model.
* **P6** The nutpie gap persists: per model in [1.2, 2.6], pooled in
  [1.4, 2.1] (primary arm `from_pymc`).
* **P7** ESS/s vs nutpie at matched threads/cores, every model: `from_pymc`
  0.10–0.40 (1), 0.03–0.25 (4, thread_safe); gil_free 0.35–1.2 (1 and 4);
  `from_jax` 0.05–0.6 (1); cfunc 1.5–12 (1) and 1.5–16 (4); rust 1.5–16 (4).
* **P8** All 126 sampler cells and 18 micro cells complete with exit code 0,
  including `from_pymc(thread_safe=True)` at threads=4 (F6 on Linux / 3.12);
  every oWALNUTS arm passes the gates on ≥ 8 of its 9 threads=1 cells; nutpie
  fails the gates on eight on ≥ 2 of 3 seeds (divergences, as in WP58) and
  passes gauss100 3/3 and hier ≥ 2/3.

## Decision rule for the README's Python guidance (frozen)

The rule decides documentation only (`protocol.json` `decision_rule`); no
library code or default changes. Model classes: `gauss100` = well-scaled
smooth posterior, `eight` = small funnel-shaped hierarchical model, `hier` =
larger hierarchical regression.

* **R1 (PyMC first choice).** If gil_free at threads=4 gives ≥ 2.0x the
  ESS/s of `from_pymc` at threads=1 on every model, completes every cell, and
  passes at least as many gate cells per model, the README recommends
  `from_pymc(model, gil_free=True)` with `threads=4` first for PyMC models on
  Linux; otherwise `from_pymc(model)` at threads=1 stays first and gil_free
  is an opt-in with its measured ratio.
* **R2 (PyMC vs nutpie, per model class).** If nutpie (cores=4) ESS/s ≥ 1.25x
  the R1 path's and nutpie passes the gates on ≥ 2/3 seeds, the README says
  nutpie is faster on that class by the measured ratio; if nutpie fails the
  gates on ≥ 2/3 seeds, it states the failure instead of a speed; otherwise
  it says the R1 path is competitive (ratio stated).
* **R3 (hand-written kernels).** If cfunc at threads=4 gives ≥ 2.0x py-njit
  at threads=1 on every model, recommend `from_cfunc` (numpy error model +
  guard) for speed; if cfunc's wall per gradient at threads=4 is ≤ 1.5x
  rust's on every model, say it runs within 1.5x of a native Rust target,
  else state the ratio.
* **R4 (threads for callables).** Per callable path (py-njit, jax,
  `from_pymc`): t4/t1 < 1.0 on ≥ 2 of 3 models → keep "use threads=1";
  ≥ 1.2 on every model → "threads=4 helps"; else "little difference".
* **R5 (the nutpie sentence).** Pooled gap in [1.4, 2.1] with every model
  > 1.2 → "persists on Linux" with the Linux numbers; pooled < 1.25 → "did not
  reproduce on Linux"; otherwise "smaller on Linux" with the numbers.
* **R6 (JAX).** jax at threads=1 ≥ 0.5x py-njit's ESS/s on every model →
  "competitive with a compiled callable"; else "JAX's per-call dispatch
  dominates small models", with the µs per gradient.

## Seeds

Sampler seeds 7878101–7878103, micro point seed 7878501. Checked unused
before the freeze: exact-word `git grep` over `main` and every local `wt/*`
branch, and `grep -rw` over `~/lanes` on the box.

Result of the check: no match on any branch (`git grep` exit 1) and none in
`~/lanes`.

## Setup done before the freeze (not evidence)

* Lane venv created and the packages above installed (all pinned versions
  resolved); the box clone is sparse (other studies' directories excluded)
  and checked out at `55e5a0aa`. `main` advanced to `b542b394` (WP75 docs
  and a research flag, off by default) while this study was being written;
  the code under test stays `55e5a0aa`, the base of this branch.
* The extension was built with `maturin develop --release` (pinned, 4 jobs)
  and imports with kernel revision
  `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. No sampler run and
  no timing was made.
* Disclosure: one `grep -rlw` for the seeds over `~/lanes` was first run
  without `taskset` (about 2 s of file reading, before any cell); it was
  repeated pinned. Every later command is pinned.
