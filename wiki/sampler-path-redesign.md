# Sampler-path redesign: mutable structured metrics

## Existing fixed structured-coordinate path

`sample_chains_structured` currently implements a fixed metric by changing
coordinates.  For block Cholesky factor `L` with momentum covariance
`M = L L'`, it maps the user's position to

`z = L' q`,

runs the diagonal kernel with identity mass, and maps every retained state back
with

`q = L^{-T} z`.

`StructuredCoordinates` evaluates the target at `q = L^{-T} z` and returns the
chain-rule gradient `L^{-1} grad_q log pi(q)`.  Thus identity dynamics in `z`
are exactly the fixed-metric Hamiltonian dynamics in `q`.  The same wrapper
pattern is used by the dense and block-dense facades.

This construction is correct only while `L` is fixed.  Replacing `L` while
retaining the same numeric `z` changes physical state to `L_new^{-T} z`.
Preserving state would require the exact boundary remap

`z_new = L_new' L_old^{-T} z_old`.

That remap is avoidable and creates extra roundoff, allocation, observer
coordinate ambiguity, and cached-target-state hazards.

## Required architecture

The mutable path remains in original user coordinates `q`.  The private kernel
accepts an immutable `MassOperator` for one complete transition:

* `dimension()`
* `sample_momentum(rng, out)`, producing `p ~ N(0, M)`
* `velocity(p, out)`, producing `M^-1 p`
* `kinetic_energy(p)`, producing `p' M^-1 p / 2`

Leapfrog drift uses `velocity`.  Hamiltonian calculations use
`kinetic_energy`.  Generalized U-turn checks use the endpoint momenta dotted
with `M^-1(q_plus-q_minus)`.  Span construction and all reverse/coarsening
replays receive the same borrowed operator.  The operator cannot be replaced
while a transition is live.

The existing diagonal implementation must retain its present scalar loop
order.  Fixed dense, block-dense, structured-block, and arrowhead facades keep
their public signatures and RNG draw order.  Their old coordinate wrappers
remain as a compatibility oracle until direct-operator golden tests pass; they
are then removed only from mutable paths.

## Boundary installation protocol

Each slow warmup window owns a projected-covariance accumulator.  A transition
returns a complete selected `q` plus its cached `log_prob` and gradient.  Only
after that return:

1. update/finalize the window accumulator;
2. build and validate a `LowRankArrowheadMass` candidate;
3. atomically replace the chain's active mass on successful validation;
4. discard all momentum (momentum never crosses transitions);
5. retain `q`, `log_prob`, and `grad` unchanged;
6. optionally run bounded initial-step search with fresh momentum;
7. restart dual averaging and emit one boundary telemetry event.

Failure to construct/factor the candidate leaves the previous mass installed
and emits a typed fallback.  No RNG is consumed by covariance collection,
candidate construction, fallback, telemetry, or preflight.

Terminal fast warmup and retained sampling do not update the metric.  The
active metric is frozen before the first retained transition.

## Projected covariance

The structured adaptation configuration explicitly supplies:

* global coordinate indices (bounded by `MAX_GLOBAL_DIMENSION`);
* one structured path block and its coordinate range;
* a bounded projection basis/rank (bounded by `MAX_RANK`);
* regularization, conditioning, and minimum-window-sample policy;
* per-chain or shared installation policy.

Online Welford statistics are collected only for the global coordinates and
the configured low-dimensional path projections.  Candidate construction
regularizes the global covariance, path factor parameters, and projected
cross-covariance, then forms the arrowhead Cholesky representation.  Every
finite/shape/SPD/resource check occurs before installation.

Shared adaptation is deterministic: chains collect independently; the
coordinator merges accumulators in ascending chain index at a common window
barrier, installs one cloned metric for every chain, and releases the next
window.  Per-chain adaptation never shares mutable metric state.

## Accounting and controls

Preflight computes checked bounds for projected accumulators, candidate and
active factors, per-chain/shared telemetry, momentum/velocity scratch, and
window barriers before any target callback.  Zero-transition and rejected
configurations invoke zero target callbacks.

Work totals preserve the existing meanings.  Momentum refreshes and standard
normal components count only actual transition/search refreshes.  Metric
updates separately report sample count, candidate outcome, ridge/shrinkage,
condition estimate, factorization failures, installation generation, sharing
mode, step-search work, and dual-averaging restart state.

### Selected-subspace path factor

Let `M_path = P P'`, define base-whitened path coordinates `y = P' q_path`,
and choose Euclidean-orthonormal columns `V` in y-space. The equivalent raw-q
projection basis is `B = P V`, with the coordinate-invariant identity

`B' M_path^-1 B = V' P' (P P')^-1 P V = V' V = I`.

The generalized arrowhead factor is

`L = [[G, 0], [P U C', P Q]]`,

where `Q = I + V (S-I) V'`, and `S` is bounded, finite, lower triangular with
positive diagonal. Thus `Q` is identity on the orthogonal complement of
`span(V)` and is invertible exactly when `S` is. Multiplication and triangular
solves require O(T r + r^2) work:

* `Q x = x + V (S-I) V' x`;
* `Q^-1 x = x + V (S^-1-I) V' x`;
* `Q^-T x = x + V (S^-T-I) V' x`.

Momentum sampling applies `L` to independent standard normals. Velocity first
solves `L z=p`, then `L' v=z`; kinetic energy remains `p'v/2`. The determinant
is `det(G) det(P) det(S)`, although fixed Euclidean HMC does not require it.
The legacy constructor stores no selected-subspace factor and retains its
original arithmetic/fingerprint.

Cancellation/deadline checks occur before collection finalization, before and
after candidate construction, before installation, and at the existing
transition checkpoints.  Cancellation cannot expose partial output or a
partially installed shared generation.

## Regression gates

Implementation proceeds only with tests covering:

1. fixed-path golden traces and bit identity for every existing facade;
2. operator algebra against dense references;
3. leapfrog reversibility and Gaussian stationary moments for each fixed
   window;
4. immutable operator generation throughout a transition;
5. exact `q`/target-cache invariance at installation;
6. sequential/parallel and per-chain/shared determinism;
7. SPD/resource/fallback and zero-callback preflight behavior;
8. dual-averaging restart, work, and RNG accounting;
9. cancellation and target-budget boundaries;
10. public API compile coverage.

Synthetic rank-two Gaussian experiments are diagnostics, not evidence.  They
must report seeds, dimensions, windows, installed rank, moment error and work;
the `T=1000` experiment remains disabled until all gates above pass.
