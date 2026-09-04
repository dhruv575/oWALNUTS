# Amendment 1 — reverse_coarsening_order_v1 (WP37B)

Frozen 2026-09-04 after protocol review and before candidate or harness
implementation, build, child launch, sampling, or evidence. This is an
append-only clarification of preregistration commit
`84a76b1a47ae43034ac460e7d409cc0d4e5ec5f2`. The original
`PREREGISTRATION.md` and `protocol.json` remain byte-for-byte unchanged. Their
UTF-8/LF-normalized SHA-256 values remain:

- `PREREGISTRATION.md`:
  `ba4a3a9e64c8757d021ec9886e24f537c4059e8deb24565f1bd90ba94d98234d`;
- `protocol.json`:
  `6dc9deaf1a3133c9e308a68bd6352f0a30cf61653ee7dad8da93dba59a4b9c81`.

Where this amendment is more specific than the original files, this amendment
controls. It does not change the arms, targets, seeds, target order, alternating
arm order, run lengths, 84-child manifest, one-shot/no-rerun rule, or efficiency
thresholds.

## A1. Pair-common and arm configuration authentication

The original phrase "configuration identity" is split into two different
hashes.

The **pair-common configuration record** contains everything that must be
identical between the two arms of one target/seed pair: source baseline;
harness/binary/dependency identities; target, model, data, fixture and backend
identities; evidence seed and chain-seed derivation; exact initial positions
and initialization transcript; chain/thread counts; warmup/retained counts;
timeout and process policy; admission/budget settings; metric and adaptation;
all kernel settings other than reverse traversal order; cache and selection
rules; telemetry schema; and semantic-hash schema. It expressly excludes:

- arm name or arm tag;
- reverse-coarsening traversal order;
- candidate/incumbent role;
- implementation, branch, commit, revision, feature, or build labels that
  differ only to identify the arm implementation.

Its SHA-256 domain is
`owalnuts.reverse_coarsening_order_v1.pair_common_config` at schema version 1,
encoded by A6. M2 compares this pair-common hash for exact equality across each
of the 42 pairs. A differing pair-common hash is configuration
non-authentication and fails M1/M2.

Each child also carries a separate **arm configuration record**. It contains
the pair-common hash, frozen arm tag, frozen traversal-order tag, and the
arm-specific implementation identifier. Its SHA-256 domain is
`owalnuts.reverse_coarsening_order_v1.arm_config` at schema version 1. Before
the first evidence launch, the committed provenance record must contain one
expected incumbent hash and one expected candidate hash for every distinct
target configuration. A child is authenticated only when its arm hash equals
the corresponding frozen expected value. Incumbent and candidate arm hashes
are expected to differ and are never compared to each other.

This replaces any reading of the original M2 that would compare arm IDs,
traversal-order IDs, or candidate implementation IDs as pair-common data.

## A2. Eligibility boundary and decision scope

The candidate can be qualified only for a target satisfying this complete
contract:

1. the target is deterministic and thread-safe, with no hidden mutable
   cross-chain state;
2. every position presented by the kernel deterministically produces either
   a finite log density with a fully finite gradient, or
   `TargetError::recoverable`;
3. a recoverable result means a deterministic zero-density point and is mapped
   to `log_density = -inf` and an all-zero gradient;
4. the same position always receives the same finite-versus-recoverable
   classification;
5. the initial/current position is finite and evaluable.

Targets that can return a fatal `TargetError`, malformed/nonfinite output,
panic, or otherwise abort an evaluation do not satisfy the qualified contract.
In particular, when one generated reverse level is accepted and another is
fatal-invalid, traversal order can decide whether the accepted level
short-circuits before the fatal condition. The two public outcomes can differ.
Evidence on the fixed targets cannot establish safety for that generic
`Target` case.

Accordingly, the original pass label and default-change authorization are
replaced. The only pass label is:

`QUALIFY_COARSEST_FIRST_OPT_IN_FOR_FINITE_OR_RECOVERABLE_TARGETS`

A pass may authorize a later, separately reviewed and labelled stable Rust
opt-in only on these surfaces:

- `walnutpie::KernelTuning`, through an explicit reverse-coarsening-order
  option;
- high-level `owalnuts::sampler::Tuning`, through a corresponding explicit
  option.

