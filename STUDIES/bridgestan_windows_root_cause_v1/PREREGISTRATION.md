# WP50 — Windows-GNU BridgeStan heap-corruption root cause: preregistration

Status: engineering/process diagnostic only. Frozen before the evidence cells
run. This study does not alter, rerun, or reinterpret any prior study's
immutable records. WP35/WP36 posteriordb evidence seeds (90101, 90102, 90103)
are forbidden and are hard-rejected by the harness.

## Question (wiki/open-questions.md item 8)

On Windows GNU a BridgeStan child sometimes dies with STATUS_HEAP_CORRUPTION
(`0xC0000374`) after sampling completes, during teardown.
`sblrc_process_stability_v1` reproduced it in 1/46 children;
`bridgestan_lifetime_v1` (8/180) and the `bridgestan_owned_worker_v1`
comparator (16/180 heap, 19/180 fault-union) reproduced it with resident DLLs
and scoped Rayon pools; the owned-worker mitigation cleared it (0/540) at
3.1–5.1x sampling cost. The root cause is not established. Establish it or
narrow it decisively; if a cheap fix exists, measure it.

## Hypotheses (frozen) and their discriminating experiments

- **H1 — mingw emulated-TLS autodiff-stack destructor on `FreeLibrary`.** Stan
  Math's thread-local autodiff stack has emutls destructors; if the model DLL
  is unloaded (Rust `libloading::Library` drop) before worker threads exit or
  before the emutls destructor runs, the destructor touches unmapped/reused
  memory → heap corruption at drop.
  Discriminators: (a) **never-unload** — hold the `Library` resident
  (`std::mem::forget`); (b) **join-first** — join every worker OS thread before
  dropping the `Library`; (c) **build-symbol analysis** — whether the faulting
  build even contains the thread-local autodiff stack and its emutls
  destructor.
- **H2 — allocator mismatch** across the DLL/Rust boundary (memory allocated
  by the DLL's CRT freed by Rust's, or vice versa), e.g. in the error-message
  or parameter-names path. Discriminator: static audit of every pointer that
  crosses the FFI boundary in `integrations/bridgestan/src/lib.rs`.
- **H3 — double-free / use-after-free in the owned-worker drop ordering**
  (model destroyed while an RNG object or another model handle still
  references it). Discriminator: static audit of the drop order and the
  owned-worker lifecycle, plus the `owned_worker` empirical arm.
- **H4 — `STAN_THREADS` build difference.** The repo uses a non-threads build;
  does a `STAN_THREADS=true` build change the fault signature? Discriminator:
  build both, compare the exported emutls/TLS symbol set, and run the
  `sampler_concurrent` baseline against each build.

## Fixed external inputs (read-only; copied into `models/`, hashes in `protocol.json`)

- posteriordb `sblrc`/`blr` and `arK`/`arK` Stan programs and JSON data from
  the frozen posteriordb checkout (`28f8d3d`), compiled with BridgeStan 2.9.0 /
  Stan 2.39.0 (mingw-w64 GCC 16.1.0), **no `STAN_THREADS`** for the primary
  models and **`STAN_THREADS=true`** for the H4 model (`sblrcT`).
- `tbb.dll` preload from the BridgeStan home.

## Harness (committed before evidence)

A single Rust child binary (`src/main.rs`) with selectable arms, linked
directly against BridgeStan via hand-written `libloading` FFI (NOT through the
`owalnuts-bridgestan` owned-worker backend), so that concurrency, thread
lifetime and library lifetime are the controlled variables. Two families:

Micro arms (direct gradient bursts, no sampler):
`main_only`, `concurrent_resident`, `concurrent_unload`, `serialized_resident`.

