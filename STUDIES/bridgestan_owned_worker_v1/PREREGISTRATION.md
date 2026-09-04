# BridgeStan Windows owned-worker diagnostic: preregistration

Status: engineering/process diagnostic only, frozen before implementation or
execution. This study is append-only and does not alter or rerun
`STUDIES/bridgestan_lifetime_v1`. WP35/WP36 seeds and artifacts remain
forbidden.

## Diagnosis and intervention

The first scoped-worker/resident-DLL mitigation remains a failed result:
8/180 fixed children ended in native heap corruption. Seven failed inside the
sampling interval after the Rayon workers began and before their joined
teardown returned. The new working diagnosis is that Windows/mingw native
model execution or TLS teardown is unsafe when model code is entered by
short-lived caller/Rayon threads, even when modules remain resident. This
pattern is consistent with the diagnosis but does not prove it.

On Windows, the intervention moves every BridgeStan operation to one dedicated
owned OS thread per target: library/symbol loading, model construction,
metadata/name reads, gradients and error freeing, model destruction, and
shutdown. Caller and Rayon threads use a bounded request channel and never
enter model code. Shutdown destroys the model on its owner thread, then joins
that thread so native TLS teardown finishes before close/drop returns.
`ReplicatedStanTarget::load(..., requested)` records the request but uses one
serialized owned worker. Multiple owned workers are out of scope. Non-Windows
direct execution and unloading remain unchanged.

Model construction is serialized by content-consistent module identity.
Windows loads a real-SHA-256 cached model copy so the source model need not
remain locked. Dimensions and parameter names are validated as one owner-side
snapshot. Process-resident handles outlive owner TLS teardown. Channel
disconnects and worker panics are fatal target errors; drop must join without
panicking.

## Frozen matrix and seeds

Every child uses four sampler chains and four sampler threads, four warmup and
four retained transitions per chain, and one effective owned BridgeStan
worker in the intervention arm. Seeds are diagnostic only:

- paired schedule: 180 seeds `992001..=992180`, partitioned as 60 sblrc,
  60 diamonds, and 60 mesquite;
- comparator: all 180 paired seeds against the committed first mitigation
  (`9edcbac`);
- owned-worker paired: the same 180 seeds for exact fingerprint comparison;
- owned-worker extension: 360 fresh seeds `993001..=993360`, partitioned as
  120 sblrc, 120 diamonds, and 120 mesquite.

Thus the comparator has exactly 180 children and owned-worker mode exactly 540
children. A durable exclusive pre-launch marker makes each child a single
attempt. Existing markers or records prevent launch; failures and
interruptions are results and are never rerun.

The parent records raw/signed/unsigned/hex process codes, timeout state,
stdout/stderr, atomic heartbeats around load/sample/result/drop/close, raw
fingerprints, target counters, effective/requested replicas, and descriptive
duration. After each arm it captures Windows Application Error Event 1000 and
Windows Error Reporting Event 1001. Event 1000 is correlated by executable
path, faulting PID, and application start time; a correlated event makes an
otherwise nominal child a fault.

## Acceptance

Owned-worker mode passes only if all 540 children have:

- zero nonzero exits, timeouts, missing/malformed outputs, and incomplete
  heartbeat sequences;
- zero correlated Windows Application Error Event 1000 records; and
- exact retained-draw fingerprints for every successful paired comparator
  cell.

Zero failures in 540 gives a one-sided 95% binomial upper bound
`1 - 0.05^(1/540) = 0.552%`. Passing is limited to these three models, short
4/4 runs, this BridgeStan build, and this Windows host; it does not establish
the historical root cause. Any native fault leaves release blocked.
Performance overhead is descriptive and cannot alter acceptance.

## Required tests and artifacts

Before stress, commit fake-backend tests proving owner-thread affinity for all
native operations; model destruction before owner TLS destruction and close
return; safe serialization across callers; counter/error transfer; joined
load failure; and no worker leakage after repeated load/drop. Add real-model
parity where assets exist, preserve sampler fingerprints/work/RNG, and scope
the two remaining research Rayon pools.

Commit protocol, runtime implementation, and harness separately before child
execution. Afterwards commit the immutable manifest, binary/model hashes,
launches, process records, heartbeats, stdout/stderr, correlated Windows
events, analysis, README verdict, checksum manifest, and release-ledger stub.