The stable option must document the finite-or-recoverable target precondition.
It may use a public order enum needed by those two methods, but no other public
surface is authorized. `KernelTuning::default()`, `KernelOptions::default()`,
`RunConfig`, high-level `Tuning::default()`, `Sampler::default()`, all Python
configuration and bindings, registered fingerprints, replay fixtures, and
`ALGORITHM_REVISION` remain `FinestToCoarsest` regardless of the study result.
No generic `Target` default may change.

If any gate fails or is inconclusive, the result remains
`KEEP_FINEST_TO_COARSEST` and no stable opt-in is qualified. In both pass and
failure cases every default remains finest-first. This amendment and the
evidence-only research implementation authorize no production API change.

## A3. Exact generated schedule and synthetic conformance

For every forward macro leaf accepted at zero-based refinement level `L`, both
arms must completely generate and record the reverse schedule **before**
traversal. The schedule has exactly `L` entries. Generation starts with the
accepted forward `step` and `micro_steps` and applies the existing operations
once per entry:

```text
coarse_steps /= 2
coarse_step  *= 2.0
coarse_level  = previous coarse_level - 1
```

The recorded entry is exactly
`(coarse_level: u64, coarse_micro_steps: u64, coarse_step_bits: u64)`, where
`coarse_step_bits = coarse_step.to_bits()`. Incumbent traversal uses entries
`0..L`; candidate traversal uses entries `(0..L).rev()`. An `L = 0` leaf has
an empty schedule.

For every corresponding leaf, before considering traversal outcomes, the arms
must have exact equality of:

- schedule length;
- every coarse-level index;
- every coarse-micro-step count;
- every `f64` coarse-step bit pattern.

The schedule must contain each permitted coarser level exactly once. A skipped,
duplicated, lazily omitted after short-circuit, reused, memoized,
trajectory-cached, directly exponentiated, approximated, or differently
associated level fails M2. Each visited attempt still starts from the current
forward endpoint copied into the reverse workspace with momentum negated, as
at the source baseline; no visited result or trajectory is reused.

Before evidence, committed non-evidence synthetic conformance tests must cover
both directions and every schedule length reachable with eight refinement
levels:

1. all generated reverse levels valid and over tolerance ("all fail"), proving
   the forward leaf is retained and the full schedules match;
2. a parameterized case in which each possible reverse level is the accepted
   level, proving both arms reject as `ReverseCoarserAccepted` while permitted
   reverse work differs;
3. recoverable zero-density at each possible reverse level, proving it maps to
   `-inf`/zero gradient, is never accepted, and preserves semantic and
   stop/cause identity under the eligible contract;
4. at least one two-level mixed case containing one accepted level and one
   malformed/fatal-invalid level, with their relative order reversed between
   arms. This test must record the expected different rejection/public-error
   cause and state explicitly that the target is ineligible for the qualified
   opt-in. It is an expected order-dependence demonstration, not an identity
   test to be made green by suppressing the fatal result.

Synthetic tests use no evidence seed and supply no evidence cell.

## A4. Child timeout, grace, and process-tree policy

The parent timeout runs from successful child creation through child exit:

| target | timeout |
|---|---:|
| `posteriordb_accel_gp` | 1,800 seconds |
| `posteriordb_gp_pois_regr` | 900 seconds |
| `posteriordb_eight_schools_centered` | 600 seconds |
| `posteriordb_eight_schools_noncentered` | 600 seconds |
| `neal_funnel_10d` | 1,800 seconds |
| `gaussian_100d` | 300 seconds |
| `state_space_sspd11_t1000` | 900 seconds |

Each Windows child is created suspended, assigned before resume to a dedicated
Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, and then resumed. On
timeout the parent marks the cell process-invalid and terminates the entire Job
Object/process tree. It then allows exactly **30 seconds of cleanup grace** to
observe process-tree termination, close stdout/stderr, and record late-file
state. Grace does not extend the timeout, make a late result valid, or permit a
rerun. Failure to terminate every descendant is separately recorded and the
cell remains process-invalid. A timeout is never replaced, even if an atomic
raw result existed before or appears during grace.

## A5. Evaluation and abort categories

Every attempted initial, forward, and reverse target call is assigned exactly
one category:

