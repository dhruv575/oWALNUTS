# Preregistration — reverse_coarsening_order_v1 (WP37B)

Frozen 2026-09-04 before candidate implementation, study-harness
implementation, build, or evidence. The source baseline is commit
`a630e04151842cf7a92131dcadd8e9412c675f5b` (tree
`59ff3f52debb54fd8cea62effd51982c7ecd7a88`). `protocol.json` is the
machine-readable protocol. This commit contains only the preregistration
scaffold; it changes no sampler code, default, replay contract, or algorithm
revision and contains no evidence.

## Question and scope

WP30 and WP34 identified the reverse-coarsening check as the remaining
kernel-side cost on the hard targets: it ends 10–54% of transitions on
`accel_gp`, `gp_pois_regr`, and the centered and noncentered Eight Schools.
WP37A did not qualify the fixed-`delta = 2` route and directed the next kernel
study to a cheaper reverse-coarsening check at fixed `delta = 1`.

This study asks whether evaluating the already-defined reverse levels from
coarsest to finest saves calls without changing the sampled process. It is a
mechanical semantic-and-work qualification, not a posterior-result selection
study. Posterior validity statistics are reported for every cell but cannot be
used to select seeds, targets, chains, phases, or outcomes.

## Frozen arms and the only algorithmic difference

There are exactly two arms:

| arm | role | reverse-level evaluation order |
|---|---|---|
| `finest_to_coarsest` | incumbent | current order: nearest coarser level first |
| `coarsest_to_finest` | candidate | same levels in the opposite order: coarsest first |

Both arms use fixed `delta = 1`. After a forward refinement level is accepted,
both arms must generate the identical ordered list of
`(coarse_step, coarse_micro_steps)` pairs using the current repeated arithmetic:
start from the accepted `step` and `micro_steps`, then repeatedly execute
`coarse_steps /= 2` and `coarse_step *= 2.0` while the next level is permitted.
No direct power, division from the original step, reassociation, cached
trajectory, changed integrator, changed validity test, or changed energy test
is allowed. The incumbent evaluates that generated list in generation order;
the candidate evaluates the same list in reverse order.

In either arm, evaluation short-circuits. The first reverse attempt whose
endpoint error is accepted by the current `endpoint_error <= delta` predicate
rejects the forward leaf as `ReverseCoarserAccepted`. The first invalid reverse
attempt also rejects the leaf through the current invalid-evaluation path.
Only if every evaluated reverse attempt is valid and rejected by the
reverse-acceptance predicate is the forward leaf retained. The candidate may
save work only by encountering a rejecting condition earlier in the same
precomputed level list.

The candidate must initially be exposed only through an explicitly named
research option. Existing `walnutpie::KernelOptions::default()`,
`walnutpie::RunConfig`, registered replay/fingerprint paths, and
`walnutpie::ALGORITHM_REVISION =
"walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10"` remain unchanged.
Candidate evidence carries a separate WP37B implementation identifier. No
implementation is present in this scaffold.

## Semantic qualification and its limit

For a deterministic target, when all reverse attempts reached by either order
are valid, the two arms evaluate the same mathematical OR over the same
coarse-level set. Therefore the accepted endpoint, leaf accepted/rejected
boolean, sampler RNG evolution, adaptation evolution, and retained draws are
order-independent; only reverse work, visited reverse energies, and which
accepted reverse level is encountered first may differ.

That statement is deliberately not universal bit identity. If the same level
set contains both an accepted reverse attempt and an invalid reverse attempt,
the first one encountered can change the rejection cause and the public
target-error path. Floating-point target implementations are also qualified
only on the fixed builds below. Consequently the evidence must independently
prove exact semantic hashes, exact stop/rejection sequences, exact forward-call
identity, and no invalid/health regression. A mixed accepted-plus-invalid case
that changes cause or public error fails the study even if retained summaries
look equivalent.

## Common sampler settings

Every target uses four chains and the current high-level sampler defaults made
explicit rather than inherited:

