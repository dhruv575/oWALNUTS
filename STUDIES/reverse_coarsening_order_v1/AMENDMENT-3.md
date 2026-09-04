# WP37B preregistration Amendment 3

Status: **final append-only clarification before implementation or evidence**.

This amendment controls any conflict with `PREREGISTRATION.md`,
`protocol.json`, `AMENDMENT-1.md`, or `AMENDMENT-2.md`. It changes no manifest
cell, arm, target, seed, timeout, sampler setting, or one-shot execution rule.
The frozen predecessor documents, hashed after LF newline normalization as
UTF-8 without a BOM, are:

| document | SHA-256 |
|---|---|
| `PREREGISTRATION.md` | `ba4a3a9e64c8757d021ec9886e24f537c4059e8deb24565f1bd90ba94d98234d` |
| `protocol.json` | `6dc9deaf1a3133c9e308a68bd6352f0a30cf61653ee7dad8da93dba59a4b9c81` |
| `AMENDMENT-1.md` | `83c0f92f4314449c52746ab44e5a9185b18b97359884b11c4556abb940a6a1ca` |
| `AMENDMENT-2.md` | `564e35b1424a738b6d424f05f84138f45d97176fd70287465e8a9f943f2e5162` |

No implementation, build, or evidence exists in this amendment.

## A3.1 Exact callback accounting and work gates

At source baseline `a630e04151842cf7a92131dcadd8e9412c675f5b`,
`WorkTotals::target_calls_total()` in `src/walnutpie.rs` is exactly the sum of
its `target_calls_initial`, `target_calls_forward`, and
`target_calls_reverse` fields. `Posterior::total_target_calls()` in
`src/sampler.rs` sums that same total over every chain and phase. Uniform-start
search evaluations are expressly outside this telemetry. The controlling Git
blobs are `3a3b372d317cc5c702cbe80f6445885d14c4a14f` for
`src/walnutpie.rs` and `e3c70f3e3ccd2a3e82bbc6400181d8bedd39467e` for
`src/sampler.rs`.

WP37B uses the following controlling names and checked `u64` equations:

```text
initial_state_or_cached_transition_calls = WorkTotals::target_calls_initial()
forward_calls                           = WorkTotals::target_calls_forward()
reverse_calls                           = WorkTotals::target_calls_reverse()

gated_kernel_calls =
    checked_add(initial_state_or_cached_transition_calls,
      checked_add(forward_calls, reverse_calls))

initialization_search_calls =
    target callbacks made by Init::Uniform while finding valid starts
    (zero for Init::Given)

all_callback_calls =
    checked_add(initialization_search_calls, gated_kernel_calls)
```

`initial_state_or_cached_transition_calls` counts kernel-phase initial
evaluations exactly as `WorkTotals` does. With initial-evaluation caching, a
transition may contribute zero to that component; such a zero is not moved
into `forward_calls`. The successful evaluation used to choose a uniform start
remains an `initialization_search_call`; it is not reclassified as a kernel
transition-initial call. Conversely, the kernel's later evaluation of that
start, if performed and counted by `WorkTotals`, belongs only to
`initial_state_or_cached_transition_calls`.

For each chain/phase, cell, target aggregate, and global aggregate, evidence
records the three kernel components and `gated_kernel_calls` as `u64`.
`initialization_search_calls` is recorded per chain and cell, before any phase,
and `all_callback_calls` is recorded at cell, target-aggregate, and global
levels; neither is assigned to warmup or retained. Evidence computes all sums
with checked addition and directly verifies each kernel partition against
`WorkTotals::target_calls_total()`. The checked sum over chains and phases must
also equal `Posterior::total_target_calls()`. A negative/noninteger imported
value, value outside `u64`, overflow, or disagreement fails the cell and study.

`all_callback_calls` is authenticated and reported for target-load accounting,
but it is not an efficiency gate. Every efficiency gate uses
`gated_kernel_calls`, and no field named only `total_calls` is permitted in a
gate or verdict. This section supersedes the ambiguous `total_calls`
definitions in the original preregistration and Amendments 1–2.

The controlling work gates are renamed **W1–W3**:

1. **W1, all 84 pair-phase comparisons:** candidate
   `gated_kernel_calls <=` incumbent `gated_kernel_calls`.
2. **W2, global:** over checked sums of all 84 pair-phase records, candidate
   `gated_kernel_calls <` incumbent `gated_kernel_calls`; incumbent summed
   `reverse_calls > 0`; and the reverse reduction passes the exact integer
   test
   `checked_mul(20, candidate_reverse_calls) <=
   checked_mul(19, incumbent_reverse_calls)`.