| category | definition | evidence treatment |
|---|---|---|
| `finite` | target returns finite log density and every gradient component is finite | eligible |
| `recoverable_zero_density` | `TargetError::recoverable`; facade maps to `-inf` and a zero gradient | eligible; exact category/call comparison required |
| `malformed_or_nonfinite_fatal` | nonfinite position produced by the kernel; `Ok` with nonfinite log density or any nonfinite/unwritten/wrong-length gradient; malformed callback payload | fatal |
| `fatal_target_error` | explicit fatal `TargetError` | fatal |
| `target_panic` | target callback panics | fatal |
| `control_abort` | cancellation or deadline/control stop | abort |
| `budget_abort` | target-call/admission budget stop | abort |
| `observer_abort` | observer panic, observer limit, malformed observation, or observer-requested stop | abort |

An adapter may translate a domain failure or raw `-inf` into
`TargetError::recoverable` before this boundary; the recorded category is then
`recoverable_zero_density`. A target directly returning nonfinite `Ok` data is
not recoverable.

Recoverable events, their positions, phase/level/evaluation indices, counts,
and mapped bits are included in the forward-call or reverse-evaluation
telemetry and compared across arms. Forward records must be exactly equal.
Reverse records may differ in traversal order and in levels skipped after
short-circuit, but any level visited by both arms must have an exactly equal
evaluation record when keyed by chain, transition, leaf and generated-schedule
index; candidate-only/incumbent-only visited levels and recoverable counts are
reported. Recoverable events do not count as invalid stops.
`StopReason::InvalidEvaluation`, its leaf rejection/cause, and every public
error class/message are separately recorded and must match exactly within a
pair.

Any fatal or abort category in any evidence cell fails qualification,
regardless of whether the child exits zero, writes a raw artifact, or the paired
arm encounters the same category. It is not converted into a process exclusion
or recoverable event. A timeout additionally follows A4.

## A6. Canonical byte schema and test vector

All hashes in this amendment use SHA-256 over a domain header followed by a
canonical payload. The header is the exact ASCII domain string without Unicode
normalization, followed by one zero byte, followed by schema version `1` as
little-endian `u16`. No field names, JSON formatting, host `usize`, native
struct layout, debug strings, or platform-dependent enum discriminants enter a
hash.

Primitive encoding is frozen:

- `u8`, `u16`, `u32`, `u64`, and `i64`: fixed width, little-endian where
  wider than one byte;
- every index, count, ordinal, dimension, and vector/string length: `u64`;
- evidence seed and effective chain seed: `u64`;
- boolean: one `u8`, `0` false and `1` true; no other value is valid;
- enum: one `u8` using the explicit tag tables below;
- option: one `u8` (`0` none, `1` some), immediately followed by the encoded
  payload only for `some`;
- `f64`: `f64::to_bits()` encoded as little-endian `u64`; signed zero is
  preserved and NaN payloads are never canonicalized;
- UTF-8 string: byte length as `u64`, then exact bytes, with no terminator and
  no normalization;
- byte vector or typed vector: element count as `u64`, then elements in order;
- SHA-256 value: exactly 32 raw bytes, no length and no hexadecimal text;
- struct: fields in the order specified here; map/object encoding is forbidden.

Shared enum tags are:

```text
transition_phase: warmup=0, retained=1
evaluation_phase: initial=0, forward=1, reverse=2
direction: forward=0, backward=1
evaluation_category: finite=0, recoverable_zero_density=1,
  malformed_or_nonfinite_fatal=2, fatal_target_error=3, target_panic=4,
  control_abort=5, budget_abort=6, observer_abort=7
rng_event: standard_normal=0, direction=1, recursive_barker_uniform=2,
  outer_metropolis_uniform=3
selection_event: recursive_barker=0, outer_biased_progressive_metropolis=1
orbit_event: forward_leaf=0, recursive_uturn_predicate=1,
  recursive_combine=2, outer_uturn_predicate=3, outer_combine=4,
  selected_output=5
warmup_phase: initial_fast=0, slow_window=1, terminal_fast=2
acceptance_statistic: current_coarse_endpoint=0
metric_update_outcome: none=0, insufficient_samples=1, installed=2
stop_reason: maximum_depth=0, outer_uturn=1, recursive_uturn=2,
  refinement_exhausted=3, reverse_coarser_accepted=4, invalid_evaluation=5
arm: finest_to_coarsest=0, coarsest_to_finest=1
config_value_type: none=0, bool=1, u64=2, i64=3, f64=4, string=5,
  sha256=6, string_vector=7, u64_vector=8, f64_vector=9
```

An unlisted enum variant or RNG/selection event is a schema/configuration
mismatch and stops evidence before launch or fails qualification if observed.