- `h0 = 0.5`, maximum tree depth 10, one minimum micro-step, eight refinement
  levels, fixed `delta = 1`, divergence threshold 1000, and
  `UTurnRule::MomentumSum`;
- retained exhaustion `ExhaustionRule::Stop`;
- `Adaptation::DualAveraging { target_accept: 0.8 }`, adapted diagonal metric
  from identity, `DiagonalMetricRegularization::Stan`, and warmup
  `ExhaustionRule::AcceptUnlessDivergent`;
- `DEFAULT_CHAIN_RESCUE = None`, asserted and serialized; no explicit rescue;
- cached initial evaluation through the high-level `Sampler` boundary and
  `Limits::admit_worst_case()`;
- four sampler threads, except that the qualified Windows BridgeStan backend
  has one effective serialized native worker.

The reverse order is the only arm difference. The harness must assert and
serialize every effective setting and both arms' configuration fingerprints
before evidence. No arm may inherit a later default.

## Frozen targets and run lengths

The ordered target manifest is:

1. `posteriordb_accel_gp`:
   `mcycle_gp-accel_gp`;
2. `posteriordb_gp_pois_regr`:
   `gp_pois_regr-gp_pois_regr`;
3. `posteriordb_eight_schools_centered`:
   `eight_schools-eight_schools_centered`;
4. `posteriordb_eight_schools_noncentered`:
   `eight_schools-eight_schools_noncentered`;
5. `neal_funnel_10d`, the pure-Rust Neal funnel;
6. `gaussian_100d`, the pure-Rust standard Gaussian;
7. `state_space_sspd11_t1000`, the pure-Rust
   `polyscope-canonical-v2` `sspd-11` fixture at `T = 1000`.

The four posteriordb targets use repository commit
`28f8d3d6e975315f42aa274a8399f21e07a43b30`, the WP35 model/data definitions,
`Init::uniform()` shared across arms, and 1,000 warmup plus 1,000 retained
transitions. Models are compiled without `STAN_THREADS` through the current
Windows owned-worker backend. Four replicas are requested, one
`Execution::OwnedSerialised` worker is effective, and the process-global native
mutex is required. The pre-evidence provenance record must freeze SHA-256 and
byte length for every Stan source, data JSON, compiled model library, BridgeStan
library, and runtime dependency; a mismatch makes the cell unauthenticated.

The pure-Rust Neal funnel is 10-dimensional:
`omega ~ Normal(0, 3)` and nine
`x_i | omega ~ Normal(0, exp(omega / 2))`. Its four fixed starts have
`omega in {-3, -1, 1, 3}` and every `x_i = 0`. Each cell runs 2,000 warmup and
20,000 retained transitions.

The pure-Rust Gaussian is the 100-dimensional standard Gaussian with
`Init::uniform()` (`uniform(-2, 2)`) shared across arms. Each cell runs 1,000
warmup and 1,000 retained transitions.

The state-space target copies the canonical `polyscope-canonical-v2` target,
centeredness `a = 1`, parity oracle SHA-256
`4c91f5fddda2e15f42e4209343ee9234bdab866a32918c260fe29fd6b0cf7d0c`, and
fixture
`sspd-11-n1000-mixed-regular-moderate-h1-none-none-cold.json`, SHA-256
`2fff97663b6e7946e64e465610ebf9dd4350d6615ecaa5aa513ff070b683baad`.
Its four seed-independent starts use the fixture's `initial_innovations`,
`mu` offsets `[-0.03, -0.01, 0.01, 0.03]`, zero sigma offsets, and do not
apply the fixture's cold-initialization factor. Each cell runs 500 warmup and
2,000 retained transitions.

## Fresh paired seeds and exact manifest

The contiguous fresh evidence range is **96101 through 96106**, with no skipped
numbers. Every target uses all six seeds and both arms. Before this scaffold
was written, this standalone whole-number search was run against every tracked
file at baseline `a630e04151842cf7a92131dcadd8e9412c675f5b`, including all
tracked artifact trees:

