# Thread scaling v1 (WP45) — how oWALNUTS wall time scales with chains and threads

**Verdict: mixed.** The driver is correct and has no internal scaling defect
that this contended machine could expose. Draws were bit-identical across every
thread count, repetition and binary (165 grid cells, every profile run and 36 A/B
cells). Multi-chain runs did speed up. At 16 chains, 16 threads gave 4.6x on the
cheap target (`gauss100`), 3.9x on the autodiff target (`ll1000`) and 2.8x on
BridgeStan `arK`. Those speedups were capped by the 2–3 cores the other agents
left free, and by chain-length imbalance. The one real shared-counter mechanism
(fix F1) was **not merged**: the frozen rule failed on its no-regression clause
(C=T=1 ratio 0.92), and its 1.98x at C=T=16 coincides with the fixed arm getting
more CPU (4.3 vs 1.7 cores). F1 shows no CPU-per-gradient saving here.

**All wall numbers here are CONTENDED PILOTS.** Nine other agents kept 11–13.5 of the 16 cores
busy throughout ("other load" column). A single-thread run received only
0.25–0.67 of a core. Gradient counts, ESS, fingerprints and allocation counts do
not depend on the machine; walls are upper bounds. `RUN-QUIET.md` gives the
one-line idle-machine rerun.

Study: preregistered at `6a569881` (the harness binaries missed by an ignore
pattern followed in `e4c5bf56`, still before any evidence). The pilot grid ran
2026-10-24 18:31–19:31 local, the profile ran 19:31–19:35 and the A/B ran
19:35–19:50. Machine: Intel Core Ultra 7 255H (6 P + 8 E + 2 LP-E, no SMT),
Windows 11, Rust 1.88 GNU.

## What determines scaling (answers to the question)

| candidate | evidence | verdict |
|---|---|---|
| machine contention (other agents) | process CPU/wall at T=16 is only 2.77 (`gauss100`), 1.88 (`ll1000`) and 0.84 (`ark`), with 11–13 other cores busy. In the timeline, per-thread CPU/span is 0.45–0.93 on `gauss100` and 0.11–0.53 on `ll1000`. Threads were runnable but not running. | **dominant in this pilot** |
| chain-length imbalance (wall = longest chain once T >= C) | max/mean chain gradients at C=16: 1.51 on `gauss100` and **3.05 on `ll1000`**. One `ll1000` chain made 1.01 M gradients while another made 43 k. That alone caps C=T=16 at 10.6x on `gauss100` and 5.2x on `ll1000`, even on an idle machine. | **a hard bound, target-dependent** |
| hybrid cores | `gauss100` C=T=16: E-core threads spend ~1.2x the CPU per gradient of P-core threads (~2.06 vs ~1.72 µs outside the target). No thread was ever sampled on the two LP-E cores. | moderate |
| BridgeStan Windows owned worker | `ark` speedup 1.6–3.7x despite full serialisation. At T=1, CPU/wall is 0.25–0.36: every gradient is a rendezvous hand-off (`sync_channel(0)` per call) to the owner thread and back. That costs two OS wake-ups, which are slow on a loaded machine. More caller threads keep the owner's queue non-empty. C=16 throughput is flat beyond T=4 (15.4–15.9 k gradients/s). | **serialised, but latency-bound, not compute-bound** |
| shared counter (`TargetEvaluationBudget::reserve`, one CAS per gradient on the default `Limits::admit_worst_case` path) | CAS bench, no work between ops: 899 ns/op/thread at n=16 vs 67 ns for the no-counter control (13x; capacity ~18 M CAS/s). With ~1 µs of work per op: 1.9x at n=16, 3.3x at n=8. With ~4 µs: no effect. A `gauss100` gradient is ~1.5–2 µs, of which 0.09 µs is inside the user target. The A/B shows no CPU-per-gradient saving (ratios 1.00, 1.00, 1.10, 0.86 at C=T=1/4/8/16; 1.03 and 1.01 on `ll1000`). | real mechanism, **not visible at ≤ 3 effective cores**; would matter for sub-µs gradients on an idle 16-core box |
| allocator | 2.3–2.8 heap allocations per gradient on `gauss100` (22–26 per transition) and 0.06–0.08 on `ll1000` (64 per transition). A thread-local caching allocator changes C=T=16 wall by −4.9 % (median of 3; within noise) and C=T=1 by −8 %. | not a scaling factor here; a single-thread cost worth a separate look |
| thread spawn / result collection / RNG | timeline: wall minus the longest thread's active span is 7 ms of 803 ms (`gauss100` C=T=16) and 176 ms of 29.8 s (`ll1000`). That gap covers pool build, chain hand-out, `finish` and collection: < 1 %. RNG is per chain (`SmallRng`), never shared. | negligible |
| threads > chains | the driver clamps T to C; `metadata.thread_count` = C in every T > C cell; `gauss100` T > C walls are noise around T = C | as designed |