Sampler arms (the real `owalnuts::sampler::Sampler`, Rayon multi-chain, tree
building) over a BridgeStan target:
- `sampler_concurrent` — R resident replica modules, each gradient dispatched
  to a free replica and called directly with no process-global serialization
  (the reproducing comparator's native-execution model). Libraries resident
  (never unloaded). **Baseline.**
- `sampler_concurrent_unload` — identical but every replica library is
  unloaded (`FreeLibrary`) after the run. **H1 unload discriminator.**
- `sampler_owned` — every native call routed to one long-lived owner thread
  holding one replica, serialized; library unloaded on the owner after join.
  **Owned-worker mitigation (fix arm).**

The Python parent (`run_root_cause.py`) launches children sequentially, writes
an exclusive durable pre-launch marker before each, never relaunches an
existing record or orphan marker (failures and interruptions are results),
and records the Windows return code (raw/signed/unsigned/hex), timeout state,
stdout/stderr, and the child's atomic heartbeat sequence (`process/start`,
`load`, `initialization`, `sampling`, `drop`, `result_write`,
`process/complete`). Four sampler threads/chains per sampler child.

## Frozen matrix and seeds

Fresh diagnostic seeds, base `50500000`, exact-word-verified unused in the
repository before freezing; outside all WP35/WP36 evidence ranges and all
prior diagnostic ranges. Order is arm-block then ascending seed.

| arm | model | seeds | children |
|---|---|---|---:|
| `sampler_concurrent` (baseline) | sblrc (no-threads) | `50500001..=50500060` | 60 |
| `sampler_concurrent_unload` (H1) | sblrc (no-threads) | `50500201..=50500260` | 60 |
| `sampler_owned` (fix) | sblrc (no-threads) | `50500401..=50500520` | 120 |
| `sampler_concurrent` (H4 threads) | sblrc (STAN_THREADS) | `50500801..=50500830` | 30 |
| `sampler_concurrent` (H4 no-threads control) | sblrc (no-threads) | `50500901..=50500930` | 30 |

Each sampler child: 4 replicas (owned arm reports 1 effective), 4 chains, 4
sampler threads, warmup 100, retained 100 (`rounds`=warmup,
`calls_per_thread`=retained in the CLI). Timeout 90 s per child. Total 300
children, strictly sequential, at most 4 threads per process. The fix arm
(120) is 2x the baseline (60) as the decision rule requires. Counts were set
after harness calibration on separate non-evidence seeds (`40060000`–`40081999`)
that are not part of the evidence matrix and are not reused here.

## Predictions and decision rule

- P-H1a/P-H1b (library unload is the cause): `sampler_concurrent_unload`
  produces strictly more `0xC0000374` exits than `sampler_concurrent`. H1's
  unload mechanism is **supported** only if the resident baseline reproduces
  >=1 fault, the unload arm reproduces strictly more, AND the drop-order log
  localizes the fault to `drop`/`library_drop`.
- P-fix (owned worker mitigates): `sampler_owned` produces zero `0xC0000374`
  exits over >=2x the baseline child count.
- P-H2: the static boundary audit finds a pointer allocated on one side and
  freed on the other. (Committed as `artifacts/h2-boundary-audit.md`.)
- P-H3: the drop-order audit finds a double-free / use-after-free path.
  (Committed as `artifacts/h3-drop-order-audit.md`.)
- P-H4: the `STAN_THREADS` arm's fault count/signature differs from the
  no-threads control, and the symbol analysis shows the threads build adds the
  thread-local autodiff stack emutls destructor absent from the faulting
  no-threads build. (`artifacts/h4-build-symbols.md`.)

A hypothesis is **SUPPORTED** only if its baseline arm reproduces the fault at
least once AND its fix/discriminator arm behaves as predicted over at least 2x
the baseline's child count AND the mechanism is shown in the drop-order log or
the committed audit. If the baseline does not reproduce in this harness, the
empirical arms are reported as a non-reproduction and no hypothesis is declared
supported on empirical grounds; the static/build audits still stand as
decisive refutations or narrowings where they apply.

If H1's unload mechanism holds, implement never-unload / join-first in
`integrations/bridgestan` and measure sampling cost WITHOUT the one-owned-worker
serialization (4 replicas, 4 threads) on arK and sblrc vs the mitigated path.

## Rules

- Run the fixed order; report every planned child. Never run seed 90101/2/3.
- Do not tune, substitute inputs, or rerun a child after observing it.
- Durations are contended on a shared 16-core machine and are descriptive
  only; return codes, heartbeat stages and fault counts are the evidence.
- If the fault does not reproduce, say so and do not invent a cause.
