# WP65: BridgeStan dispatch on Linux (latency, fault rate, wall per gradient vs CmdStan)

## Verdict

**Both concurrent Linux dispatch paths are qualified under the frozen rule. The concurrent-replica
dispatch (`ReplicatedStanTarget::load`, the off-Windows default) had 0/500 faults. Its draws were
bit-identical to the serialised path in 500/500 children and on 16/16 benchmark models, and its
wall per gradient was 0.96x CmdStan 2.39.0's. On Linux the 1.85x Windows gap comes from
serialisation, not from BridgeStan.** The single-module `STAN_THREADS` path also met its rule,
but only just: 1.248x the replicated wall per gradient against a 1.25 limit.

This is a process and engineering study, not posterior evidence. The run was
pinned to cores 4-7 of a shared 16-core EPYC box (c7a.4xlarge, Ubuntu 24.04, g++ 13.3,
BridgeStan 2.9.0 / Stan 2.39.0, Rust 1.88), with three other lanes active. Every wall and
latency figure is therefore **pinned, co-tenanted**. Fault counts, bit-identity, ESS per gradient
and pass counts do not depend on co-tenancy.

| path (Linux) | faults /500 (95% UB) | parity vs serialised | 4-caller throughput vs serialised (a) | wall/grad vs CmdStan, fixed-16 (c) | rule |
|---|---:|---|---:|---:|---|
| DirectSerialised (`StanTarget`, no `STAN_THREADS`) | 0 (0.60%) | — | 1 | **3.46x** | reference |
| **ReplicatedConcurrent** (`ReplicatedStanTarget`, 4 replicas) | **0 (0.60%)** | **500/500 and 16/16 bit-identical** | **4.0–5.4x** | **0.96x** | **qualified** |
| DirectConcurrent (`StanTarget`, `STAN_THREADS=true`) | 0 (0.60%) | 500/500 and 16/16 bit-identical (different build) | 2.5–4.4x | 1.20x | qualified (T3 1.248 <= 1.25) |

Predictions: 11 of 12 held. **A1 failed**: `STAN_THREADS` is not uniformly cheap on Linux. A
single call costs 1.22x on eight schools, **1.57x on arK** and 1.01x on diamonds (threshold
1.25). The penalty carries into sampling: the threaded arm averages 1.25x the replicated arm's
wall per gradient (arK 1.62x, nes 1.47x).

## What the README should say

> **Linux (x86_64, glibc, GCC 13.3, BridgeStan 2.9.0):** the default concurrent-replica dispatch
> of `ReplicatedStanTarget::load` is qualified (WP65). 0/500 child faults (95% upper bound
> 0.60%); draws bit-identical to the serialised path; 4.0–5.4x gradient throughput at four
> callers; wall per gradient 0.96x CmdStan's on the fixed-16 (pinned, co-tenanted, one seed).
> Serialising the same library costs 3.6x. A `STAN_THREADS=true` library behind one
> `StanTarget` is also safe (0/500) but 1.0–1.6x slower per call than the default build. Build
> without `STAN_THREADS` and use `ReplicatedStanTarget` on Linux too.

This replaces the "Linux/macOS (native TLS) it is cheap" line in the integration README's build
table. macOS, aarch64, musl and Windows are outside this study.

## Results

### (a) Gradient-call latency (medians of 5 processes; `artifacts/latency/results-table.md`)

| model | raw µs nothreads / threads | A1 threads/nothreads | A2 replicated4/direct4 | A3 threads direct4 / nothreads direct4 | A4 max wrapper ratio |
|---|---|---:|---:|---:|---:|
| eight_schools_noncentered (d 10) | 0.67 / 0.82 | 1.215 | **5.43** | 4.37 | 1.06 |
| arK (d 7) | 20.5 / 32.2 | **1.572** | **4.06** | 2.54 | 1.02 |
| diamonds (d 26) | 38.5 / 38.8 | 1.008 | **3.98** | 4.03 | 1.02 |

- **A1 failed** (arK 1.57 > 1.25). A2, A3 and A4 held.
- With four callers, DirectSerialised throughput falls *below* one caller's. On eight schools
  each call is 5.7x slower per caller, so the four callers are worse together than one alone.
