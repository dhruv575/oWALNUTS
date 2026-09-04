# BridgeStan native-lifetime mitigation: pre-execution protocol

Status: engineering protocol only. It is not posterior evidence. It must be
committed before implementation or diagnostic execution.

## Diagnosis and intervention

The working diagnosis is a Windows teardown race: run-local Rayon workers can
retain native TLS state while BridgeStan model/preload DLLs and copied replica
modules are dropped. A late native TLS destructor can then execute code or
touch state from an unloaded module. The prior silent post-result
`0xC0000374` failure is consistent with this interval but does not prove the
mechanism.

The intervention has two independent lifetime barriers:

1. every run-local parallel sampling driver uses scoped, joined workers, so
   helper return occurs only after worker OS-thread exit and TLS teardown;
2. on Windows, loaded model and preload libraries become process-lifetime
   residents while model objects retain normal deterministic destruction.
   Copied replica files remain present while mapped and stale process-private
   directories are cleaned only by later processes when no longer mapped.

Non-Windows unloading and the public numerical API remain unchanged. Task
ordering, RNG streams, transition counts, and draws must not change.

## Frozen diagnostic design

All seeds are diagnostic and outside WP35/WP36 evidence schedules. Never read,
modify, rerun, or regenerate WP35/WP36 seed records or artifacts. Child seeds
are allocated monotonically from `991000`; a pre-launch record makes each
child single-attempt, and a failed/interrupted child is a result, never rerun.

The harness is parent/child and uses existing compiled models read-only when
available. Each sample/drop child uses four chains, four Rayon threads, and
four BridgeStan replicas. It writes atomic heartbeats around load, sample,
result publication, model drop, and normal process exit; the parent records
the raw/signed/hex return code, timeout status, stdout, stderr, and available
Windows event-log matches.

The fixed matrix contains 180 fast children: 100 `sblrc`, 40 short
diamonds-shaped, and 40 short mesquite-shaped runs. This gives a 97.37%
chance of observing at least one failure if the historical independent-child
failure probability were 2%; zero failures gives a one-sided 95% binomial
upper bound of 1.65%. Warmup/draw counts are deliberately short and recorded
in the machine-readable manifest; this is a lifetime stress test, not a
posterior run.

Where a historical executable or a separately built baseline preserving
unscoped-worker/normal-Windows-unload behavior is safely available, run the
same frozen 180-child matrix against it before the fixed matrix. If that is
not feasible, use the archived `sblrc_process_stability_v1` result only as
historical context and label the baseline/fixed comparison inconclusive.
Never mutate archived baseline evidence.

## Acceptance

The mitigation passes this diagnostic only if:

- all 180 fixed children have zero native faults, timeouts, and missing or
  malformed outputs;
- every child reaches post-drop and process-complete heartbeats;
- fixed numerical fingerprints match the frozen baseline/reference
  fingerprints for identical model, seed, and configuration;
- unit tests demonstrate model-before-library destruction, Windows resident
  handle semantics, replica cleanup/reuse behavior, repeated load/drop, and
  scoped-pool TLS destruction before helper return; and
- format, Clippy, debug/release tests/builds, rustdoc, and applicable
  BridgeStan integration tests pass.

No absence of failures establishes root cause. Claims are limited to worker
joining, Windows module residency, observed deterministic parity, and the
measured finite stress bound.

## Artifacts

Commit implementation and harness before execution. Then retain a frozen
manifest, pre-launch ledger, per-child process records and heartbeats,
stdout/stderr, Windows-event captures (including explicit unavailability),
fingerprints, command/toolchain/model hashes, machine-readable summary,
README verdict, checksum manifest, and ledger stub. Artifacts are committed
after execution; checksums exclude only the checksum file itself. No
posterior evidence artifact is produced.
