# WP65 preregistration: BridgeStan dispatch on Linux (latency, fault rate, wall per gradient)

Frozen before any cell. `protocol.json` is the machine-readable form and wins on any
discrepancy. Ledger id `WP65-BRIDGESTAN-LINUX-DISPATCH-V1`.

## WP number

The highest WP in the README evidence list and the wiki ledger at freeze is WP63
(`delta2_default_confirmation_v1`). Lane 1 of the shared box takes WP64; this study is
**WP65**.

## Question

On Linux (native TLS, one C runtime), what does the BridgeStan path cost per gradient call on
each dispatch path the crate exposes, and is the off-Windows concurrent-replica dispatch, which
the README describes but has never qualified (the wiki lists "whether the historical
multi-replica path is safe on Linux and macOS" as open), safe and faster?

## What the crate exposes off Windows

Read from `integrations/bridgestan/src/lib.rs` at `a49df800`:

- **DirectSerialised**: `StanTarget` on a library built without `STAN_THREADS`. One module;
  every native call takes the module mutex. With four sampler threads this is the Linux
  analogue of the Windows owned-worker serialisation.
- **DirectConcurrent**: `StanTarget` on a `STAN_THREADS=true` library. One module called by all
  sampler threads at once.
- **ReplicatedConcurrent**: `ReplicatedStanTarget::load(.., n > 1)`. Replica 0 at the original
  path, replicas 1..n-1 as byte copies in the temp dir, free-replica `try_lock` dispatch. This is
  the default of `ReplicatedStanTarget::load` off Windows and what posteriordb v7's harness loads.

There is no Linux owned worker (it, and the process-global native-call lock, are `cfg(windows)`),
and no separate multi-worker owned path. "Multi-worker" on Linux means ReplicatedConcurrent.

## Environment (disclosed before running)

- AWS c7a.4xlarge, 16 dedicated EPYC 9R14 cores, no SMT, two 32 MB L3 instances (cores 0-7 share
  one), Ubuntu 24.04, g++ 13.3.0, Rust 1.88.0.
- **This study runs core-pinned on a shared box with three other lanes active.** Lane 2 = cores
  4-7; every build, driver, child and CmdStan process runs under `taskset -c 4-7` with
  `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1`. Lane 1 (cores 0-3) shares this lane's L3 instance;
  all lanes share memory bandwidth. All wall-clock and latency figures are therefore
  **pinned, co-tenanted**. ESS per gradient, pass counts, fault counts and bit-identity are
  unaffected by co-tenancy.
- Files live only under `~/lanes/bridgestan_linux_dispatch_v1/`; `TMPDIR` points there, so
  replica copies are written there. Shared `~/infra`, `~/venv`, `~/owalnuts` are read only.
- BridgeStan 2.9.0 (the version of the Windows record) from the release tarball
  (`b6034f83…a05a4c`), extracted twice (`bs-nothreads/`, `bs-threads/`) so the two builds share
  no objects. CmdStan 2.39.0 is a byte copy of `~/infra/cmdstan/cmdstan-2.39.0` so that model
  compiles cannot write into the shared tree. The lane venv is `~/venv`'s exact package set
  (arviz 0.23.4, bridgestan 2.9.0, cmdstanpy 1.3.0, numpy 2.5.4) plus posteriordb 0.2.0, which
  `~/venv` lacks and the v7 driver needs.
- Library source: `a49df800` (main at freeze); this study adds files only in its own directory.

## Seeds

Child seeds 65201001–65201500 (part b, shared by the three paths), cell seed 652651 (part c),
position seed 65299001 (part a), probe seed 65299002. `git grep -n -w -E
'65201[0-9]{3}|652651|6529900[0-9]'` over the worktree at `a49df800` found nothing.

## Part (a): gradient-call latency per dispatch path

Models eight_schools_noncentered (d = 10), arK (d = 7, N = 200) and diamonds (d = 26,
N = 5,000); builds `nothreads` and `threads`. One `latency` process per (repeat, model, build),
five repeats, repeat-major order. Each process measures, in order: `raw1` (raw function pointer,
one caller), `direct1` and `direct4` (one `StanTarget`, one and four callers), `replicated1` and
`replicated4` (`ReplicatedStanTarget`, four replicas, one and four callers). Every caller makes
the same calibrated number of calls (about 1 s for one caller) over 64 fixed positions; callers
start at a barrier. Statistic: medians over the five processes; ratios of medians.

| | prediction | point |
|---|---|---|
| A1 | `STAN_THREADS` is cheap on Linux: raw1 latency threads / nothreads <= 1.25 on each model (mingw: 9–16x) | 1.15 / 1.05 / 1.05 |
| A2 | replicas scale: nothreads replicated4 / direct4 throughput >= 3.0 on each model | 3.7 |
| A3 | one threaded module scales: threads direct4 / nothreads direct4 throughput >= 2.5 on each model | 3.4 |
| A4 | wrapper and dispatch are cheap: direct1 / raw1 and replicated1 / direct1 latency <= 1.15 everywhere | <= 1.05 |

## Part (b): fault rate over 500 children per path

The WP50D run shape (sblrc, 4 chains / 4 threads, 1,000/1,000, `Init::uniform()`, diagonal
metric, default adaptation and tuning), one process per (path, seed), seeds paired across paths,
order rotated per seed, strictly one child at a time, 300 s timeout. Arms `serialised`
(DirectSerialised), `replicated` (ReplicatedConcurrent, 4 replicas), `threaded_direct`
(DirectConcurrent). A probe at seed 65299002 must show the expected execution and replica count
for every arm before the matrix runs. An exclusive launch marker precedes every child; a launched
child is never relaunched.

A child is a **fault** on any of: nonzero exit or death by signal (SIGSEGV, SIGABRT from glibc
heap checks), timeout, missing/unparsable output, status not ok, wrong execution label or
replica count, non-finite retained value, wrong draw count, incomplete heartbeat sequence, or a
registered stderr marker (`corrupted`, `double free`, `free(): invalid`, `malloc():`, …).

| | prediction |
|---|---|
| B1 | **0 faults on every path**: serialised 0/500, replicated 0/500, threaded_direct 0/500. The Windows record had `STATUS_HEAP_CORRUPTION` at drop on the unserialised dynamic-runtime path (WP50C 2/120, WP50D 4/300); Linux has native TLS and one C runtime. 0/500 bounds the rate at 0.597% (one-sided 95%). |
| B2 | serialised and replicated give bit-identical FNV-1a draw fingerprints and identical target-call counts on all 500 seeds |
| reported | serialised vs threaded_direct parity (different build): expected identical, not gated |

## Part (c): wall per gradient vs CmdStan 2.39.0

The v7 fixed-16 models, seed 652651, 4 chains x 1,000/1,000, everything pinned to the lane.
Arms, per model in this order: `cmdstan` (cmdstanpy 1.3.0 defaults, four parallel chain
processes, no `STAN_THREADS`), `owalnuts` (v7's exact target call, `ReplicatedStanTarget`, four
replicas, nothreads build: ReplicatedConcurrent), `owalnuts-serialised` (one `StanTarget`,
nothreads build: DirectSerialised), `owalnuts-threaded` (one `StanTarget`, threads build:
DirectConcurrent). oWALNUTS runs `Sampler::new()` at the commit's defaults with only the run
shape and `admit_worst_case` set, exactly as v7. Metrics are v7's: wall around the sampler call
(start search excluded; CmdStan process launch and CSV I/O included), gradients including warmup,
wall per gradient = wall / gradients; geomean over models complete on both sides.

The Windows record (v7, WP56) measured 1.85x CmdStan's wall per gradient on the serialised
owned-worker path, contended; v6 (Windows, unserialised dynamic DLLs) measured 0.825x.

| | prediction | point |
|---|---|---|
| C1 | on the Linux default (replicated) path the gap disappears: owalnuts / CmdStan wall per gradient <= 1.0 | **0.85** |
| C2 | the serialised Linux path keeps a gap: owalnuts-serialised / CmdStan >= 1.5 | **2.3** (larger than Windows' 1.85x because pinned CmdStan has four uncontended cores while serialised gradients use one) |
| C3 | serialised / replicated in [1.8, 4.0] | 2.7 |
| C4 | owalnuts and owalnuts-serialised bit-identical (unconstrained draws SHA-256 and gradient count) on 16/16 | |
| C5 | no oWALNUTS error or timeout in any arm (48/48 ok) | |
| C6 | owalnuts-threaded / owalnuts wall per gradient <= 1.25 | 1.05 |

Reported, not gated: threaded vs replicated bit-identity, min bulk ESS per gradient vs CmdStan
(one seed), v7 gate pass counts /16 per arm.

## Decision rule (when the multi-worker path becomes qualified in the README)

**ReplicatedConcurrent is qualified on Linux x86_64 glibc** if and only if:

- Q1: part (b) replicated has 0 faults in 500 counted children;
- Q2: part (b) serialised-replicated parity is 500/500 and part (c) C4 is 16/16;
- Q3 (faster): part (a) nothreads replicated4 / direct4 throughput >= 2.0 on all three models,
  and part (c) owalnuts-serialised / owalnuts wall per gradient geomean >= 1.5;
- Q4: part (c) `owalnuts` arm 16/16 cells ok.

**DirectConcurrent (STAN_THREADS, one module) is qualified on Linux** if T1 threaded_direct has
0 faults in 500; T2 threads direct4 / nothreads direct4 throughput >= 2.0 on all three models;
T3 `owalnuts-threaded` 16/16 ok with wall per gradient <= 1.25x `owalnuts`.

If qualified, the README says: *Linux (x86_64, glibc, GCC 13.3, BridgeStan 2.9.0): the default
concurrent-replica dispatch is qualified (WP65): 0/500 child faults, draws bit-identical to the
serialised path, <A2>x gradient throughput at four callers, wall per gradient <C1>x CmdStan's on
the fixed-16 (pinned, co-tenanted, one seed).* Otherwise it stays unqualified and the README
names the failed clause. Scope: this host class, toolchain, BridgeStan version and run shapes;
nothing about macOS, aarch64, musl or Windows. Nothing here changes a default or library code.
`verdict.py` evaluates the rule mechanically.

## Changes to the v7 code (copy and parametrise)

`src/main.rs` is a copy of `STUDIES/posteriordb_bench_v7/src/main.rs`. Changes:

1. a `dispatch` argument (`replicated` | `direct`) and a `Loaded` enum that delegates `Target`
   and the counters to `ReplicatedStanTarget` or `StanTarget`; `replicated` is v7's call
   verbatim (`ReplicatedStanTarget::load(model, &default_preload(), Some(data), 1, threads)`);
2. the cell additionally records `dispatch`, `compiled_threading` and the process's
   `Cpus_allowed_list`; `threading` and `execution` come from the enum;
3. schema strings renamed; usage and module docs.

`sampler()`, `starts()`, the timing, the per-chain records and every other field are unchanged.

`run_bench.py` is a copy of `STUDIES/posteriordb_bench_v7/run_posteriordb.py`. Verbatim:
`posterior`, `stan_name`, `bridgestan_name`, `has_reference`, `reference`, `gate_names`,
`arviz_stats`, `chain_disagreement`, `metrics` and `failure` (schema string only), `write_cell`,
`save_draws`, `prepare_cmdstan`, `run_cmdstan`, `geomean`, `KEYS`, `model_arm_entry`,
`ratio_geomean`. Changes:

1. paths: the study's protocol keys, `artifacts/bench/`, `models/{nothreads,threads,cmdstan}/`,
   posteriordb at `~/infra/posteriordb`, the lane's CmdStan copy, `target/release/harness`;
   `WP65_SMOKE_ART` / `_MODELS` / `_SEEDS` replace v7's `V7_SMOKE_*` for pre-freeze smoke runs
   on a non-study posterior;
2. arms `cmdstan`, `owalnuts`, `owalnuts-serialised`, `owalnuts-threaded`; nutpie, the funnel
   row, the dense arm and the v6 comparison are removed;
3. models: the fixed-16 only; one seed;
4. the AMENDMENT-1 guard becomes `source_commit()`: the library source must equal `a49df800`;
5. `bridgestan_model()` loads the nothreads library for `param_constrain` and calls
   `windows_dll_path_setup()` only on Windows;
6. `run_owalnuts()` passes the arm's dispatch and library build; a failure records the return
   code; the cell additionally records dispatch, build, compiled threading, threading, CPU list,
   `model_info`, the SHA-256 of the unconstrained draws and per-chain target calls;
7. `run_all()` records `lscpu`, `g++`, affinity and the environment instead of the amendment;
8. `analyze()` is new: wall per gradient and ESS per gradient geomeans for each arm, the
   bit-identity checks and predictions C1–C6.

Libraries: v7 used Windows mingw builds copied from WP48/WP46. Here every BridgeStan library and
CmdStan executable is compiled on the box from the same posteriordb sources by
`build_models.py`, the nothreads build exactly as v7 (BridgeStan 2.9.0, no `STAN_THREADS`).

`src/bin/stress_child.rs` is adapted from the WP50D child: same run shape, heartbeats and
fingerprint; the arms are the crate's three Linux paths (no study-local target); the Windows
module probe becomes `/proc/self/maps` model/TBB mappings and a replica-copy cleanup check.
`src/bin/latency.rs` is derived from `integrations/bridgestan/src/bin/wallgap.rs` (five paths,
64 positions, barrier start, calibrated call count).

## Pre-freeze smoke runs (disclosed)

The predictions above were written before any binary ran. Before this commit the binaries and
drivers were smoke-tested on the box on a **non-study** posterior, `kidiq-kidscore_momiq` (seed
1 and the probe seed only, output in `~/lanes/.../smoke/`, never in `artifacts/`), while the
library builds were compiling on the same four cores. All three stress arms reported the
expected execution, a complete heartbeat sequence and one identical draw fingerprint; the four
(c) arms completed with identical oWALNUTS draws. The smoke latency ratios were seen
(threads/nothreads raw 1.45, replicated4/direct4 1.87, both on a small regression
with compilers sharing the lane). They are not evidence, and **no prediction or
threshold was changed after seeing them**.

## Rules

Parts run in the order (a), (b), (c), one process at a time. Builds, the probe and binary smoke
runs on a BridgeStan test model (not a study model, no study seed) are infrastructure. Every cell
is reported; failures, faults and timeouts are results; no reruns; no tuning after seeing results.
A driver killed by the host may be relaunched; launched-but-unrecorded children count as faults
and are not relaunched; an interrupted (c) cell with no artifact may be rerun once with the same
seed, recorded as a deviation. Amendments only for parts not yet run, committed before them.
