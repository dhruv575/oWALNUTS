# Performance audit — 2026-11-01

Source checkpoint: `acea9c8a7ff77cf41c2142fdd6a5d716ae2146de`.

Audit only: no sampler, integration, or study implementation was changed. The existing edit to `STUDIES/options_flow_v1/endpoint_exact_controls.py` was preserved. Reviewed the Rust integration hot path, state ownership, mass operators, diagnostics, Python and BridgeStan boundaries, autodiff tape, and current pendulum/spatial study paths. This is targeted source inspection plus baseline measurements, not an exhaustive profile of every historical study or native dependency.

## Findings and priority

Priority means recommended implementation order, not measured speedup. The allocation/copy sites below are source-confirmed; their individual runtime shares remain to be measured.

| Priority | Finding | Best application | Risk / effort |
|---|---|---|---|
| 1 | Non-diagonal metrics allocate inside integration | Dense, block, structured and arrowhead sampling | Medium |
| 1 | ESS allocates a temporary vector per evaluated lag; summaries repeat sorting | Diagnostics and large research outputs | Low–medium |
| 1 | Research instrumentation copies momentum on every evaluation | Research-feature builds | Medium; preserve observers |
| 2 | Small reverse schedules and four telemetry vectors allocate repeatedly | Cheap-target kernel overhead | Low–medium |
| 2 | Selected state is copied through overlapping ownership layers | Cheap targets / large parameter vectors | Medium |
| 2 | Pendulum prediction computes unused sensitivities and crosses Python per draw | Physics workflow postprocessing | Medium |
| 2 | Diagnostics materialize a full transposed sample copy | High-dimensional, many-draw output | Medium |
| 3 | Rc state ring could become an indexed arena | Cheap targets and memory locality | High |
| 3 | Autodiff node layout can be made more compact | Scalar-heavy native autodiff models | High; profile first |
| Conditional | Python callbacks copy and acquire Python runtime access per evaluation | Python-callable targets only | API/lifetime-sensitive |
| Conditional | Spatial GP dense factorization dominates scaling | Spatial model evaluation | Algorithmic; preserve target |
| Low | Bitset conversion and replacing module-registry hash maps | Little demonstrated benefit here | Defer |

## 1. Make metric application allocation-free

Locations: `src/kernel.rs:199,3973`; `src/walnutpie.rs:4511,4538,4552,4647,4683,4944,4977,5335`.

The integrator calls `MassOperator::velocity_into` each micro-step. Its default implementation allocates through `velocity()` and then copies into the already-allocated destination. The diagonal implementation overrides it; `DenseMass`, `BlockDiagonalMass`, `StructuredBlockMass`, and `LowRankArrowheadMass` do not.

There is additional work beyond that default: dense kinetic energy collects a velocity vector just to take its dot product; block drift allocates a combined output plus each block output; structured drift allocates lower/upper-solve intermediates; arrowhead drift constructs several temporary vectors. Kinetic energy runs after integration steps, so these are repeated operations, not merely setup allocations.

Recommended design: internal checked `*_into` methods with explicitly owned metric scratch storage; write block results into destination slices; calculate dense kinetic energy from row dot products without collecting a velocity vector. Preserve row and outer summation order. Retain the allocating public convenience methods as wrappers if API compatibility requires them. Merely overriding `velocity_into` while leaving allocating solves underneath is insufficient.

Measure dense/structured/arrowhead allocations per micro-step and representative dimension scaling. The existing `kernel_bench` uses diagonal mass and therefore does **not** measure this finding. `examples/structured_metric_benchmark.rs` is a useful starting point, but compares different metric representations rather than a before/after implementation of the same representation.

## 2. Remove work inside diagnostics, not diagnostic checks

Locations: `src/diagnostics.rs:71,98,357,388,506`.

`ess_raw` computes each lag mean by collecting `acov.iter().map(|row| row[lag])` into a fresh vector and immediately passing it to `mean_slice`. The mean implementation is just an ordered sum divided by length. An iterator sum in the same chain order removes this allocation without changing the statistical estimator. There is one allocation per requested lag, not necessarily every possible lag: Geyer's stopping rule can stop early.

`ParameterSummary::compute` independently calls quantile for the three reported probabilities. Each call pools and sorts the same data. Tail ESS also requires quantiles; rank/folded diagnostics perform further related transformations. Build a scoped summary workspace, sort pooled values once for compatible quantile requests, and reuse FFT scratch buffers across serial computations. Preserve tie handling, interpolation, normalization, constant-chain behavior, and the distinction between rank/folded/raw series. Do not reuse a transformed series for an estimator that requires a different one.

