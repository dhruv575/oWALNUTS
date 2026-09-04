# WP37B preregistration Amendment 2

Status: **frozen final-review clarification before implementation or evidence**.

This is an append-only amendment to `PREREGISTRATION.md`, `protocol.json`, and
`AMENDMENT-1.md`. It changes no manifest cell, target, seed, arm, timeout,
sampler setting, or execution rule. Where this amendment conflicts with an
earlier document, this amendment controls. The frozen predecessor documents,
hashed after LF newline normalization as UTF-8 without a BOM, are:

| document | SHA-256 |
|---|---|
| `PREREGISTRATION.md` | `ba4a3a9e64c8757d021ec9886e24f537c4059e8deb24565f1bd90ba94d98234d` |
| `protocol.json` | `6dc9deaf1a3133c9e308a68bd6352f0a30cf61653ee7dad8da93dba59a4b9c81` |
| `AMENDMENT-1.md` | `83c0f92f4314449c52746ab44e5a9185b18b97359884b11c4556abb940a6a1ca` |

No implementation, build, or evidence exists in this amendment.

## A2.1 Authoritative work counts and zero handling

Raw unsigned integer counters are authoritative for every efficiency decision.
Hashes and ratios are summaries and cannot override a raw-count failure.
For every arm, cell, phase, target aggregate, and global aggregate:

```text
total_calls = checked_add(forward_calls, reverse_calls)
```

The stored `total_calls` must equal that checked sum. A negative imported
value, a value outside `u64`, addition or summation overflow, a noninteger
count, or disagreement with the checked sum fails the affected cell and the
study. Initialization calls remain separately reported and included in the
cell total as frozen by Amendment 1; the warmup/retained phase records contain
only their phase calls.

The controlling efficiency gates are:

1. **E1, all 84 pair-phase comparisons:** candidate `total_calls <=`
   incumbent `total_calls`. Forward-call direct equality is required by the
   semantic gates, so this also implies candidate `reverse_calls <=` incumbent
   `reverse_calls`; raw reverse counts are nevertheless reported.
2. **E2, global:** checked sums over all 84 pair-phase records must satisfy
   candidate reverse calls `<` incumbent reverse calls and candidate total
   calls `<` incumbent total calls. The incumbent summed reverse-call count
   must be greater than zero. Candidate summed reverse calls may be zero.
   Candidate/incumbent reverse calls must be `<= 0.95`.
3. **E3, each target:** candidate reverse and total calls, checked-summed
   across all six seeds and both phases, must not exceed incumbent reverse and
   total calls. Warmup and retained target subtotals are reported but are not
   additional gates.

A ratio is computed only when its incumbent denominator is greater than zero.
If an incumbent reverse-call denominator is zero, the candidate reverse-call
count must also be zero; that ratio is recorded exactly as `N/A` with a passing
zero/zero raw-count check. A positive candidate count against a zero incumbent
count fails. A zero candidate numerator against a positive incumbent
denominator is ratio `0.0` and may pass.

All ratio arithmetic is derived from validated `u64` raw counts using a
checked implementation. A negative input or result, integer overflow,
floating-point overflow, NaN, or infinity fails; no such value may be omitted,
clamped, replaced, or interpreted favorably. This section supersedes
Amendment 1 A8's requirements that every denominator and numerator be positive:
zero candidate reverse work is explicitly valid under the rules above.

## A2.2 Direct typed equality and canonical encoding

Pair qualification is decided by direct equality of the typed records defined
here, field by field and vector item by vector item in the stated order.
SHA-256 hashes are integrity and transport summaries only. A matching hash
never excuses a typed mismatch. A typed match with a hash mismatch is a
serialization/integrity failure and fails qualification.

This section replaces Amendment 1 A6. There are no implementation-defined,
JSON-order-dependent, native-layout, debug-string, or unspecified event
fields. Every canonical record starts with its exact ASCII domain string,
followed by one zero byte, followed by schema version `2` as little-endian
`u16`, followed by its fields in the order specified below.
The integrity hash of a record is SHA-256 over exactly those complete canonical
bytes.

### Primitive encodings

- every length, index, ordinal, count, seed, dimension, microstep count, and
  iteration is an unsigned `u64` in little-endian order;
- an `f64` is `f64::to_bits()` encoded as little-endian `u64`; signed zero and
  NaN payload bits are preserved, never normalized;
- a boolean is one `u8`: `0` false or `1` true;
- an option is one `u8`: `0` none or `1` some, with the typed payload
  immediately after tag `1`; any other tag is invalid;