## Predictions

| id | predicted | observed (median of 3) | held? |
|---|---|---|---|
| P1 `gauss100` efficiency at C=16 | T2 .90, T4 .75, T8 .50, T16 .30 | 1.08, 0.79, 0.52, 0.29 | T4/T8/T16 held within 0.05; T2 exceeded (the T=1 baseline got 0.44 cores) |
| P2 `gauss100` weak scaling | 0.45 at k=8 and k=16 | 0.49, 0.36 | k=8 held, k=16 failed (lower) |
| P3 `ll1000` efficiency at C=16 | .85, .70, .50, .30 | 1.07, 1.04, 0.55, 0.24 | T8 held; T2/T4 failed (super-linear vs a 0.42-core T=1 baseline); T16 within 0.06 |
| P4 `ark` speedup in [0.8, 1.1] | flat | 1.6–3.7x (C=16: 1.61/2.74/2.73/2.83) | **failed**: hand-off latency, not compute, bounds the serialised path |
| P5 bit identity | 100 % | 100 % (grid, profile, A/B; metadata identical too) | held |
| P6 allocations / ablation | 2–4 and < 0.05 per gradient; ablation < 5 % | 2.29–2.83 and 0.056–0.077; −4.9 % | `gauss100` held, `ll1000` failed narrowly, ablation held narrowly |
| P7 hybrid cores | E 1.2–1.6x P; LP-E unused | ~1.2x; 0 LP-E samples | held (low end) |
| P8 CAS bench | < 1.5x at 256–1024 steps, >= 3x at 0–64 | 1.9x (256), 0.85x (1024); 13x (0), 2.2x (64) | mixed |
| P9 F1 | 1.00/1.00/1.03/1.08, rule not met | 0.92/1.60/0.65/1.98 wall ratios; CPU ratios 1.00/1.00/1.10/0.86 | outcome held (not met) but via the regression clause; wall ratios are contention noise |
| P10 why | contention + imbalance 1.2–1.6 + E-cores; spawn etc. < 2 % | contention dominant; imbalance 1.51 / **3.05**; overhead < 1 % | held except the `ll1000` imbalance size |

## Fix F1 and the decision

F1 (`walnutpie::sample_chains_with_target_budget_metered`, `BudgetMetering`)
lets `Sampler::run` on the identity/diagonal path skip the shared
`TargetEvaluationBudget` compare-and-swap when its private budget covers the
preflight's exact worst case, which is always so under the default
`admit_worst_case`. The public budgeted entry point keeps exact metering, and
the change is covered by the unit test
`unmetered_covered_budget_is_bit_identical_to_the_metered_run`. `cargo test`
passed, including `tests/kernel_fingerprint.rs`
(`artifacts/cargo-test-fix.log`), and every A/B pair has identical draws, work
and metadata.

Rule outcome: bit-identical yes. The C=T=16 ratio was 1.98 (>= 1.15) and the
C=T=8 ratio 0.65. The C=T=1 ratio was 0.92, below 1/1.05, so the
no-regression clause fails: **DO NOT MERGE**. The individual walls show why:
two cells hit contention outliers (5.15 s against 0.38 s, and 45.1 s against
0.55 s). The fixed arm's C=T=16 cells ran with 4.3 cores against the baseline's
1.1–3.5. F1 stays on the branch as a candidate for a quiet-machine study.

## Quiet-machine rerun (2026-10-25, `artifacts/quiet/`)