This is common-subexpression elimination within a computation, not a persistent memoization cache. Verify against `tests/diagnostics_arviz.rs` and existing edge-case tests; benchmark summary time separately from sampling.

## 3. Research-feature instrumentation is on the hot path

Locations: `src/kernel.rs:179,3991`; compare `ContextKineticScope` at `src/kernel.rs:143`.

With the `research` feature, each integration evaluation invokes `set_evaluation_momentum`, which replaces the stored value with `Some(momentum.to_vec())`. This allocates and copies a dimension-sized vector even though that call site does not check whether a momentum observer is active. The kinetic-context path already has an observation scope that avoids unnecessary work.

Recommended design: an explicit observer lifetime/scope that enables momentum capture only when required; when required, overwrite an owned buffer with sufficient capacity. Audit all context consumers, nesting, early returns and thread-local cleanup before changing this. Never silently remove evidence from a conformance experiment. Benchmark feature-enabled builds both with observers absent and present, and retain identical trajectories and required trace contents.

## 4. Small vectors: target schedules and telemetry first

Locations: `src/kernel.rs:794,2130,3511,3646`.

Every `TransitionWorkTelemetry::for_tuning` eagerly creates four heap-backed histogram vectors, reserving up to eight levels. These are good candidates for inline capacity with an overflow path, or internal fixed common-case storage converted at the public boundary. Do not silently cap valid tuning or truncate telemetry.

`generate_reverse_schedule` allocates a vector with capacity equal to the accepted refinement level. For the incumbent finest-to-coarsest branch, the schedule is generated and then the arithmetic is repeated by the original loop; the reverse traversal branch consumes the list. Research builds also record the schedule. In a non-recording incumbent path, eliminate the materialized schedule altogether. Where the list is needed, inline storage is plausible.

Preserve the existing repeated arithmetic: replacing repeated doubling/halving with a formula can change floating-point behavior. Tests must cover both traversal policies, high refinement counts, reverse rejection, RNG consumption and research observations. Inline capacity should follow observed distributions; it is not a guarantee of stack residency when the enclosing object itself is heap allocated.

## 5. Consolidate selected-state ownership

Locations: `src/kernel.rs:434,461,3274`; `src/walnutpie.rs:9915`.

The ring retains a strong `Rc` for pooled states. `take_selected` drops endpoint references and tries to unwrap the selected state, but for ring-retained states the ring reference remains, so it must clone theta and gradient. The sampler subsequently clones `result.selected` into its persistent state and moves its theta into `position`; gradient adaptation can make another gradient clone.

Recommended design: one chain-owned current theta/gradient/log-density record, with borrowed views for transition input and adaptation. Copy only when a retained sample or independently lived observation needs ownership. Reuse output capacity where an owning copy is necessary. First eliminate the duplicate chain-current-state representation; this is smaller and easier to review than replacing the whole tree.

Keep the valid current target evaluation. The existing test at `src/kernel.rs:5089` checks equal selected results/RNG consumption and one fewer target call for the cached path. Deleting that evaluation would deliberately repeat expensive work. Renaming it to current-state evaluation and making ownership explicit better addresses the design concern than deleting it.

## 6. Pendulum: avoid calculating derivatives for predictions

Locations: `STUDIES/physics_pendulum_v1/pendulum.cpp:7,15,61`; `backend.py:44`; `worker.py:79`; corresponding precision-followup copies.

The six-component RK4 state contains angle, angular velocity, and four sensitivity components. `predict` uses the same solver as gradient evaluation but only returns angle. A two-component prediction-only RK4 path can avoid sensitivity arithmetic. The Python worker also calls `Backend.predict` once per posterior draw, allocating and crossing ctypes each time. A bounded native batch interface can fill one output array, amortizing that boundary.

The gradient evaluator already uses fixed-size stack arrays; replacing its small lists is not the missing optimization. Keep its sensitivity solver for gradients. Validate prediction-only results against the original implementation, analytic linear solutions, and the independent numerical checks in `prepare.py`. Preserve timestep rules and batch ordering. Update maintained study templates prospectively; do not rewrite archived evidence or frozen source hashes.

The precision-study median postprocess time is approximately 1.26 seconds for each sampler, but this also includes diagnostics and serialization. It is **not** all prediction time, so no whole-workflow speedup can be claimed yet.

## 7. Use different layouts for sampling and diagnostics

Locations: `src/diagnostics.rs:1292,1365`; `integrations/python/src/lib.rs:1094,2091,2152`.