- an enum is one `u8` using only the frozen tags below;
- a string is its UTF-8 byte length as `u64` followed by the exact bytes,
  without normalization or terminator;
- a vector is its item count as `u64` followed by each typed item in order;
- a SHA-256 value is 32 raw bytes without a length or hexadecimal encoding;
- a struct is its fields in the exact listed order; maps and omitted struct
  fields are forbidden.

Enum tags are:

```text
phase: warmup=0, retained=1
direction: forward=0, backward=1
leaf_outcome: accepted=0, rejected=1
rejection: refinement_exhausted=0, reverse_coarser_accepted=1,
  invalid_evaluation=2
stop: maximum_depth=0, outer_uturn=1, recursive_uturn=2,
  refinement_exhausted=3, reverse_coarser_accepted=4,
  invalid_evaluation=5
evaluation: finite=0, recoverable_zero_density=1
fatal_error: malformed_or_nonfinite_evaluation=0, fatal_target_error=1,
  target_panic=2, control_abort=3, budget_abort=4, observer_abort=5
target_kind: posteriordb=0, neal_funnel=1, gaussian100=2,
  sspd11_t1000=3
target_contract: finite_only=0, finite_or_recoverable=1
backend: in_process_rust=0, windows_owned_serialized_worker=1
initialization: given=0, uniform=1
metric: diagonal=0
metric_regularization: stan=0
adaptation: dual_averaging=0
u_turn: momentum_sum=0
retained_exhaustion: stop=0
warmup_exhaustion: accept_unless_divergent=0
outer_selection: biased_progressive=0
recursive_selection: barker=0
reverse_order: finest_to_coarsest=0, coarsest_to_finest=1
arm: incumbent=0, candidate=1
metric_update: none=0, insufficient_samples=1, installed=2
warmup_stage: initial_fast=0, slow_window=1, terminal_fast=2
```

An unknown enum tag, option tag, trailing byte, short record, duplicate keyed
record, vector length mismatch, or out-of-order item is a schema failure.

### Pair-common static configuration

Domain:
`owalnuts.reverse_coarsening_order_v1.pair_common_static_config`.
There is one expected typed record and expected SHA-256 per target. Both are
committed with the implementation before any evidence. Both arms of every
pair must directly equal that expected record and each other.

The payload is the following exhaustive ordered field list. Inapplicable
options are encoded as explicit `none`; no field is omitted.

| order | key | type |
|---:|---|---|
| 1 | `study_id` | string |
| 2 | `work_package` | string |
| 3 | `source_baseline_commit` | string |
| 4 | `source_baseline_tree` | string |
| 5 | `algorithm_revision` | string |
| 6 | `target_id` | string |
| 7 | `target_kind` | enum `target_kind` |
| 8 | `target_dimension` | `u64` |
| 9 | `target_contract` | enum `target_contract` |
| 10 | `target_artifacts` | vector of `ArtifactPin` |
| 11 | `posteriordb_commit` | option string |
| 12 | `backend` | enum `backend` |
| 13 | `requested_backend_replicas` | `u64` |
| 14 | `effective_backend_replicas` | `u64` |
| 15 | `stan_threads_enabled` | bool |
| 16 | `global_bridge_serialization` | bool |
| 17 | `chains` | `u64` |
| 18 | `sampler_threads` | `u64` |
| 19 | `warmup_draws` | `u64` |
| 20 | `retained_draws` | `u64` |
| 21 | `timeout_seconds` | `u64` |
| 22 | `termination_grace_seconds` | `u64` |
| 23 | `kill_entire_process_tree` | bool |
| 24 | `initialization` | enum `initialization` |
| 25 | `initialization_radius` | option `f64` |
| 26 | `initialization_max_attempts` | option `u64` |
| 27 | `initialization_seed_xor` | option `u64` |
| 28 | `fixed_starts_artifact` | option `ArtifactPin` |
| 29 | `fixed_starts_count` | option `u64` |
| 30 | `chain_seed_derivation` | string |
| 31 | `rng_type` | string |
| 32 | `normal_distribution_type` | string |
| 33 | `h0` | `f64` |
| 34 | `max_depth` | `u64` |
| 35 | `min_micro_steps` | `u64` |
| 36 | `max_refinement_levels` | `u64` |
| 37 | `delta` | `f64` |
| 38 | `divergence_threshold` | `f64` |
| 39 | `u_turn` | enum `u_turn` |
| 40 | `retained_exhaustion` | enum `retained_exhaustion` |
| 41 | `metric` | enum `metric` |
| 42 | `adapt_metric` | bool |
| 43 | `initial_metric` | option vector `f64` |
| 44 | `adaptation` | enum `adaptation` |
| 45 | `target_accept` | `f64` |
| 46 | `adapt_step_size` | bool |
| 47 | `warmup_exhaustion` | option enum `warmup_exhaustion` |
| 48 | `metric_regularization` | enum `metric_regularization` |
| 49 | `chain_rescue` | option string |
| 50 | `initial_step_search` | option string |
| 51 | `warmup_initial_buffer` | `u64` |
| 52 | `warmup_base_window` | `u64` |
| 53 | `warmup_terminal_buffer` | `u64` |
| 54 | `warmup_telemetry_checkpoints` | vector `u64` |
| 55 | `dual_averaging_acceptance` | string |
| 56 | `dual_averaging_gamma` | `f64` |
| 57 | `dual_averaging_t0` | `f64` |
| 58 | `dual_averaging_kappa` | `f64` |
| 59 | `paper_adaptation` | option string |
| 60 | `restart_reference_multiplier` | `f64` |
| 61 | `stan_restart_reference` | bool |
| 62 | `initial_phase_max_error` | option `f64` |
| 63 | `minimum_step` | option `f64` |
| 64 | `step_floor_relative_to_search` | option `f64` |
| 65 | `max_window_shrink` | option `f64` |
| 66 | `cache_initial_evaluation` | bool |
| 67 | `outer_selection` | enum `outer_selection` |
| 68 | `recursive_selection` | enum `recursive_selection` |
| 69 | `admit_worst_case` | bool |
| 70 | `max_target_evaluations` | option `u64` |
| 71 | `cooperative_deadline` | option `u64` |
| 72 | `cancellation_enabled` | bool |
| 73 | `maximum_depth_stop_limit` | option `u64` |
| 74 | `reverse_schedule_generation_revision` | string |
| 75 | `comparison_schema_version` | `u64` |

