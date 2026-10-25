# WP50D: confirmatory stress gate for static-runtime BridgeStan DLLs without the owned worker

This study is a process and engineering diagnostic, not posterior evidence.
It follows WP50C (`../bridgestan_windows_root_cause_v3`), whose Phase B
verdict needed a post-hoc correction to the crash-event correlation after
Windows reused a PID. The purpose here is a verdict with **no post-hoc
analysis step**. Everything below is frozen in `protocol.json` and
implemented in `run_gate.py` (with unit tests in `test_run_gate.py`) before
any evidence child runs. The script runs exactly once. Failures are results,
and nothing is rerun. Seeds 90101–90103 are forbidden.

## Configuration (the WP50B/WP50C reproducing cell)

- **Model and shape.** sblrc with 4 requested replicas, 4 chains and 4
  threads, 1000 warmup and 1000 draws. One child runs at a time.
- **Launch.** PowerShell `-Command "& '<exe>' ...; exit $LASTEXITCODE"` under
  the registry Machine;User PATH. This is the WinLibs runtime on PATH, the
  configuration that faulted before.
- **Code path.** This worktree's HEAD sampler and BridgeStan integration
  (`child/`, built by `build_child.py`).
- **The target, for the static arm and the primary control.** It is the
  WP50C Phase C `unserialised` target, unchanged: 4 independently loaded
  copies of the model DLL, each behind its own mutex, with free-replica
  dispatch. The libraries stay resident, and there is no owned worker and no
  process-global lock. This is the dispatch that the opt-in integration change
  would ship; the change itself is prepared after the gate. No library code
  changes before or during the gate.
- **Launch directories.** Each arm has its own exe-only launch directory
  holding a byte-identical copy of the child exe. The Event 1000 application
  path therefore names the arm.

## Arms (interleaved single-arm blocks of 10, 1,600 children)

- **`static_unserialised`.** The WP50C Phase A static-runtime sblrc DLL plus
  the private `tbb.dll`; 1,000 children; seeds 50801001–50802000. This is the
  gate arm.
- **`dynamic_unserialised`.** The old dynamic sblrc DLL (WP50) plus the stock
  `tbb.dll`, on the same unserialised target; 300 children; seeds
  50803001–50803300. This is the **primary positive control**: the same
  configuration faulted 2/120 in WP50C Phase B.
- **`dynamic_owned`.** The old dynamic DLLs with HEAD's owned-worker
  `ReplicatedStanTarget`; 300 children; seeds 50804001–50804300.
  - This is the control exactly as the coordinator worded it.
  - **Disclosed before evidence:** the owned worker suppressed the fault in
    540/540 dynamic children (`bridgestan_owned_worker_v1`), so this arm is
    not expected to reproduce. Gating on it alone would very likely give
    "inconclusive" by construction.
  - The primary rule therefore uses `dynamic_unserialised`, which is the
    configuration under test with only the DLLs changed. The rule with
    `dynamic_owned` as the control is computed and reported too, as the
    literal reading. Both readings are frozen now.

**Ordering.** The j-th of an arm's n blocks gets the key (j + 0.5) / n.
Blocks run in ascending key order, with ties broken in arm order. Every
quarter of the run therefore holds about a quarter of each arm, so all arms
see the same machine conditions. Other agents share the machine, so wall
times are contended.

**Seeds.** An exact-word `git grep -wE "5080[0-4][0-9]{3}"` over the
worktree and the main checkout found no hits.

## Module recording (proof that static never maps a runtime DLL)

Every child records the full path and size of each of these modules if it is
mapped: `libwinpthread-1.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll` and
`tbb.dll`. It records them twice: after load (the `load/after` heartbeat and
the raw output) and after the target is dropped (`drop/after`).

- **Static expectation:** none of the three runtime DLLs is mapped, and
  `tbb.dll` is the private one.
- **Dynamic expectation:** all three come from the WinLibs bin, and `tbb.dll`
  is the stock one.

A pre-launch probe that does no sampling checks this for each arm
(`artifacts/manipulation-check.json`).

## Crash-event correlation (frozen; this is the rule that was missing)

An Application Error Event 1000 is attributed to a child iff all of these
hold:

- **(a) Path.** The event's application path equals that child's arm exe
  path.
- **(b) PID.** The event PID, read as decimal, equals the child's PID from
  its heartbeats.
- **(c) Time.** The event time lies within the child's lifetime: from 1 s
  before the launcher started to 5 s after it returned.

Each event goes to at most one child. Events on an arm exe path that match no
child, or more than one, are reported as unattributed:

- an unattributed event on the **static** exe path counts as a **static
  fault** (conservative);
- unattributed control-path events never count as a control reproduction.

## Classification

**Fault.** Any of:

- a launcher timeout (300 s);
- a nonzero launcher return code;
- missing or non-ok raw output;
- a heartbeat sequence different from the expected 12;
- an attributed Event 1000. Hidden exit-0 crashes count.

**Heap corruption.** 0xC0000374 as the return code, or as the attributed
event's exception code.

## Decision rule

- **Supported** iff all of these hold:
  - `static_unserialised` is 0/1,000, event-inclusive;
  - `dynamic_unserialised` has at least 1 fault;
  - there are 0 static manipulation failures;
  - all 1,600 records are present.
- **Inconclusive (control did not reproduce)** if static is 0/1,000 and the
  primary control is 0/300.
- **Not supported** if static has at least 1 fault.

Reported either way:

- the exact one-sided (control > static) and two-sided Fisher p for each
  control against static;
- the one-sided 95% Clopper-Pearson upper bound on the static fault rate,
  which is 0.299% at 0/1,000.

## Power

At the WP50C dynamic-unserialised rate of 1.67%, P(primary control ≥ 1 in
300) = 0.994. At 1% it is 0.951; at 0.5% it is 0.778.

One-sided Fisher p for k control faults out of 300 against static 0/1,000:

- k = 1: 0.231
- k = 2: 0.053
- k = 3: 0.012
- k = 5: 0.0006

## After the gate (not evidence)

Prepare, but do not merge:

- an opt-in integration change: a load-time PE-import check that the model
  DLL and the preloaded tbb import no mingw runtime DLL. The owned worker is
  skipped only when that check passes and the option is set. It comes with
  unit tests and `cargo test`;
- a draft CHANGELOG entry.

## Pre-evidence state (at this commit)

- **Build.** The child is built (`artifacts/build-manifest.json`, exe sha256
  `d3d7fe34…`, library diff against HEAD empty), and its unit tests pass.
- **Manipulation probe.** It passed for all three arms
  (`artifacts/manipulation-check.json`).
- **Static DLL location.** The static DLLs are the WP50C Phase A products at
  `../bridgestan_windows_root_cause_v3/build/static/`. That directory is
  gitignored and is hash-pinned in `protocol.json`.
- **No evidence yet.** No gate child has run.