```powershell
$pattern = '(?<![0-9A-Za-z_.])(?:96101|96102|96103|96104|96105|96106)(?![0-9A-Za-z_.])'
git grep -n -P $pattern HEAD -- .
```

Result: **no matches**. The lookarounds exclude a digit sequence embedded in a
longer integer, decimal, exponent, identifier, or hexadecimal checksum.

There are exactly **84 one-shot cells**:
7 targets x 6 seeds x 2 arms. Targets use the order above and seeds ascend.
For zero-based even seed indices the arm order is
`finest_to_coarsest,coarsest_to_finest`; for odd seed indices it is
`coarsest_to_finest,finest_to_coarsest`. `protocol.json` freezes the complete
ordered 84-cell ID list. The same four initial positions and chain seeds are
used in paired arms.

## Identity and required telemetry

Every chain produces a SHA-256 semantic digest with ASCII domain separator
`owalnuts.reverse_coarsening_order_v1.semantic.v1`, canonical length-delimited
little-endian encoding, and IEEE-754 values encoded with `f64::to_bits()`.
The digest includes:

- target/configuration identity, evidence seed, chain index, and exact initial
  unconstrained position bits;
- every retained unconstrained draw bit pattern and, for posteriordb, every
  retained constrained/reference-parameter bit pattern;
- for every warmup and retained transition, phase/index, selection result and
  selected-state bits, orbit direction/depth/leaf-selection trace, and sampler
  RNG state or an exact digest before and after the transition;
- every adaptation input/output, dual-averaging state, warmup-window boundary
  and metric installation, plus final tuning and metric bits.

The semantic digest excludes reverse-work counters, the order/list of visited
reverse levels, reverse-only energy extrema/traces, and stop/rejection/cause
fields. Those exclusions permit the intended work change; they are not ignored
semantics. Each paired cell must separately have:

1. exact equality of all four chain semantic digests;
2. exact equality of the canonical per-chain, per-transition stop and
   leaf-rejection sequence over warmup and retention, including public
   sampler/target error identity;
3. exact forward-call identity: a domain-separated digest over every forward
   target call's phase, chain, transition, leaf/step indices, unconstrained
   input bits, and returned log-density/gradient/error bits, plus exact forward
   call counts;
4. matching initial-position hashes and effective configurations.

Per cell and phase, report forward calls, reverse calls, total calls, attempted
and executed reverse micro-steps, generated and visited reverse-level
histograms, first-rejecting level/cause, forward/reverse invalid evaluations,
all stop/rejection counts, divergences, refinement exhaustions, maximum-depth
stops, nonfinite results, sampler/public target errors, final step/metric, and
wall duration.

## Process, provenance, and one-shot contract

Every planned cell runs in a fresh child process. Before launch, the parent
atomically creates an exclusive create-new marker keyed by target, seed, and
arm. A marker or process record permanently forbids a second launch. The child
atomically writes, flushes, and renames its raw result before teardown. The
parent durably records command, timestamps, PID/start time, stdout/stderr and
their hashes, timeout state, signed/unsigned/hex exit status, raw-result state
and SHA-256. A nonzero exit after a complete raw result is still a process
failure. A successfully returned sampler error is a valid failing result.

There are no reruns, replacement seeds, or result-driven exclusions. A timeout,
crash, setup error, malformed/missing result, authentication mismatch, identity
mismatch, or implementation defect discovered after the first evidence launch
makes the study fail; evidence is not deleted or replaced.

Before the first evidence launch, a committed provenance record must bind:

- source baseline, preregistration, protocol, candidate/harness source commit
  and tree, complete release binary, `Cargo.lock`, and toolchain hashes;
- normalized SHA-256 of the two frozen protocol files, ordered manifest and
  serialized effective target/arm configurations;
- `rustc -Vv`, Cargo/profile/features, OS/build/CPU metadata, and dependency
  versions;