`ArtifactPin` is, in order: role string, repository-relative or external
identity string, and SHA-256. `target_artifacts` is sorted by exact UTF-8 role
bytes and contains all target source, model, data, fixture, and bridge artifacts
required by Amendment 1 A7 and A9 below. Duplicate roles are forbidden.

The exact effective values are those frozen in Amendment 1 A7. In particular,
`adapt_step_size=true`, `dual_averaging_gamma=0.05`,
`dual_averaging_t0=10.0`, `dual_averaging_kappa=0.75`, and
`restart_reference_multiplier=1.0`; the apparently absent controls remain
explicit `none` values. Seed is deliberately not a static-config field.

### Arm configuration

Domain: `owalnuts.reverse_coarsening_order_v1.arm_config`. Its fields, in
order, are pair-common static-config SHA-256, arm tag, and reverse-order tag.
The only valid records are incumbent/finest-to-coarsest and
candidate/coarsest-to-finest. The two expected arm records and hashes are
committed before evidence.

Arm/order/implementation IDs remain excluded from pair-common configuration.
Harness commit, source commit, executable hash, build transcript, command line,
host, timestamps, and runtime transcript are provenance, not pair-common or
arm configuration. In particular, implementation IDs do not enter either
expected static hash.

### Initial-position matrix

Domain: `owalnuts.reverse_coarsening_order_v1.initial_positions`. Its fields
are target ID string, evidence seed, row count, column count, then row-major
`f64` bits. Each one-shot arm cell produces this separate deterministic hash
after initialization. No initial-position value or matrix hash must be
precommitted.

The analyzer directly compares matrix dimensions and every bit across paired
arms. For `Init::uniform`, it independently validates the matrix and complete
initializer attempt classifications against the frozen initializer, target,
seed XOR, and chain-seed derivation. For `Init::Given`, it validates every bit
against the pinned fixed-start fixture or fixed-start construction. Any
validation or paired equality failure fails the cell. Initial positions and
runtime initializer transcripts never enter static expected config hashes.

Domain: `owalnuts.reverse_coarsening_order_v1.initializer_attempts`. Its
fields are target ID string, evidence seed, and an ordered attempt vector.
Each attempt is chain index, attempt index, proposed position vector,
evaluation tag, finite log-density option, finite-gradient option, and selected
boolean. Records are ordered by chain then attempt. A finite evaluation
requires both finite fields; a recoverable-zero-density evaluation forbids
both. Exactly one attempt per uniform-initialized chain has `selected=true`,
and it must be that chain's last attempt and equal the corresponding initial
matrix row. Given initialization has an empty attempt vector. Paired records
must directly match; their hashes are integrity summaries only.

### Semantic comparison records

