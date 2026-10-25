# Preregistration — thread_scaling_v1 (WP45-THREAD-SCALING-V1)

Frozen 2026-10-25 before the first evidence cell. `protocol.json` is the
machine-readable copy and is authoritative where the two differ; both are
hashed in `CHECKSUMS.sha256`. Base commit `3583d130` (0.2.0).

## Question

The machine has 16 cores (Intel Core Ultra 7 255H: 6 P, 8 E, 2 low-power E,
no SMT) and users see ESS per second. How does `Sampler::run` wall time scale
with chains C in {1,2,4,8,16} and threads T in {1,2,4,8,16} on

- (a) `gauss100`: a 100-D standard Gaussian with a hand gradient;
- (b) `ll1000`: the owalnuts-autodiff T=1000 local-level path;
- (c) `ark`: posteriordb `arK-arK` through BridgeStan, which on Windows is one
  owned worker behind a process-global mutex (BRIDGESTAN-OWNED-WORKER-V1);

and where it is sub-linear, why: allocator contention, shared counters / false
sharing, RNG, thread spawn, per-transition result collection, the BridgeStan
serialisation, hybrid cores, chain-length imbalance or other load?

## What code reading found before any evidence

1. `sample_chains_validated` clamps T to min(T, C) and runs one Rayon
   `par_iter` item per chain in a run-local scoped pool. T > C is a duplicate
   of T = C.
2. `Limits::default()` has `admit_worst_case = true`, so **every default
   `Sampler::run` wraps the target in `BudgetedTarget`**, whose `reserve()` is
   a compare-and-swap on one shared `AtomicUsize` per target call, written by
   every chain thread. This is the one shared, per-gradient, written cache
   line on the default path.
3. RNG is per chain; outputs are reserved up front; kernel workspaces are
   thread-local caches. Nothing else written is shared per gradient.

## Calibration (non-evidence seed 945199)

Used only to size the workloads and to test the instruments; listed in full
in `protocol.json`. Notably the probe showed that on `gauss100` a gradient
costs ~1.8 µs of which ~0.09 µs is inside the user target, so the per-thread
CAS rate is ~0.5 M/s (8 M/s at 16 threads), and ~3 heap allocations happen
per gradient. One `ll1000` C=T=4 calibration run took 162 s wall for 41 s CPU
while the machine was 87 % busy — contention episodes of that size are
expected in the pilot.

## Protocol

- Grid (baseline library): `gauss100` all 25 cells, `ll1000` and `ark` the 15
  cells with T <= C; three repetitions, rep-major, chains then threads
  ascending; one process per target; strictly sequential. Workloads and seeds
  in `protocol.json` (945101–945103).
- Per cell: wall around `Sampler::run`, process user/kernel CPU, system busy
  core-seconds (so "other load" = system busy − own CPU), page faults, peak
  working set, gradients per chain, fingerprints, min bulk ESS, ESS/s.
- **Correctness check:** at fixed (target, C) the draws + diagnostics +
  telemetry fingerprint of every chain must be identical across every T and
  repetition. The harness records and exits nonzero on a mismatch.
- Profile (baseline library, instrumented binary): allocation counts, a
  per-thread timeline (inside/outside the user target, CPU/span, P/E/LPE
  placement), an allocator ablation (system vs thread-local cache, ABBA, 3
  reps) and a shared-CAS micro-benchmark.
- Fix under test **F1** (code reviewed, unit-tested, committed with this
  preregistration): `Sampler::run` on the identity/diagonal path skips the
  shared budget counter when its private budget covers the preflight's exact
  worst case (always, under the default `admit_worst_case`); the public
  budgeted entry point keeps exact metering. A/B: baseline vs fixed binaries,
  interleaved per cell with alternating order, `gauss100` C=T in {1,4,8,16}
  and `ll1000` C=T in {1,16}, three repetitions.

## Predictions (contended pilot)

| id | prediction |
|---|---|
| P1 | `gauss100` strong-scaling efficiency at C=16: T=2 0.90, T=4 0.75, T=8 0.50, T=16 0.30 |
| P2 | `gauss100` weak scaling wall(1,1)/wall(k,k): 0.45 at k=8 and k=16 |
| P3 | `ll1000` efficiency at C=16: T=2 0.85, T=4 0.70, T=8 0.50, T=16 0.30 |
| P4 | `ark` speedup in [0.8, 1.1] at every (C, T) (efficiency 0.05–0.07 at T=16) |
| P5 | fingerprints identical in 100 % of cells and in every A/B pair |
| P6 | 2–4 allocations per gradient on `gauss100`, < 0.05 on `ll1000`; allocator ablation moves C=T=16 wall by < 5 % |
| P7 | E-core threads 1.2–1.6x the CPU per gradient of P-core threads; LPE cores mostly unused |
| P8 | shared CAS < 1.5x the no-counter control at n=16 with 256–1024 work steps; >= 3x with 0–64 |
| P9 | F1 ratio 1.00 at C=T=1,4; 1.03 at 8; 1.08 at 16; **decision rule not met**; `ll1000` within ±3 % |
| P10 | sub-linearity is machine contention + chain-length imbalance (max/mean 1.2–1.6) + E-cores; spawn, RNG, collection < 2 % of wall; BridgeStan on Windows has no parallelism |

## Decision rule (from the task, frozen)

Merge F1 iff (1) every A/B cell is fingerprint-identical (draws, work and
metadata) and `cargo test` passes, (2) on `gauss100` median baseline wall /
median fixed wall >= **1.15 at C=T=8 or C=T=16**, and (3) that ratio is
>= 1/1.05 at C=T=1 and C=T=4. Otherwise do not merge. The contended pilot
decides; the quiet rerun (`RUN-QUIET.md`) is reported beside it.

Failures are results; nothing is rerun or tuned after seeing results. The
shared brief's four-thread cap is exceeded deliberately (the task requires 8-
and 16-thread cells); those cells are short and run once per repetition.