3. **W3, each target:** over checked sums across all six seeds and both phases,
   candidate `gated_kernel_calls <=` incumbent `gated_kernel_calls` and
   candidate `reverse_calls <=` incumbent `reverse_calls`. Warmup and retained
   target subtotals are mandatory reports, not additional gates.

Any overflow in either W2 multiplication fails W2; the analyzer must not use a
wider, wrapping, saturating, floating-point, or rearranged calculation to turn
that failure into a pass. With positive incumbent reverse work, the integer
inequality also implies strict reverse reduction. Candidate reverse work may
be zero. For a nonglobal comparison with zero incumbent reverse work,
candidate reverse work must be zero and a displayed ratio is `N/A`/pass as
specified by Amendment 2. Ratios are descriptive only; the integer inequality
is authoritative for the global 5% gate.

The identity criterion previously described as forward-call identity is
renamed **C2**: paired arms must have exact direct equality of `forward_calls`
at every chain/transition and at every checked aggregate. C2 is a comparison
criterion independent of W1–W3; it is not used to redefine
`gated_kernel_calls` or to omit transition-initial calls from the work gates.

## A3.2 Exhaustive target-specific static configuration

This section replaces Amendment 2's `target_kind`, `target_contract`,
`target_artifacts`, `posteriordb_commit`, `backend`,
`requested_backend_replicas`, `effective_backend_replicas`,
`stan_threads_enabled`, `global_bridge_serialization`, and
`reverse_schedule_generation_revision` fields. The remaining pair-common
fields and encodings in Amendment 2 continue unchanged.

The pair-common static-config and arm-config domain versions for implementation
are `3`; arm config embeds the version-3 pair-common hash.
`comparison_schema_version` is exactly `3`. Other Amendment 2 comparison
record versions remain unchanged. At the position occupied by the replaced
fields, each target record has the following exhaustive ordered fields:

| order | key | type |
|---:|---|---|
| 1 | `target_id` | string |
| 2 | `target_backend` | enum `TargetBackend` |
| 3 | `target_role` | enum `TargetRole` |
| 4 | `target_dimension` | `u64` |
| 5 | `target_contract` | enum `TargetContract` |
| 6 | `posterior_id` | option string |
| 7 | `model_id` | option string |
| 8 | `posteriordb_commit` | option string |
| 9 | `requested_backend_replicas` | `u64` |
| 10 | `effective_backend_replicas` | `u64` |
| 11 | `threading_mode` | enum `ThreadingMode` |
| 12 | `execution_mode` | enum `ExecutionMode` |
| 13 | `target_artifacts` | vector `TargetArtifactRecord` |
| 14 | `reverse_schedule_generation` | enum `ReverseScheduleGeneration` |
| 15 | `reverse_schedule_generation_revision` | string |

The exact enum tags are:

```text
TargetBackend: PureRust=0, BridgeStanOwned=1
TargetRole: HardPrimary=0, LocalizedStiffnessSafety=1, NullControl=2
TargetContract: DeterministicFiniteOrRecoverable=0
ThreadingMode: InProcessDirect=0, StanThreadsDisabled=1
ExecutionMode: InProcessDirect=0, OwnedSerialised=1
ReverseScheduleGeneration: RepeatedHalvingDoublingV1=0
```

Every target has
`TargetContract::DeterministicFiniteOrRecoverable`,
`ReverseScheduleGeneration::RepeatedHalvingDoublingV1`, and the exact revision
string `repeated-halving-doubling-v1`. No other contract or schedule value is
valid.

The seven target records are:

| target ID | role | dimension | backend | requested/effective replicas | threading / execution | posterior ID / model ID |
|---|---|---:|---|---:|---|---|
| `posteriordb_accel_gp` | `HardPrimary` | 66 | `BridgeStanOwned` | 4 / 1 | `StanThreadsDisabled` / `OwnedSerialised` | `mcycle_gp-accel_gp` / `accel_gp` |
| `posteriordb_gp_pois_regr` | `HardPrimary` | 13 | `BridgeStanOwned` | 4 / 1 | `StanThreadsDisabled` / `OwnedSerialised` | `gp_pois_regr-gp_pois_regr` / `gp_pois_regr` |
| `posteriordb_eight_schools_centered` | `HardPrimary` | 10 | `BridgeStanOwned` | 4 / 1 | `StanThreadsDisabled` / `OwnedSerialised` | `eight_schools-eight_schools_centered` / `eight_schools_centered` |
| `posteriordb_eight_schools_noncentered` | `HardPrimary` | 10 | `BridgeStanOwned` | 4 / 1 | `StanThreadsDisabled` / `OwnedSerialised` | `eight_schools-eight_schools_noncentered` / `eight_schools_noncentered` |
| `neal_funnel_10d` | `LocalizedStiffnessSafety` | 10 | `PureRust` | 0 / 0 | `InProcessDirect` / `InProcessDirect` | none / none |
| `gaussian_100d` | `NullControl` | 100 | `PureRust` | 0 / 0 | `InProcessDirect` / `InProcessDirect` | none / none |
| `state_space_sspd11_t1000` | `LocalizedStiffnessSafety` | 1006 | `PureRust` | 0 / 0 | `InProcessDirect` / `InProcessDirect` | none / none |