Domain: `owalnuts.reverse_coarsening_order_v1.semantic`. Its payload fields,
in exact order, are:

1. target ID string, evidence seed, chain count;
2. chains ordered by ascending chain index;
3. for each chain: chain index, effective chain seed, transition vector, final
   tuning record, final metric vector, retained unconstrained draw matrix, and
   optional constrained/reference draw matrix in the frozen column order;
4. transitions ordered as all warmup transitions by phase index followed by
   all retained transitions by phase index;
5. each transition: phase, phase index, global transition index,
   `direction_draws`, `uniform_draws`, orbit-state count, initial orbit
   selection index, final orbit selection index, depth, position-changed
   boolean, selected theta vector, selected rho vector, selected log-density,
   selected gradient vector, ordered leaf-attempt vector, and adaptation
   option;
6. each adaptation record: warmup stage, option window index, option window
   start, option window end, input acceptance-statistic option `f64`, active
   step `f64` before and after, dual-averaging state before and after in order
   `(target f64, mu f64, log_step f64, log_step_bar f64, h_bar f64,
   iteration u64)`,
   metric-update tag, and option installed metric vector;
7. final tuning: `h0`, active step, max depth, min microsteps, max refinement
   levels, delta, divergence threshold, U-turn tag, retained exhaustion tag,
   outer-selection tag, and recursive-selection tag;
8. each matrix: row count, column count, then row-major `f64` values.

The complete RNG semantic payload is exactly the per-transition
`direction_draws` and `uniform_draws` `u64` counts plus the initial and final
orbit selection indices. There are no RNG-event variants, event names,
generator-state dumps, individual direction bits, individual uniform or
normal variates, or selection-probability records in this schema. Leaf
direction is an algorithmic trajectory field, not an RNG-payload extension.
No implementation may add unspecified RNG event types.

A leaf-attempt record has these ordered fields:

1. leaf-attempt index;
2. direction tag;
3. ordered forward-attempt vector;
4. accepted-forward-level option;
5. accepted-forward-endpoint option;
6. complete generated-reverse-schedule vector;
7. leaf-outcome tag;
8. rejection option;
9. accepted-built-state option.

A forward-attempt is, in order: refinement level, microsteps, step `f64`,
ordered target-evaluation vector, and endpoint option. An endpoint/state is
theta vector, rho vector, log density, and gradient vector. A target evaluation
is evaluation tag, position vector, finite log-density option, finite-gradient
option. A finite evaluation requires both finite fields to be `some`; a
recoverable-zero-density evaluation requires both to be `none`. Target error
messages and categories are not semantic fields.

A generated reverse-schedule entry is, in order: coarse-level index,
microsteps, and step `f64`. Schedules are compared directly in generated order,
before traversal, for exact length, indices, microsteps, and step bits.

Required and forbidden leaf option combinations are:

| outcome | accepted level | forward endpoint | schedule | rejection | built state |
|---|---|---|---|---|---|
| accepted | required | required | complete, length equals accepted level | forbidden | required and exactly equals forward endpoint |
| rejected: refinement exhausted | forbidden | forbidden | required empty | required tag `refinement_exhausted` | forbidden |
| rejected: reverse coarser accepted | required | required | required nonempty | required tag `reverse_coarser_accepted` | forbidden |
| rejected: invalid evaluation in forward traversal | forbidden | forbidden | required empty | required tag `invalid_evaluation` | forbidden |
| rejected: invalid evaluation in reverse traversal | required | required | required nonempty | required tag `invalid_evaluation` | forbidden |

No other option combination is valid. For reverse-coarser rejection, visited
reverse records form the arm's traversal prefix and end at the first finite
accepting evaluation. For reverse-invalid rejection, they end at the first
fatal evaluation. For an accepted leaf, every scheduled reverse level was
visited without acceptance or fatal error. No level is skipped, repeated, or
approximated.

### Reverse evaluations, stops, and fatal errors

Domain: `owalnuts.reverse_coarsening_order_v1.reverse_evaluations`. Each
record's key is exactly, in this order:

1. chain index;
2. global transition index;
3. leaf-attempt index;
4. reverse-evaluation index within that reverse attempt;
5. coarse-level index;
6. microsteps;
7. step `f64` bits.

The key is followed by position vector, evaluation tag, finite log-density
option, and finite-gradient option. Records are stored in actual traversal and
evaluation order. Complete stream equality is not required because order and
short-circuiting are the intervention. Records with the same key must directly
match in all fields; schedule equality, prefix legality, first-result behavior,
and work counters are checked separately.