- Replicas add 2–6% per-caller latency at four callers.
- The wrapper and the replica dispatch add <= 6% over the raw function pointer.

### (b) Fault rate (`artifacts/stress/result.md`)

The run used sblrc with 4 chains / 4 threads, 1,000/1,000, the WP50D run shape. Seeds
65201001–65201500 were paired across arms, 1,500 children ran one at a time, and nothing was
interrupted or rerun.

| path | children | faults | median sampling wall s |
|---|---:|---:|---:|
| serialised | 500 | 0 | 0.354 |
| replicated | 500 | 0 | 0.088 |
| threaded_direct | 500 | 0 | 0.105 |

- **B1 held**: no nonzero exit, signal, timeout, glibc heap message or incomplete heartbeat.
- **B2 held**: 500/500 fingerprints and call counts were identical between serialised and
  replicated.
- Serialised vs threaded_direct was also 500/500 identical (reported).
- Replica copy directories were removed in every replicated child.
- Descriptive: **a `STAN_THREADS` model library stays mapped after its `StanTarget` drops (500/500
  children)**. glibc keeps a DSO loaded while it has registered thread-local destructors. The
  non-threaded library was unmapped in every child. The integration README's "unload-on-drop"
  statement therefore holds only for non-`STAN_THREADS` builds.

### (c) Wall per gradient vs CmdStan, fixed-16, seed 652651 (`artifacts/bench/results-table.md`)

| ratio (geomean, 16/16 models) | value | prediction |
|---|---:|---|
| owalnuts (replicated) / CmdStan | **0.959** | C1 <= 1.0 (point 0.85): held |
| owalnuts-serialised / CmdStan | **3.462** | C2 >= 1.5 (point 2.3): held |
| serialised / replicated | 3.609 | C3 in [1.8, 4.0] (point 2.7): held |
| threaded / replicated | 1.248 | C6 <= 1.25 (point 1.05): held, by 0.002 |

- **C4 held**: replicated and serialised gave 16/16 identical unconstrained draws and gradient
  counts. The threaded build was also 16/16 identical (reported).
- **C5 held**: 48/48 oWALNUTS cells completed.
- Per model, replicated/CmdStan ranges from 0.77 (eight schools noncentered) to 1.26 (earnings).
  Gradient-bound models sit at 1.0 (diamonds 1.02, gp_pois_regr 0.99).
- Reported, one seed: oWALNUTS passes 13/16 gates in each arm (identical draws), CmdStan 12/16.
  Min bulk ESS per gradient is 0.944x CmdStan's.
- The passing `one_comp` oWALNUTS cell has max |z| 4.69, above v7's flag of 4. CmdStan's
  `one_comp` cell is 4.41 and fails its gates.

## Against the Windows record

- **Windows v7 serialised gap, 1.85x (contended):** reproduced only on the serialised path, and
  larger: 3.46x pinned. Pinned CmdStan has four uncontended cores, while serialised gradients
  use one.
- **Linux default path:** 0.96x. This is consistent with v6's 0.825x on Windows before the
  owned worker.
- **WP50C payoff of removing serialisation, 3.2–4.0x:** reproduced at 3.6x, as the fixed-16
  geomean.
- **Windows mingw `STAN_THREADS` cost, 9–16x:** does not apply on Linux (1.0–1.6x). The
  integration README's "cheap on Linux" did not reproduce for arK (1.57x).
- **Windows `STATUS_HEAP_CORRUPTION` at drop:** no Linux analogue in 1,500 children.

## Reproduce

On the box, inside `~/lanes/bridgestan_linux_dispatch_v1/` with `env.sh` sourced and every
command prefixed with `taskset -c 4-7`:

```
python build_models.py 3 && cargo build --release -j4 --locked
python run_latency.py run && python run_latency.py analyze
python run_stress.py probe && python run_stress.py run && python run_stress.py analyze
python run_bench.py run && python run_bench.py analyze
python verdict.py && python checksums.py
```

The single run happened 2026-10-26 01:13–01:40 UTC at study commit `42455688` (library
`a49df800`). `PREREGISTRATION.md` lists every change to the v7 code. Uncommitted raw draws,
CmdStan CSVs and models remain on the box; draws are hashed in `CHECKSUMS.sha256`; stress
heartbeats are in `artifacts/stress/heartbeats.tgz`.