The remaining target-varying static fields have these exact values:

| target ID | warmup / retained | timeout seconds | initialization |
|---|---:|---:|---|
| `posteriordb_accel_gp` | 1000 / 1000 | 1800 | `Uniform`, radius 2, max attempts 100 |
| `posteriordb_gp_pois_regr` | 1000 / 1000 | 900 | `Uniform`, radius 2, max attempts 100 |
| `posteriordb_eight_schools_centered` | 1000 / 1000 | 600 | `Uniform`, radius 2, max attempts 100 |
| `posteriordb_eight_schools_noncentered` | 1000 / 1000 | 600 | `Uniform`, radius 2, max attempts 100 |
| `neal_funnel_10d` | 2000 / 20000 | 1800 | `Given`, four WP37A fixed starts |
| `gaussian_100d` | 1000 / 1000 | 300 | `Uniform`, radius 2, max attempts 100 |
| `state_space_sspd11_t1000` | 500 / 2000 | 900 | `Given`, four canonical fixed starts |

Every target has four chains, four sampler threads, 30 seconds termination
grace, and the common kernel/adaptation values frozen in Amendment 1 A7.

The four BridgeStan records use posteriordb commit
`28f8d3d6e975315f42aa274a8399f21e07a43b30`. The three PureRust records encode
`posteriordb_commit=none`; BridgeStan records encode it as `some`. PureRust
requested/effective replicas are exactly `0/0`. BridgeStan requested/effective
replicas are exactly `4/1`; process-global native calls are owned and
serialized, and `STAN_THREADS` is disabled.

The frozen study roles are exactly:

- hard-primary: `posteriordb_accel_gp`, `posteriordb_gp_pois_regr`,
  `posteriordb_eight_schools_centered`, and
  `posteriordb_eight_schools_noncentered`;
- localized-stiffness safety: `neal_funnel_10d` and
  `state_space_sspd11_t1000`;
- null control: `gaussian_100d`.

These roles are labels fixed before evidence. They do not alter gates, weights,
manifest membership, aggregation, or result selection.

### Target artifact records

A `TargetArtifactRecord` is encoded in this exact order:

1. `artifact_role`: enum `TargetArtifactRole` (`u8`);
2. `role_index`: `u64`;
3. `identity`: UTF-8 string;
4. `byte_length`: `u64`;
5. `sha256`: 32 raw bytes;
6. `git_commit`: option UTF-8 string;
7. `git_tree`: option UTF-8 string;
8. `git_blob`: option UTF-8 string.

Its unique key is `(artifact_role: u8, role_index: u64)`. Each target's vector
is sorted by that key, starts every used role at index zero, and uses
contiguous indices. Duplicate keys, an unlisted role, a missing required
record, or an extra record fail static configuration.

`TargetArtifactRole` tags are:

```text
PosteriordbRepositoryTree=0
Wp35Protocol=1
Wp35RunnerSource=2
StanModelSource=3
PosteriordbDataJson=4
CompiledModelLibrary=5
BridgeStanRuntime=6
NativeDependency=7
Wp37aPureTargetSource=8
SspdCanonicalTargetSource=9
SspdCanonicalHarnessSource=10
SspdCanonicalProtocol=11
SspdFixedStarts=12
SspdParityOracle=13
SspdTargetFixture=14
```

Required artifact vectors are exhaustive:

- each BridgeStan target has exactly one record at index zero for roles 0–6,
  plus one role-7 record for every loaded native dependency. The complete
  role-7 count and ordered identities are committed before evidence and may be
  zero only if build provenance proves no separate native dependency is
  loaded. The repository-tree record pins the posteriordb commit and tree; the
  model, data, compiled library, runtime, and dependency records each pin exact
  identity, byte length, and SHA-256. The WP35 records pin
  `STUDIES/posteriordb_bench_v6/protocol.json` and
  `STUDIES/posteriordb_bench_v6/run_posteriordb.py`.
- `neal_funnel_10d` and `gaussian_100d` each have exactly one role-8 record,
  index zero, for `STUDIES/delta2_sidechecks_v1/src/main.rs`, pinned by
  Amendment 2 A2.4 to commit
  `e91458dca1aa7944b07c65514ad2313b4a60cd4d`, Git blob
  `0385e3fbcd2caad2c92c81a02b0ec148f02d2543`, byte length `36666`, and
  SHA-256
  `ba6629bd6ceb0d1d0d7b6016de68c21c2ef8861c294aed8c24d50aff52f4ec49`.