Samples are already stored flat per chain, with each draw's parameter vector contiguous. That is a sensible layout for recording full sampler states. Rust summary construction transposes the full dataset into parameter/chain vectors. Python summary processes one parameter at a time, but Python chain warnings builds another full three-dimensional collection. Export also concatenates chain sample buffers into a NumPy-owned flat buffer.

At 4 chains × 2,000 draws × 205 parameters, one full f64 payload is 13,120,000 bytes (12.51 MiB), excluding vector metadata and temporaries. This is a calculated size, not a measured peak RSS.

Recommended design: a parameter-at-a-time diagnostic workspace; accumulate per-parameter disagreement results rather than requiring the complete transpose. For NumPy export, consider an output ownership API that can transfer an already-contiguous run buffer. The current concatenation copy cannot disappear merely by changing a container name: source chains own separate buffers. Do not transpose the sampler's hot state just to optimize postprocessing, or expose unsafe borrowed arrays that outlive Rust storage.

## 8. Indexed state arena: promising, larger rewrite

Locations: `src/types.rs:15`; `src/kernel.rs:358,372,434,477,496`.

The state ring scans entries for unique ownership, touches reference counts, and follows an Rc pointer plus three vector allocations per state. An arena with compact slot indices, a free list, and contiguous theta/rho/gradient storage could improve locality and remove the scan/refcount machinery. Use generation/lifetime discipline or equivalent checked ownership to prevent references to reused slots.

This is where the user's flat-array/index idea fits much better than replacing unrelated hash maps. Size the arena by simultaneously live state requirements and support overflow safely. Keep the current bounded retention behavior in mind; alternating dimensions can also retain mismatched buffers. Benchmark recursion/depth extremes, multiple chains and dimensions, cancellation, and memory peaks. Avoid large inline parameter arrays inside recursively live spans: that can inflate every frame and worsen stack use.

Start with plain indices. Packing tags into high bits reduces representable capacity and adds decoding; adopt it only after explicit range checks, measured layout savings and overflow tests.

## 9. Autodiff already incorporates much of this advice

Locations: `integrations/autodiff/src/tape.rs:23,54,87`; `integrations/autodiff/src/operand.rs`.

The tape already uses u32 indices, separate adjoints/partials/index buffers, reusable capacity, contiguous segments and fused vector primitives. There is no per-operation allocation after capacity growth. Preserve these strengths.

Remaining hypothesis: `Vec<Node>` is a tagged enum whose element layout must accommodate the largest variant, while Unary, Filler and Nary payloads are smaller. Investigate node-kind histograms and `size_of` on actual build targets before splitting opcodes/operands/partials into separate streams. Block cumsum uses Filler nodes for intermediate outputs; a compact output-range representation may save traffic. More streams can also make scalar reverse sweeps slower, so a full SoA conversion is not automatically better.

`Segment` has three u32 fields and a boolean. A tag in an index could reduce padding on some layouts, but index-range reduction and overflow checks are required. This is lower priority than removing known per-step allocations. No layout size or speedup was measured in this audit.

## 10. Python and BridgeStan boundaries

Locations: `integrations/python/src/lib.rs:240`; `integrations/bridgestan/src/lib.rs:174,598,1112`.

The Python-callable path attaches to Python, creates an input NumPy array, calls Python, and copies the gradient back each evaluation. Use the existing native target route for cheap benchmark/research targets when available. A reusable mutable Python input buffer would change callback ownership semantics if user code retains the array; it is not a safe drop-in optimization. A new explicit in-place callback contract would need separate design and tests.

The hash maps found in the reviewed Rust integrations are BridgeStan module/library registries keyed by paths, not tree traversal tables. Flat-array replacement has little justification without profiling module startup. BridgeStan chooses unlocked evaluation for concurrent builds and a lock for serialized builds. Do not remove the lock as a performance shortcut: it encodes the model's threading requirement. Likewise resident-library and replica caches manage module lifetime/isolation, not merely avoid a cheap calculation.

## 11. Spatial GP: separate layout work from target complexity

Locations: `STUDIES/usefulness_search_v1/spatial_counts_v1/spatial_gp.stan:18`; `audit_spatial_reference.py:57`.

The model constructs a dense covariance and computes its Cholesky factor at each target position; rho and alpha vary with the state. A persistent cache keyed only by fixed observation coordinates would not make the varying factor valid. The transform path also reconstructs physical functionals for each retained draw.

Potential exact optimization: represent fixed pairwise distances once as immutable model data, then construct each covariance from that data; benchmark against Stan's existing GP implementation before adopting it. Batch functional extraction where feasible, but factorization still depends on each draw. Sparse/low-rank GP variants are separate statistical models or approximations and require a new fidelity study; they are not transparent layout improvements.