The semantic hash domain is
`owalnuts.reverse_coarsening_order_v1.semantic`, version 1. Its payload is:

1. pair-common configuration hash;
2. target ID string, evidence seed, and chain count;
3. chains in ascending chain index;
4. for each chain: chain index, effective chain seed, initial-position `f64`
   vector, and ordered initialization-evaluation records;
5. transition count, then transitions in this exact order: all warmup
   transitions by increasing phase index, followed by all retained transitions
   by increasing phase index;
6. for each transition: phase, phase index, global transition index; selected
   state (`theta`, `rho`, log density and gradient bit vectors); selected and
   initial orbit indices; orbit-state count; depth; position-changed boolean;
   ordered RNG-event vector in consumption order; ordered non-reverse orbit
   event vector; ordered selection-event vector; and adaptation record;
7. an orbit event is encoded as event tag `u8`, optional depth, optional leaf
   ordinal, optional direction, optional selected boolean, optional selected
   index, optional state (`theta`, `rho`, log density, gradient), and optional
   log weight/update probability, in that order;
8. a selection event is encoded as its tag, direction, `f64` uniform draw,
   `f64` log update probability, selected-new boolean, and selected orbit
   index;
9. an adaptation record is an option. When present it contains, in order:
   acceptance-statistic tag, input statistic option, active step before and
   after, complete dual-averaging state before and after
   `(target, mu, log_step, log_step_bar, h_bar, iteration)`, warmup phase,
   optional window index/bounds, optional metric-update outcome and complete
   installed metric bits;
10. final active tuning fields in A7 order and final metric bit vector;
11. retained unconstrained draws in draw-major order and, for posteriordb,
    retained constrained/reference-parameter draws in the frozen reference
    column order.

The semantic payload excludes generated/visited reverse schedules, reverse
work, reverse-only energy values, first-rejecting reverse level, and
stop/rejection/public-error causes. They are covered by separate exact records
and hashes rather than silently ignored.

Separate domains, all version 1 and using the same primitives, are:

- `owalnuts.reverse_coarsening_order_v1.pair_common_config`: a vector of
  configuration entries sorted by the exact UTF-8 bytes of their unique key.
  Each entry is key string, `config_value_type` tag, then its typed value;
  vector values use the primitive vector encoding. The entry set is exactly
  the included A1 fields and exact A7 effective values, including
  target-specific values under `target.*` keys. Source Git IDs are strings,
  SHA-256 values are raw 32-byte values, and inapplicable target-specific keys
  are present with type `none`, not omitted;
- `owalnuts.reverse_coarsening_order_v1.arm_config`: pair-common hash, arm tag,
  traversal-order tag using the same arm tag table, then implementation-ID
  string;
- `owalnuts.reverse_coarsening_order_v1.reverse_schedule`: records sorted by
  chain, transition phase/index, and leaf execution ordinal; each record
  contains that key, accepted forward level, schedule length, and the complete
  generated entry vector from A3;
- `owalnuts.reverse_coarsening_order_v1.forward_calls`: records sorted by
  chain, transition phase/index, leaf ordinal, forward level, and evaluation
  index; each contains that key, position bits, evaluation category, optional
  finite log-density/gradient bits, and exact mapped recoverable bits;
- `owalnuts.reverse_coarsening_order_v1.reverse_evaluations`: records in actual
  traversal order, each containing chain, transition phase/index, leaf ordinal,
  generated-schedule index, coarse-level index, evaluation index, position
  bits, evaluation category, optional finite log-density/gradient bits, and
  exact mapped recoverable bits. Whole-stream equality is not required because
  traversal and short-circuit work are the intervention; equality is required
  for records sharing the same generated-schedule key;
- `owalnuts.reverse_coarsening_order_v1.stop_causes`: records sorted by chain
  and transition order; each contains transition stop tag, ordered leaf
  rejection tags, and optional public error category plus exact UTF-8 message.

Parallel wall-clock/interleaving order never enters a hash. Chain order,
transition order, leaf execution order within a chain, vector coordinate order,
and posteriordb reference-column order do.

Before evidence, the committed provenance must include a
`semantic-hash-test-vector-v1` fixture containing: a human-readable logical
record exercising every primitive, every option tag, every enum tag, signed
zero, and nonempty chain/transition/leaf/RNG/selection/adaptation data; the
exact canonical payload as hexadecimal bytes; and expected SHA-256 values for
semantic, reverse-schedule, forward-call, reverse-evaluation, stop/cause,
pair-common, and both arm records. The Rust encoder and an independent non-Rust
checker must reproduce every expected byte and hash. Any mismatch stops before
evidence. The fixture and expected hashes are conformance data, not study
evidence.