Run per `RUN-QUIET.md` after the other nine WP41–50 agents had finished
(other load 1.3–2.2 cores throughout, versus 4–10 during the contended run).
Rule outcome on the quiet box: bit-identical yes; A/B baseline/fixed medians
1.027 (C=T=1), 1.066 (4), 1.053 (8), 1.004 (16) on `gauss100`, 1.004 / 1.074
on `ll1000` (1 / 16). The C=T=16 ratio is below the 1.15 threshold, so the
decision stays **DO NOT MERGE**; the contended run's 1.98 at C=T=16 was a
contention artefact, not a CAS effect. The `cas-bench` profile explains why:
the shared counter costs 850 ns/op at 16 threads with no work between
increments but is indistinguishable from a per-thread add once 1,024 work
steps separate increments, and a gradient is far more than that.

Clean scaling numbers (median of 3, speedup versus T=1 at the same chain
count): `gauss100` 16 chains reaches 6.80x at 16 threads (efficiency 0.43);
`ll1000` 16 chains reaches 3.90x at 8 threads and does not improve at 16
(3.85x; max/mean chain gradients 3.05, so the slowest chain bounds the wall);
`arK` (BridgeStan, owned worker) saturates at 1.6–1.8x from 2 threads
onwards at every chain count, the signature of the Windows process-wide
serialisation that WP50 removes with a static runtime. Draws, transition
diagnostics and telemetry are identical across every thread count and
repetition. This machine has 6 P, 8 E and 2 LPE cores
(`measured_on-*.json`), which caps 16-thread efficiency independent of the
sampler.

## Recommendations

1. **Nothing changes in the defaults or the sampler on this evidence.** F1 is
   not merged under its frozen rule. If the quiet rerun shows the CAS cost
   on cheap targets, preregister F1 again on an idle box. It is bit-identical
   and API-preserving.
2. Docs: state that `threads` above `chains` does nothing, and that
   wall time is bounded by the slowest chain. On `ll1000`-like targets one
   chain can make 3x the mean gradients.
3. BridgeStan on Windows: the owned worker is latency-bound. Use T >= 4
   even though calls are serialised. A spin-then-park or batched hand-off
   would need its own requalification (BRIDGESTAN-OWNED-WORKER-V1 is frozen).
4. Single-thread: on `gauss100` about 95 % of the time per gradient is
   kernel/driver, with ~2.5 allocations per gradient (per-transition momentum
   and cached-input clones and traced warmup events). This is the larger
   lever for cheap targets, but it is not a threading issue.

## Anomalies and process notes

- The shared brief caps processes at 4 threads. This task required 8- and
  16-thread cells; they were run once per repetition and are short.
- Profile step 2 (`allocs ll1000`): the driver was stopped by an operator
  mistake (an outer 590 s timeout wrapper). The child process finished and
  wrote its file. The resumed driver skipped steps 1–2 (refused to overwrite,
  `exit 101` in `profile-log.txt`) and ran steps 3–6. No cell was rerun.
  `measured_on-profile.json` is from the resumed driver.
- Calibration (seed 945199, non-evidence) is described in `protocol.json`.
  One calibration `ll1000` C=T=4 run spent 162 s wall for 41 s CPU.
- `ll1000` at 200/200 has min bulk ESS 3–110. It was sized for scaling, not
  inference.
- The `ark` model was compiled here from posteriordb `28f8d3d` with BridgeStan
  2.9.0, without STAN_THREADS (`models/compile.log`). The `.so` is not committed.

## Files

`PREREGISTRATION.md`, `protocol.json`, `RUN-QUIET.md`, `src/lib.rs` (targets,
counters, fingerprints, cell), `src/bin/grid.rs` (timing harness),
`src/bin/profile.rs` (instrumented allocator, probe, ablation, CAS bench),
`build_bins.py`, `run_grid.py`, `artifacts/grid/cells/*.json` (165),
`artifacts/ab/cells/*.json` (36), `artifacts/profile/*.json`,
`artifacts/{summary.json,results-table.md,run-log.txt,profile-log.txt,ab-log.txt,measured_on-*.json}`,
`checksums.py`, `CHECKSUMS.sha256`.
