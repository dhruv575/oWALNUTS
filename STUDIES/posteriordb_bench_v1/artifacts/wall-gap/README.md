# Wall-gap investigation: why oWALNUTS-via-BridgeStan was ~10x CmdStan per gradient

Measured 2026-09-02 on the v1 machine (`../measured_on.json`), same
toolchain as v1 (BridgeStan 2.9.0, Stan 2.39.0, winlibs GCC 16.1.0
mingw-w64 ucrt-posix-seh, `mingw32-make`). Nothing in the v1 artifacts was
changed; everything here is new. Not preregistered; engineering evidence.

## Finding

**The whole gap is `STAN_THREADS=true` on a mingw-w64 GCC build.** GCC on
mingw-w64 implements `__thread`/`thread_local` with *emulated* TLS: every
access is a call to `__emutls_get_address` (83 call sites in the v1 arK
library vs 21 in the non-threaded one), and Stan Math touches its
thread-local `ChainableStack::instance_` for every autodiff node it records.
CmdStan's default build has no `STAN_THREADS`, so its autodiff stack is a
plain global and it never pays this. The v1 study built every BridgeStan
model with `make_args=["STAN_THREADS=true"]` (protocol note in
`run_posteriordb.py`, so that one model instance could serve four chain
threads), and nutpie's BridgeStan backend requires the same flag, which is
why nutpie was slow in the same way.

Nothing else contributes: the Rust wrapper (`StanTarget`) costs nothing
measurable over the raw C call, there is no per-call allocation or copy in
the wrapper, the flags differ from CmdStan's NUTS only in `propto` (`StanTarget`
passes `propto=false, jacobian=true`; CmdStan evaluates `propto=true,
jacobian=true`) and dropping constants can only make a call *cheaper*
(constant terms are doubles, not autodiff nodes), so it cannot explain a
10x; the model handle is not locked under `STAN_THREADS=true`; and `-march=native`,
`STAN_CPP_OPTIMS`, `STAN_NO_RANGE_CHECKS` are within noise.

## Per-call cost of `bs_log_density_gradient` (µs per call, 2,000 calls after 200 warm-up, one fixed point)

Quiet-machine pass (first run, recorded from the tool output; the machine was
idle apart from one model build on another core):

| model (dim) | build | (a) `StanTarget` | (b) raw fn ptr (Rust, no wrapper) | (b') raw C (`wallgap_c.c`) | (c) CmdStan inferred |
|---|---|---:|---:|---:|---:|
| arK (7) | v1 `STAN_THREADS=true` | 120.2 | 117.1 | 121.0 | 14.5 |
| arK (7) | no `STAN_THREADS` | **12.8** | 12.7 | 12.6 | 14.5 |
| hmm_example (4) | v1 `STAN_THREADS=true` | 445.2 | 452.5 | 452.7 | 36.0 |
| hmm_example (4) | no `STAN_THREADS` | **28.0** | 27.9 | 27.9 | 36.0 |
| eight_schools_noncentered (10) | v1 `STAN_THREADS=true` | 6.21 | 6.15 | 6.50 | 3.5 |
| eight_schools_noncentered (10) | no `STAN_THREADS` | **0.59** | 0.55 | 0.60 | 3.5 |

(c) is CmdStan 2.39.0's own cost inferred from the v1 cells: sum over the four
chains of `Elapsed Time` (warmup + sampling, from the CSV headers, per-chain
processes running in parallel) divided by `n_leapfrog__` summed over all
draws including warmup. arK seed 77102: 3.45 s / 238,570; hmm_example seed
77103: 3.63 s / 100,959; eight schools seed 77102: 0.259 s / 74,036. It
includes CmdStan's sampler and CSV-writing overhead, so it is an upper
bound on Stan's gradient cost; for eight schools (0.6 µs gradient) it is
dominated by that overhead.

Loaded-machine batch (`per-call.jsonl`, 3 reps, other agents running; all
numbers ~40% higher, ratios unchanged; min over reps):

| model | build | `StanTarget` | raw fn ptr | raw C | 4 threads, one instance (per-thread) | 4 threads, `ReplicatedStanTarget` (per-thread) |
|---|---|---:|---:|---:|---:|---:|
| arK | v1 threads | 168.6 | 172.9 | 177.5 | 215.5 | — |
| arK | nothreads | 18.5 | 18.3 | 18.0 | 83.5 (serialised) | **19.1** |
| arK | nothreads + `STAN_CPP_OPTIMS` + `STAN_NO_RANGE_CHECKS` | 16.4 | 15.9 | 16.0 | 76.3 | 16.1 |
| hmm_example | v1 threads | 669.1 | 630.1 | 590.4 | 859.5 | — |
| hmm_example | nothreads | 39.4 | 39.0 | 40.0 | 169.9 (serialised) | **43.9** |
| hmm_example | nothreads + optims | 35.8 | 36.1 | 37.2 | 157.6 | 41.6 |
| eight_schools_nc | v1 threads | 8.05 | 8.26 | 8.38 | 8.88 | — |
| eight_schools_nc | nothreads | 0.81 | 0.79 | 0.73 | 4.60 (serialised) | **1.32** |
| eight_schools_nc | nothreads + optims | 0.88 | 0.86 | 0.92 | 5.65 | 2.94 |

`-march=native` (`CXXFLAGS_OPTIM=-march=native`, with or without
`STAN_THREADS`): arK 12.9 / 117 µs, hmm_example 23.3 / 446 µs — no gain on
arK, ~15% on hmm_example — and the eight-schools library **segfaults at
load** on this toolchain (Eigen + AVX-512 stack alignment on mingw-w64).
Not recommended.

## Harness wall (arK, seed 77101, `da` arm, identical 241,119 target calls in every run)

| build | target | threads | wall s | vs v1 cell (10.54 s) |
|---|---|---:|---:|---:|
| v1 threads | `StanTarget` | 4 | 10.40 | 1.0x |
| v1 threads | `StanTarget` | 1 | 31.19 | (3.0x parallel speedup on 4 threads) |
| nothreads | `ReplicatedStanTarget` x4 | 4 | **1.53** | 6.8x faster |
| nothreads | `ReplicatedStanTarget` x1 | 1 | 5.29 | (3.5x parallel speedup) |

hmm_example seed 77101 (199,322 calls): 33.0 s -> **2.66 s**.
eight_schools_noncentered seed 77101 (74,795 calls): 0.178 s -> **0.038 s**.

## Projected wall ratio vs CmdStan at equal gradient counts

Using the fixed harness walls above and CmdStan's v1 walls (cmdstanpy,
4 parallel processes, including process launch and CSV I/O):

