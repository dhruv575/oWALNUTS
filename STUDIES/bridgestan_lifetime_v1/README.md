# BridgeStan native-lifetime diagnostic v1

Status: complete; **acceptance failed and release remains blocked**.

This is a Windows process-lifecycle diagnostic, not posterior evidence. The
engineering protocol was committed before implementation in
`PREREGISTRATION.md`; the exact 180-child-per-mode machine protocol is
`protocol.json`. WP35/WP36 evidence seeds and artifacts are out of scope and
must not be rerun or modified.

The child performs a short four-chain, four-thread sample through four
BridgeStan replicas, writes a deterministic retained-draw fingerprint, then
explicitly drops the target between durable heartbeats. The parent runs the
historical baseline before the fixed executable, creates immutable pre-launch
markers, never reruns an attempted child, records return-code forms and
heartbeats, and captures relevant Windows Application events.

## Verdict

The fixed binary did not meet the preregistered zero-fault acceptance rule.
All 360 planned records are present and no child was rerun.

| mode | successful | faults | timeouts | missing raw | incomplete heartbeat |
|---|---:|---:|---:|---:|---:|
| historical baseline | 165/180 | 15 | 2 | 5 | 15 |
| fixed | 172/180 | 8 | 0 | 7 | 7 |

Baseline faults were 11/100 sblrc, 4/40 diamonds and 0/40 mesquite. Fixed
faults were 3/100 sblrc, 4/40 diamonds and 1/40 mesquite. All eight fixed
faults returned `0xC0000374` (`STATUS_HEAP_CORRUPTION`). Seven ended after
`sampling/before` and before `sampling/after`; that interval includes
run-local Rayon work plus the new joined worker-exit/TLS-destructor barrier.
The eighth wrote its raw output and every heartbeat through
`process/complete`, then faulted during process exit.

The baseline had thirteen `0xC0000374` exits and two 60-second timeouts. Ten
baseline faults ended at `drop/before` and five at `sampling/before`.
The change in last heartbeat is consistent with worker teardown becoming
synchronous inside the sampling helper, but does not prove the underlying
cause. Windows events independently recorded all eight fixed heap-corruption
events in `ntdll.dll`; secondary access-violation events were also present.

Deterministic parity was exact for every available pair: 0 mismatches among
168 baseline/fixed retained-draw fingerprints. Twelve pairs were not
comparable because at least one raw output was unavailable, so the complete
baseline/fixed comparison is inconclusive.

Because fixed mode was not fault-free, no zero-failure upper bound is claimed.
The preregistered 1.65% one-sided 95% bound would apply only to 0/180, not the
observed 8/180. The result supports neither a complete mitigation nor a release.
Root cause remains not established.

## Implemented lifetime behavior

- Every run-local multi-chain Rayon driver, including block-dense, dense,
  structured refresh, budgeted, plain and rescued paths, uses a scoped pool
  whose OS workers are joined before helper return.
- Windows model and preload libraries are held in a canonical-path
  process-lifetime registry. Model handles still destruct normally and before
  their library fields. Non-Windows unload behavior is unchanged.
- Windows replica copies use a leased, process-private SHA-256 cache. Repeated
  loads of the same model/replica index reuse file paths and module handles.
  A later process cleans an unlocked directory after a one-hour grace period.

The Windows tradeoff is intentional process-lifetime module memory and source
file locks. Memory is bounded for repeated identical loads, but grows with
distinct model contents and the maximum replica index loaded until process
exit. Original model/preload files and cache copies can remain locked while
mapped. No new unsafe FFI operation was introduced; existing `Library::new`
calls were centralized behind the platform wrapper.

## Validation

Passed with Rust `1.88.0-x86_64-pc-windows-gnu`:

- root format, strict Clippy, full debug and release all-target/all-feature
  tests, frozen kernel fingerprints, rustdoc with warnings denied, and release
  all-target build;
- BridgeStan format/check/strict Clippy with and without all features, release
  all-feature tests and rustdoc (the integration-local Eight Schools fixture
  was absent, so its model-dependent cases skipped; the stress matrix loaded
  all three frozen external models);
- autodiff integration format/Clippy/release tests;
- Python integration format and strict Clippy with and without default
  features;
- harness format/Clippy/debug and release tests, Python unit tests, and
  rustdoc.

The stress gate failed as described above and is the remaining release
blocker. Raw records, heartbeats, stdout/stderr, launch markers, Windows
events, binary/model identities, and machine-readable summaries are under
`artifacts/`. `python checksums.py verify` validates the frozen study tree.