## A7. Source and exact effective setting pins

All effective settings are pinned to source baseline
`a630e04151842cf7a92131dcadd8e9412c675f5b`; later source defaults cannot be
inherited. The controlling source blobs at that commit are:

| path | Git blob |
|---|---|
| `src/sampler.rs` | `e3c70f3e3ccd2a3e82bbc6400181d8bedd39467e` |
| `src/walnutpie.rs` | `3a3b372d317cc5c702cbe80f6445885d14c4a14f` |
| `src/kernel.rs` | `660e841f071bb201da77f1d895bf15864dbd3389` |

The controlling definitions are `sampler::{Sampler::default,
Tuning::default, Adaptation::default, Metric::default, Init::uniform,
DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION,
DEFAULT_METRIC_REGULARIZATION, DEFAULT_CHAIN_RESCUE}`,
`walnutpie::{WarmupConfig::default, WarmupWindowConfig::default,
InitialStepSearchConfig::default, ALGORITHM_REVISION}`, and
`kernel::{KernelOptions::default, OuterSelectionPolicy::BiasedProgressive}` at
that commit. The explicit values below control if prose or a later default
differs.

The harness must construct and serialize these exact effective values:

```text
chains=4; sampler_threads=4
h0=0.5; max_depth=10; min_micro_steps=1; max_refinement_levels=8
max_error=1.0; divergence_threshold=1000.0
u_turn=MomentumSum; retained_exhaustion=Stop
metric=Diagonal{adapt=true, initial=None}
adaptation=DualAveraging{target_accept=0.8}
warmup_exhaustion=Some(AcceptUnlessDivergent)
metric_regularization=Stan
chain_rescue=None
initial_step_search=None
warmup_windows={initial_buffer=75, base_window=25, terminal_buffer=50}
warmup_telemetry_checkpoints=[]
dual_averaging_acceptance=CurrentCoarseEndpoint
paper_adaptation=None
restart_reference_multiplier=One
stan_restart_reference=false
initial_phase_max_error=None; minimum_step=None
step_floor_relative_to_search=None; max_window_shrink=None
cache_initial_evaluation=true
outer_orbit_selection=BiasedProgressive
recursive_subtree_selection=Barker
admission=Limits::admit_worst_case()
max_target_evaluations=None; cooperative deadline/timeout=None
cancellation=None; maximum_depth_stop_limit=None
```

The corresponding key `f64` bits are:
`h0 0x3fe0000000000000`, `delta 0x3ff0000000000000`,
`divergence_threshold 0x408f400000000000`, and target acceptance
`0x3fe999999999999a`. Dual averaging is exactly the source implementation:
initial `mu = ln(10*h0)`; updates use `gamma=0.05`, `t0=10`,
`kappa=0.75`; a successful nonfinal metric-window installation restarts from
the current step with `restart_reference_multiplier=One`; the final retained
step is the clamped exponent of `log_step_bar`. The source formulas and their
operation order are controlling.

During each slow window, Welford updates consume selected positions in
transition order. For each coordinate at sample count `n >= 2`, Stan
regularization computes, in source order,
`((n/(n+5)) * (m2/(n-1)) + 1e-3 * (5/(n+5)))`, then clamps to
`MIN_ADAPTATION_VARIANCE`, then takes the reciprocal to obtain the installed
momentum-covariance diagonal. The paired arms must have exact window samples,
Welford state, candidate metric bits, installation outcome, and installed
metric bits.

The actual 1,000-transition warmup schedule is
`[0,75)` initial fast, slow windows
`[75,100), [100,150), [150,250), [250,450), [450,950)`, and
`[950,1000)` terminal fast. The 2,000 schedule has slow windows
`[75,100), [100,150), [150,250), [250,450), [450,850), [850,1950)`
and terminal `[1950,2000)`. The 500 schedule has slow windows
`[75,100), [100,150), [150,250), [250,450)` and terminal `[450,500)`.
None uses the short-warmup fallback.