| model | oWALNUTS s / grads | CmdStan s / grads | oWALNUTS µs/grad | CmdStan µs/grad | ratio (was) |
|---|---|---|---:|---:|---:|
| arK | 1.53 / 241,119 | 1.03 / 238,570 | 6.35 | 4.32 | **1.47x** (was 10.2x) |
| hmm_example | 2.66 / 199,322 | 1.52 / 100,959 | 13.4 | 15.1 | **0.89x** (was 21.9x) |
| eight_schools_nc | 0.038 / 74,795 | 0.17 / 74,036 | 0.50 | 2.3 | **0.22x** (was 1.0x) |

## What remains unexplained

* arK is still 1.47x CmdStan per gradient at the harness level although the
  bare gradient is *cheaper* than CmdStan's inferred cost (12.8 vs 14.5 µs).
  With 4 threads on a shared machine the replicated per-thread cost was
  19–21 µs against 12.8 µs single-threaded, i.e. 4 threads reach ~3.5x, not
  4x; CmdStan's 4 processes have the same problem and its 1.03 s wall
  includes launch and CSV I/O, so the comparison is within run-to-run noise
  of this shared machine (v1 CmdStan arK seeds: 0.96–1.30 s). A clean
  attribution needs a quiet machine and per-chain timers on both sides.
* `STAN_CPP_OPTIMS`/`STAN_NO_RANGE_CHECKS` gave 5–10% on the loaded batch;
  not separated from noise here.
* nutpie's slowness is the same cause (its BridgeStan backend is built with
  `STAN_THREADS=true`); it is not fixable from this repository.

## Fix applied

1. `integrations/bridgestan`: new `ReplicatedStanTarget` (N copies of the
   library at distinct temp paths, one per thread; each copy is a distinct
   module with its own global autodiff stack; per-call dispatch is one
   uncontended `try_lock`, ~50 ns). `StanTarget`'s serialising mutex is now
   shared per library file (two instances of the same non-threaded file in
   one process were previously unsafe to evaluate concurrently). README
   documents the recommended build: no `STAN_THREADS` on Windows/mingw.
2. `STUDIES/posteriordb_bench_v1`: the harness loads a
   `ReplicatedStanTarget` with `threads` replicas; `run_posteriordb.py`
   compiles with `BRIDGESTAN_MAKE_ARGS = []` (was `["STAN_THREADS=true"]`).
   Deviation note in the study README. v1 artifacts untouched; the v1 ESS
   per gradient and gate results are unaffected (the trajectory is
   bit-identical: same 241,119 target calls), only ESS per second changes.

## Files

* `wallgap.rs` (in `integrations/bridgestan/src/bin/`): (a), (b), 4-thread
  single-instance and replicated per-thread costs.
* `wallgap_c.c`: (b') raw C via `LoadLibrary`/`GetProcAddress`.
* `build_variants.py`: builds the flag variants into `models/wallgap/<variant>/` (gitignored).
* `per-call.jsonl`: the loaded-machine batch, raw.
* `build-log.txt`: variant build log.