Domain: `owalnuts.reverse_coarsening_order_v1.stops`. Each record is chain
index, global transition index, stop tag, leaf-outcome vector in leaf-attempt
order, rejection option per leaf, and public-error option string. Paired
records must directly match exactly.

Fatal records are outside the semantic payload and semantic hash. Domain:
`owalnuts.reverse_coarsening_order_v1.fatal_errors`. Each is chain index,
option global transition index, option leaf-attempt index, option
reverse-evaluation key, fatal-error tag, and exact message string. Malformed or
nonfinite evaluations, fatal `TargetError`, target panic, control abort, budget
abort, and observer abort are all fatal. Any fatal record in any evidence cell
fails qualification, even if the paired arm has an identical record.

Before evidence, the version-2 conformance fixture must exercise every
primitive and enum tag, both option tags, empty and nonempty vectors, signed
zero, every valid leaf option row, a recoverable evaluation, and each fatal
record. A Rust encoder and independent non-Rust checker must reproduce the
committed bytes and hashes. Conformance data are not evidence.

## A2.3 Static-hash circularity prohibition

Expected pair-common and arm typed records and SHA-256 values are committed
after implementation but before evidence. They contain only the static fields
listed above. They must not contain initial positions, initial-position hashes,
initializer attempt transcripts, process IDs, timestamps, durations, launch
or completion markers, stdout/stderr, runtime call traces, result-derived
values, executable hashes, build transcripts, or any evidence artifact.

Per-cell initial-position hashes are deterministic runtime products governed
only by A2.2. They are validated against the frozen initializer and seed or
fixed-start fixture and must match across arms. Their absence from the
precommitted static hashes is intentional and is not a missing pin.

## A2.4 WP37A pure-target source pin

The Neal funnel and 100-D Gaussian targets are pinned to the existing tracked
WP37A source:

| item | pin |
|---|---|
| path | `STUDIES/delta2_sidechecks_v1/src/main.rs` |
| WP37A implementation commit | `e91458dca1aa7944b07c65514ad2313b4a60cd4d` |
| merged WP37B source baseline | `a630e04151842cf7a92131dcadd8e9412c675f5b` |
| Git blob at both commits | `0385e3fbcd2caad2c92c81a02b0ec148f02d2543` |
| SHA-256 recorded by WP37A | `ba6629bd6ceb0d1d0d7b6016de68c21c2ef8861c294aed8c24d50aff52f4ec49` |

WP37B may copy only the corresponding constants, target structs, and `Target`
implementations byte-for-byte from that blob. Pre-evidence provenance must
assert the path, both commits, Git blob, and SHA-256 above, and mechanically
compare the copied source spans with the pinned blob. Any difference fails
before launch.

The controlling funnel operation order is exactly:

1. `omega = position[0]`;
2. `inverse_variance = (-omega).exp()`;
3. if it is nonfinite, return recoverable
   `"exp(-omega) overflowed"`;
4. sum `x * x` over `position[1..]` in iterator order;
5. set `tail = (FUNNEL_DIMENSION - 1) as f64`, with dimension 10;
6. evaluate
   `gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares`;
7. in coordinate order set each remaining gradient to
   `-inverse_variance * x`;
8. evaluate
   `value = -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares`;
9. return the value only if it and every gradient coordinate are finite;
   otherwise return recoverable `"nonfinite funnel evaluation"`.

The controlling Gaussian operation order is: dimension 100; zip gradient and
position in coordinate order and assign `*g = -*x`; then return
`Ok(-0.5 * position.iter().map(|x| x * x).sum::<f64>())`. It has no
target-local recoverable branch or target-local finiteness check. Under A1 A5,
any nonfinite value or gradient returned as `Ok` is classified as
`malformed_or_nonfinite_evaluation`, recorded outside the semantic hash, and
fails qualification. The harness may not silently convert that outcome to
recoverable zero density.

These source operations, association, iterator order, messages, finiteness
tests, and error categories are frozen; algebraically equivalent rewrites are
not equivalent implementations.

## A2.5 Decision scope and unchanged defaults

The only possible positive label remains
`QUALIFY_COARSEST_FIRST_OPT_IN_FOR_FINITE_OR_RECOVERABLE_TARGETS`. A pass can
qualify only a later, explicit Rust opt-in on `KernelTuning` and high-level
`Tuning`, and only for targets that document and satisfy the deterministic
finite-or-recoverable evaluation contract.

Every walnutpie, high-level sampler, and Python default remains
`FinestToCoarsest`. Generic `Target` behavior, replay, fingerprints, and
algorithm revision remain unchanged. This amendment neither authorizes nor
contains implementation or default changes.