- posteriordb checkout commit/tree and SHA-256/byte length for all four external
  Stan sources, data JSON files, compiled model libraries, BridgeStan runtime
  and native dependencies;
- state-space target/oracle/fixture/start hashes and pure-target implementation
  hashes.

Evidence outputs are append-only. All **84** launch, process, raw, and
authentication records must be present and valid. There is no minimum-valid
subset.

## Frozen gates

All gates are conjunctive and use all 84 planned cells.

### M — semantic and safety gates

**M1 completeness/authentication.** All 84 cells are launched exactly once,
exit successfully, publish complete finite schema-valid raw results, and match
the frozen manifest, binary, model, data, target, and configuration hashes.

**M2 identity.** Every paired cell passes semantic-digest equality, exact
stop/rejection-sequence equality, exact public-error identity, exact
forward-call digest/count equality, and initial-position/configuration
identity.

**M3 no health or invalid regression.** The candidate introduces no process,
sampler, public-target, nonfinite, divergence, invalid-evaluation/invalid-stop,
or refinement-exhaustion event absent from its paired incumbent chain and
transition. For every cell and phase, candidate invalid-evaluation and health
counts are no greater than the incumbent's. Candidate target/global sums are
also no greater. All stop and health statistics are reported even though M2
normally makes their semantic counts identical.

### E — work gates

Let a phase be `warmup` or `retained`; `total_calls = forward_calls +
reverse_calls`, using callbacks actually started. Every comparison is paired by
target and seed and sums all four chains.

**E1 cell/phase nonincrease.** In every one of the 84 paired-cell phases, the
candidate has both reverse calls no greater than the incumbent and total calls
no greater than the incumbent.

**E2 strict global saving.** Summed over all targets, seeds, chains, and both
phases, candidate reverse calls are strictly lower and candidate total calls
are strictly lower. The incumbent global reverse-call sum must be positive, and
`candidate_reverse_calls / incumbent_reverse_calls <= 0.95`.

**E3 target nonincrease.** For each of the seven targets, candidate reverse and
total calls, summed across all six seeds and both phases, are each no greater
than the incumbent values. Warmup and retained target subtotals are also
reported.

Wall time, ESS per call, R-hat, ESS, moments, exact funnel/Gaussian quantities,
posteriordb reference agreement, and state-space functionals are descriptive.
They must be reported for all cells but are neither selection variables nor
substitutes for M1–M3 and E1–E3.

## Mechanical decision

If and only if M1–M3 and E1–E3 all pass, the result is
`QUALIFIED_FOR_SEPARATE_HIGH_LEVEL_DEFAULT_IMPLEMENTATION`. That result
authorizes a separate, labelled implementation changing only the high-level
`owalnuts::sampler` default to `CoarsestToFinest`. It must preserve
`walnutpie::KernelOptions::default()`, `RunConfig`, the v10 algorithm revision,
registered walnutpie fingerprints, and walnutpie replay as
`FinestToCoarsest`.

Any failed, incomplete, or inconclusive gate returns
`KEEP_FINEST_TO_COARSEST`. The current order remains the high-level and
walnutpie default, and the candidate remains research-only. This
preregistration itself authorizes no default or production-code change.

## Predictions

1. All deterministic all-valid paths have exact semantic hashes, exact
   stop/rejection sequences, exact forward-call identity, and no health or
   invalid regression.
2. Coarsest-first short-circuiting reduces reverse calls by at least 5%
   globally, never increases reverse or total calls in a cell/phase, and lowers
   both global sums.
3. The largest call reductions occur on `accel_gp`, `gp_pois_regr`, and the two
   Eight Schools targets; no target aggregate increases.
4. The predicted mechanical result is
   `QUALIFIED_FOR_SEPARATE_HIGH_LEVEL_DEFAULT_IMPLEMENTATION`. This prediction
   weakens no gate and authorizes nothing before the frozen evidence result.
