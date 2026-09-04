# Final owned-one qualification protocol

Status at freeze: preregistered append-only engineering diagnostic. This file
extends, but does not rewrite, `PREREGISTRATION.md`, `protocol.json`, or
`ERRATUM.md`. The historical 992xxx/993xxx children and every artifact from
commit `14b1791` are immutable and must not be launched or rewritten.

Protocol parent: `a0008e2`. The final implementation and harness must be
committed after this protocol and before any child below is launched.

## Intervention being qualified

On Windows, every BridgeStan target retains one dedicated owner OS thread and
one effective replica. In addition, every native runtime operation in the
process is serialized by one process-global mutex across all target instances:
library/symbol setup, model construction, metadata/names, density/gradient
evaluation, BridgeStan error-message deallocation, and model destruction.
Callers never enter model code. Target drop sends shutdown and joins the owner
through model destruction and native TLS teardown.

Non-Windows behavior is not qualified by these children. Replica 0 and a
single-replica target must continue loading the caller's original model path so
`$ORIGIN`/`@loader_path` dependencies retain their prior meaning; only replicas
1 through n-1 may use private copies.

## Frozen assets

Read-only model directory:
`C:\dev\owalnuts-wt\posteriordb-v6\STUDIES\posteriordb_bench_v6\models`.

| shape | model | model SHA-256 | data | data SHA-256 |
|---|---|---|---|---|
| sblrc | `sblrc__blr_model.so` | `b77acc367c40b3afbb51f239e87fe896c1e7631643352361734b0dbacb0c50f1` | `sblrc__blr.data.json` | `2227de01d39e50560dd8341a84ed176a2a081cc8c8a841261dd4d6c38b47dc9c` |
| diamonds | `diamonds__diamonds_model.so` | `49cb5dfd1963bbb78ce157db36bd6442fe8549bdc4ca0cb4f7cc09b447319ccf` | `diamonds__diamonds.data.json` | `b8ff4fbdb0f7501b961f795d1d5cf27831a0dba909ff6582b3e57996ef3dbd3e` |
| mesquite | `mesquite__logmesquite_logvash_model.so` | `15221433ff586e954e9066eb8b19c3ac9367ea2f322ef24ed4a61b7018bfcc18` | `mesquite__logmesquite_logvash.data.json` | `b0133a4fd9fbb447514616395878c3bf33d3d693927e10e16e848fd1e9160d97` |

The build manifest freezes the final child binary SHA-256 and source commit
before execution. Any asset or binary mismatch aborts before the first child.

## Fresh matrix

Exact-word repository search before this freeze found none of these values used
as seeds. They are diagnostic-only and outside WP35/WP36 evidence ranges.

### Ordinary owned-one sampling: 540 children

Each child requests four replicas, must report one effective replica, and runs
four chains on four sampler threads with four warmup plus four retained
transitions per chain. It performs the same complete run twice, sequentially,
using fresh target instances but identical starts/configuration. The two runs
must match exactly on sample fingerprint, target-call count,
recoverable-failure count, algorithm revision, observed sample count,
diagnostic checksum, finite flag, dimension, names, compiled capability,
effective execution, requested/effective replicas, and every frozen setting.
Both targets are explicitly dropped before process completion.

| shape | seeds | children |
|---|---:|---:|
| sblrc | `4940001..=4940180` | 180 |
| diamonds | `4940201..=4940380` | 180 |
| mesquite | `4940401..=4940580` | 180 |

### Concurrent multi-target instances: 180 children

Each child creates four independent `ReplicatedStanTarget` instances from four
simultaneous caller threads after a barrier. Each instance requests four
replicas and must report one effective replica. The same 16 deterministic
positions derived without floating-point randomness from the registered seed
are evaluated by every instance. All four instances must match exactly on
value/gradient fingerprint, calls, recoverable failures, dimension, names,
compiled capability, effective `Threading::Serialised`,
`Execution::OwnedSerialised`, requested/effective replicas, and settings.
Expected calls are 16 per instance and 64 total. A second barrier aligns
teardown; every caller exits and every owner joins before the child publishes
completion.

| shape | seeds | children |
|---|---:|---:|
| sblrc | `4940601..=4940660` | 60 |
| diamonds | `4940701..=4940760` | 60 |
| mesquite | `4940801..=4940860` | 60 |

Total final matrix: exactly 720 one-shot children, all using four
caller/sampler threads. Execution order is ordinary sblrc, diamonds, mesquite,
then concurrent sblrc, diamonds, mesquite, ascending seed within each block.
The parent launches exclusively and sequentially. Timeout is 90 seconds per
child. No retry, resume, substitution, or rerun is permitted; an interruption
leaves the qualification failed/incomplete.

## Durable records and Windows events

All new material is written under `artifacts/final-qualification/`: immutable
launch markers, atomic ordered heartbeats, raw child output, stdout/stderr,
parent process records, a pre-run binary/asset manifest, captured Windows
Application Error 1000/Windows Error Reporting 1001 events, correlations, and
derived summaries. Existing artifact trees are never opened for replacement.

Event capture starts before the first launch and ends after a 20-second settle.
An Application Error Event 1000 correlated by exact executable path, child PID,
and application-start FILETIME is a fault even if the process returned zero.
Event capture unavailability or malformed correlation input fails the gate.

## Acceptance

The final implementation passes only if all of the following hold:

1. Exactly 540 ordinary and 180 concurrent records exist, with no duplicate,
   missing, or out-of-matrix launch.
2. Every child returns zero before 90 seconds, publishes complete ordered
   heartbeats and a complete schema-valid raw result, and has no correlated
   Event 1000 or other captured event anomaly.
3. Every target in every child reports requested replicas 4, effective
   replicas 1, effective serialized execution, four caller/sampler threads,
   and the registered model, seed, dimensions, settings, and algorithm
   revision.
4. Every ordinary child's two runs match every registered parity invariant and
   counter exactly. Every concurrent child's four target instances match every
   registered value/gradient, metadata, counter, and setting exactly, with
   calls `[16,16,16,16]`.
5. Validation before launch includes root and integration GNU debug/release
   tests, strict Clippy, rustdoc, Python tests, all research-pool regressions,
   and real-model BridgeStan tests against the explicit WP35 directory. A
   skipped real-model test is not acceptance.
6. The 992xxx/993xxx launch/process/raw/heartbeat/stdout/stderr/event and input
   manifests retain the exact Git tree/blob identities recorded at `14b1791`.

For zero faults, report exact one-sided 95% binomial upper bounds:
ordinary `1 - 0.05^(1/540) = 0.005532292551836959` (0.553229%);
concurrent `1 - 0.05^(1/180) = 0.01650522819566269` (1.650523%);
combined `1 - 0.05^(1/720) = 0.0041520953856636345` (0.415210%).
These are finite-matrix process-fault bounds, not a proof of general native
safety.

After the first child launches, source, protocol, harness, and analysis code
are frozen. Failures remain results. Only reporting text, checksums, and derived
artifacts may be committed afterward. No merge, push, tag, or publication is
authorized.