- `state_space_sspd11_t1000` has exactly one index-zero record for each role
  9–14, corresponding in order to:
  `STUDIES/sspd11_confirmation_v1/primary/src/canonical.rs`,
  `STUDIES/sspd11_confirmation_v1/primary/src/main.rs`,
  `STUDIES/sspd11_confirmation_v1/primary/protocol.json`,
  `STUDIES/sspd11_confirmation_v1/primary/starts/sspd-11.json`,
  `STUDIES/sspd11_confirmation_v1/primary/fixtures/polyscope_parity.json`, and
  `STUDIES/sspd11_confirmation_v1/primary/fixtures/sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json`.
  Their exact SHA-256 values remain those listed in Amendment 1 A7; byte
  lengths and Git identities are committed before evidence.

The reference in Amendment 2 to “Amendment 1 A7 and A9 below” is corrected to
“Amendment 1 A7 and Amendment 3 A3.2.” There is no A9, and no requirement may
be inferred from that nonexistent cross-reference.

## A3.3 Fatal locations and public errors

Fatal and abort records use domain
`owalnuts.reverse_coarsening_order_v1.fatal_errors`, version 3. They remain
outside semantic identity and its hash, but are included in raw-result
authentication, integrity hashes, completeness checks, and reports. Any fatal
or abort record fails the cell and qualification, even if both arms match.

Each fatal record contains, in order:

1. a `FatalLocation` tagged union;
2. an `ErrorKind` tag;
3. a `SourceStage` tag;
4. the exact UTF-8 message.

`FatalLocation` is exactly:

```text
InitializationSearch=0 {
  attempt: u64
}
TransitionInitial=1 {
  chain: u64,
  transition: u64
}
Forward=2 {
  chain: u64,
  transition: u64,
  leaf_attempt: u64,
  level: u64,
  evaluation_index: u64
}
Reverse=3 {
  chain: u64,
  transition: u64,
  leaf_attempt: u64,
  reverse_evaluation_index: u64,
  coarse_level: u64,
  microsteps: u64,
  step_bits: f64::to_bits as u64 LE
}
ControlAbort=4 {
  chain: option u64,
  transition: option u64,
  kind: AbortKind
}
```

`InitializationSearch.attempt` is the global zero-based ordinal in the
canonical initializer-attempt vector, whose records already carry chain and
per-chain attempt indices. `transition` is the global zero-based transition
index. The `Reverse` fields are the complete reverse key from Amendment 2 in
the same order and encoding.

Exact tags are:

```text
ErrorKind:
  MalformedOrNonfiniteEvaluation=0
  FatalTargetError=1
  TargetPanic=2
  ControlAbort=3
  BudgetAbort=4
  ObserverAbort=5

SourceStage:
  InitializationSearch=0
  TransitionInitial=1
  Forward=2
  Reverse=3
  Control=4

AbortKind:
  Control=0
  Budget=1
  Observer=2
```

The `SourceStage` must correspond to the `FatalLocation` variant.
`ControlAbort.kind` must correspond to `ErrorKind::ControlAbort`,
`BudgetAbort`, or `ObserverAbort`. A malformed/nonfinite evaluation, fatal
target error, or target panic must use one of the four target-call location
variants, never `ControlAbort`.

A public error record uses domain
`owalnuts.reverse_coarsening_order_v1.public_errors`, version 3. Its exact
fields are fatal-record index `u64`, `ErrorKind`, `SourceStage`, and exact UTF-8
message. It must agree field-for-field with the referenced fatal record.
Public-error records are authenticated and reported; they are outside semantic
identity and cannot make a fatal/abort cell eligible.

Timeout, process-tree termination failure, malformed process output, and
authentication failure remain process-invalid outcomes under Amendment 1 A4,
not fabricated target-call locations. They also fail qualification and are
authenticated/reported by the process record.

## A3.4 Final amendment and decision scope

No further protocol amendment is expected. Implementation may begin only from
the complete controlling chain through this Amendment 3, with static expected
configuration records, hashes, and conformance fixtures committed before
evidence. If a contradiction is discovered before evidence, execution must
stop rather than silently reinterpret this protocol.

The only possible positive result remains
`QUALIFY_COARSEST_FIRST_OPT_IN_FOR_FINITE_OR_RECOVERABLE_TARGETS`. It can
qualify only a later explicit Rust opt-in on `KernelTuning` and high-level
`Tuning` for a documented deterministic finite-or-recoverable target.

Every walnutpie, high-level sampler, and Python default remains
`FinestToCoarsest`. Generic `Target` behavior, replay, fingerprints, and
algorithm revision remain unchanged. This amendment contains and authorizes no
implementation or default change.