## Advice that should not be applied mechanically

* **Bitsets:** `src/walnutpie.rs:13313,13495` contains per-chain rescue boolean flags. These scale with chain count, not trajectory length or parameter count. Packing a handful of flags is low value; keep clarity unless unusually large chain ensembles demonstrate a problem.
* **Delete all caches:** eliminate unnecessary materialization and duplicate ownership first. Keep valid current evaluations, workspace capacity, autodiff arenas and native library lifetime management. Redesign implicit thread-local scratch as explicit run/chain-owned storage where useful; freeing it every call recreates the cost.
* **SoA everywhere:** state coordinate vectors, flat samples and autodiff buffers already use contiguous numeric arrays. Choose layout for the loop that consumes it. An AoS of tiny scalar records can be appropriate when every field is consumed together.
* **Pack every index:** explicit bounded indices and well-defined lifetimes first; bit packing only with measured savings and enforced limits.

## Measurements and interpretation

Artifacts: `performance-audit-20261101/` contains raw benchmark stdout/build logs, environment details, and a reproducible extraction of existing physics costs. Baseline `kernel_bench` is single-threaded, fixed-seed, includes a counting allocator and selects the fastest of three repeats. Its target-cost estimate is measured separately at a probe point, so derived overhead is an approximation, not a profiler attribution. Allocation totals include the benchmark's whole sampling call, not just leapfrog steps. Allocated bytes are cumulative allocation traffic, not live memory.

The first successful two-repeat run produced 27.3 / 40.0 / 37.3 ms for funnel-10d / Gaussian-100d / Eight Schools. The persisted three-repeat run produced 32.3 / 43.3 / 40.5 ms, illustrating local timing noise. Both had the same allocations per call (0.24 / 0.56 / 1.27), bytes per call (25.9 / 283.5 / 2596.9), target counts and fingerprints. Do not treat these local millisecond measurements as AWS performance or optimization wins.

The persisted research-feature build produced:

| Workload | Default ms | Research ms | Default allocations/call | Research allocations/call | Research bytes/call |
|---|---:|---:|---:|---:|---:|
| Funnel 10D | 32.3 | 37.0 | 0.24 | 1.39 | 179.2 |
| Gaussian 100D | 43.3 | 48.0 | 0.56 | 1.94 | 1209.5 |
| Eight Schools | 40.5 | 45.3 | 1.27 | 2.66 | 2799.6 |

All three target-call counts and retained-draw fingerprints match between feature modes. This measures the complete feature-mode difference, including schedule/leaf observation plumbing; it does not attribute the entire delta to momentum snapshots. Timings are sequential local baseline runs, not a randomized controlled performance comparison. No optimized implementation was benchmarked.

Existing precision-physics validation, four runs per sampler:

| Median | NUTS | WALNUTS |
|---|---:|---:|
| Sampling seconds | 2.5933 | 3.5362 |
| Target calls | 176,080 | 241,441 |
| Postprocess seconds | 1.2647 | 1.2628 |
| Total seconds | 5.6396 | 6.5582 |

WALNUTS uses about 37% more target calls and 36% more sampling time here. This suggests target-call volume is a major part of the gap; it does not isolate target cost or prove zero kernel overhead. A micro-optimization is not evidence of superior posterior efficiency, decision value, or profitability.

## Recommended implementation sequence and acceptance gates

1. Remove ESS lag temporaries and repeated summary quantile sorting; verify diagnostic equivalence and measure summary latency/allocation traffic.
2. Implement metric output/scratch APIs, starting with dense and block operators; measure identical metrics, dimensions and target trajectories before/after.
3. Make research observations demand-driven; preserve observer evidence and compare both build modes.
4. Remove unnecessary reverse schedule materialization and add inline telemetry storage without changing public output or overflow behavior.
5. Consolidate selected-state ownership; then consider the larger arena rewrite only if profiling still supports it.
6. Add prediction-only/batched pendulum postprocessing as a separately versioned experiment; benchmark it independently and end-to-end.

For arithmetic-preserving changes require matching `tests/kernel_fingerprint.rs` outputs, seeded trajectory/RNG parity, reverse/zero-density behavior and relevant metric/continuation tests. For deliberate arithmetic changes require documented tolerance validation and fresh posterior-quality comparisons; do not silently relax bitwise gates. Benchmark time, allocations, peak memory and target-call counts independently, using repeated matched runs and reporting dispersion. Continue to require R-hat/ESS/MCSE and reference agreement for inference claims. No speedup is demonstrated until an actual before/after implementation passes those gates.