Recursive subtree candidates use Barker normalized-weight selection; completed
outer expansions use the existing biased-progressive Metropolis combination;
direction is drawn at each doubling. RNG is `rand::rngs::SmallRng` and
`rand_distr::StandardNormal` at the committed `Cargo.lock`; chain `i` uses
`splitmix64(seed + i)`. `Init::uniform()` is radius 2, at most 100 attempts per
chain, with its independent `SmallRng` seeded by
`splitmix64(seed ^ 0x5eed141700000000)`. Posteriordb and Gaussian use that
initializer and must match exact initial-position and initializer-call
transcripts across arms. Funnel and state space use `Init::Given` with the
fixed starts. Cache use, random draws, selections, adaptation states, and final
tuning/metric are included in A6.

Target-specific effective values remain:

| target | warmup/retained | initialization/backend |
|---|---:|---|
| each posteriordb target | 1,000/1,000 | `Init::uniform`; WP35 posteriordb `28f8d3d6e975315f42aa274a8399f21e07a43b30`; Windows owned serialized worker, requested replicas 4/effective 1, no `STAN_THREADS` |
| Neal funnel | 2,000/20,000 | fixed `omega={-3,-1,1,3}`, other coordinates zero |
| 100-D Gaussian | 1,000/1,000 | `Init::uniform` |
| `sspd-11` state space | 500/2,000 | fixed canonical fixture and starts below |

The state-space target and starts are copied from these tracked canonical-study
files; the SHA-256 values are those recorded in that study's
`CHECKSUMS.sha256`:

| canonical source | SHA-256 |
|---|---|
| `STUDIES/sspd11_confirmation_v1/primary/src/canonical.rs` | `06776b94d15b9704ff4d1e0bbddbe0f66c783930d15499540366e64d151532d7` |
| `STUDIES/sspd11_confirmation_v1/primary/src/main.rs` | `7c63fe1da3ea774479f17bee627616905c63d8a621a1a2389a03098434973997` |
| `STUDIES/sspd11_confirmation_v1/primary/protocol.json` | `2679b4edc6bf582c9762ccd55caeb16b9afafb067b56c57aa9f4faf87439c5c4` |
| `STUDIES/sspd11_confirmation_v1/primary/starts/sspd-11.json` | `e981bb97d496ac144752c25c4308aeeb4460a080b449276f0fd5a440a8eb2190` |
| `STUDIES/sspd11_confirmation_v1/primary/fixtures/polyscope_parity.json` | `4c91f5fddda2e15f42e4209343ee9234bdab866a32918c260fe29fd6b0cf7d0c` |
| `STUDIES/sspd11_confirmation_v1/primary/fixtures/sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json` | `2fff97663b6e7946e64e465610ebf9dd4350d6615ecaa5aa513ff070b683baad` |

Only the canonical target, parity behavior, fixture, and fixed-start
construction are copied. WP37B uses the common current sampler settings above,
not the canonical study's historical arm I/P metric choices, `h0=0.1`, depth
8, or three-level tuning. The pre-evidence provenance must hash the copied
WP37B source and prove it matches these pinned inputs and start bits.

## A8. Pair counts, work ratios, and amended mechanical decision

The manifest contains:

- **84 arm cells** = 7 targets x 6 seeds x 2 arms;
- **42 paired blocks** = 7 targets x 6 seeds;
- **84 pair-phase comparisons** = 42 paired blocks x the two phases
  `warmup` and `retained`.

Initialization/start-search calls, if any, are reported separately and included
in cell totals; the cell/phase E1 comparisons are exactly the 84
warmup/retained units above. The fixed configuration has no initial-step
search. For each gated work comparison, both raw integer counts and the
candidate/incumbent ratio are recorded.

Every gated work denominator must be positive, every ratio must be finite and
strictly positive, and every source count must fit the frozen `u64` schema.
A zero numerator, zero denominator, overflow, NaN, or infinity fails the
corresponding efficiency gate; it is never omitted, assigned a favorable
limit, or removed from an aggregate.

The amended mechanical decision is:

1. evaluate M1–M3 and E1–E3, as clarified by A1–A8, on all 84 cells;
2. return
   `QUALIFY_COARSEST_FIRST_OPT_IN_FOR_FINITE_OR_RECOVERABLE_TARGETS`
   only if every gate passes;
3. otherwise return `KEEP_FINEST_TO_COARSEST`;
4. regardless of label, keep every Rust and Python default finest-first.

Posterior validity statistics remain mandatory descriptive reports and cannot
select results. Wall time remains descriptive. No evidence rerun, replacement,
repair, seed/target/chain/phase selection, or post-result contract expansion is
permitted.
