# Performance implementation — 2026-11-01

This implements the applicable changes from [the audit](PERFORMANCE-AUDIT-20261101.md) and evaluates the speculative candidates. The comparison baseline is Git checkpoint `acea9c8a`. Numerical algorithm settings, target definitions used by existing studies, and archived evidence are preserved. The unrelated options-flow edit is excluded.

## Implemented in the default code paths

* **Metric scratch:** dense and block drift write into existing buffers; dense kinetic energy no longer collects a temporary velocity. Structured solves operate in place. Arrowhead velocity uses explicitly sized scratch slices for global and low-rank intermediates. Integration and its energy observations use those methods. The research metric enum forwards scratch requirements and operations, so direct-coordinate research runs actually use the optimized paths. Public allocating convenience methods remain compatible.
* **Diagnostics:** ESS averages lag covariances without allocating a vector per lag. A summary sorts its pooled quantiles once and shares thresholds with tail ESS. FFT work buffers are reused across chains. Rust summaries and Python chain warnings process one parameter's columns at a time instead of retaining the full transposed dataset. The original public estimators remain available as parity references.
* **Research observations:** scoped requirements avoid collecting momentum, reverse schedules, leaf outcomes, and selected momentum when their observers are absent. Observation-enabled runs preserve capture. Scopes restore previous settings when dropped.
* **Small containers:** reverse schedules and four private telemetry vectors use inline capacity eight with heap overflow. The incumbent reverse traversal does not materialize a schedule when no observer needs one. Repeated-arithmetic order and high-level overflow support remain intact. Container behavior follows [SmallVec's documented inline/overflow semantics](https://docs.rs/smallvec/latest/smallvec/struct.SmallVec.html).
* **State ownership:** cached transition inputs take ownership of theta, momentum and gradient instead of cloning them. The selected gradient moves into the persistent state after any adaptation observation. The state pool uses slot indices and a free list, eliminating the linear scan for reusable states. Compact nonzero slot IDs leave room for the unpooled case. Rc still enforces payload lifetime; a live clone prevents reuse. This deliberately does not introduce unsafe flat-buffer references or claim complete pointer elimination.
* **Physics predictions:** the maintained pendulum source has a two-component prediction-only RK4 solver and a native batch entry point. Python validates batch shape and the worker uses batches. The gradient solver remains unchanged. Existing frozen precision-followup sources/results are not rewritten. Rebuild `pendulum.so` through the normal preparation workflow before using the updated backend.

## Implemented as experiments, not default changes

**Compact autodiff tape.** `integrations/autodiff` has an optional `compact-tape` feature: an operation/index stream with payloads grouped by operation kind, using checked payload indices. It avoids reserving the largest enum payload for every small operation or filler. The default tape is retained because initial model timings were mixed: the candidate improved Funnel and Local Level but regressed Eight Schools. Both variants produced the same three benchmark gradient fingerprints; the compact variant passed the gradient and sampling tests. `examples/layout_bench.rs` makes this tradeoff reproducible. The measurements are local microbenchmarks, not claims about all models or AWS.

**Precomputed spatial distances.** `spatial_gp_precomputed.stan` calculates fixed squared distances in transformed data and constructs each draw's covariance from them. It represents the same mathematical GP target and passed the numerical preflight against the existing compiled model, but was slower in the fixed-point evaluation comparison. It is a separate candidate, not the active model. Cholesky factors still vary with the parameters; no invalid factor memoization was introduced. No new posterior qualification is claimed.

## Reviewed and intentionally retained

* The current target evaluation, reusable scratch capacity, autodiff arena capacity and native-library lifetime/isolation machinery have valid purposes. Deleting them would redo work or weaken lifetime/threading guarantees.
* The reviewed hash maps are module registries, not sampler traversal tables. They remain maps; the hot state pool received the index/free-list redesign instead.
* Rescue booleans scale with the number of chains and remain ordinary flags. No bitset performance case was established.
* Existing native target interfaces already bypass Python callback allocation. Python callback arrays retain their ownership semantics; no unsafe reusable array was substituted for an independently owned callback argument.
* NumPy export already transfers its newly assembled flat buffer to NumPy. Separate Rust chain buffers still require assembly for a single contiguous array. Eliminating that copy would require a broader output ownership/API change with no demonstrated payoff in these measurements.
* A completely flat state arena and packed autodiff operand tags remain unadopted. The implemented index/free-list pool removes scanning while preserving Rust ownership; the optional compact tape tests the data-layout hypothesis without imposing its model-specific regressions on everyone.

## Matched measurements

`performance-audit-20261101/compare.py` builds the same benchmark against the original checkpoint and the implementation, then alternates execution order over four rounds. Each executable warms its workload and emits five measurements per round. Both builds enable `research`, matching the instrumentation comparison. Every before/after fingerprint matches. Counting-allocator overhead is present in both builds. These are local WSL results; other build activity and CPU frequency variation limit timing conclusions.

| Workload | Before allocations | After allocations | Median speed ratio, before / after |
|---|---:|---:|---:|
| Dense-coordinate wrapper, 32D | 79,866 | 53,920 | 1.08× |
| Direct dense metric, 32D | 92,821 | 21,007 | 1.07× |
| Direct structured metric, 32D | 205,360 | 54,653 | 1.23× |
| Correlated-chain parameter summary | 1,046 | 184 | 1.30× |

The direct structured workload allocates about 74% fewer times and moves about 74% fewer cumulative allocated bytes. Summary allocations fall about 82%, and cumulative allocated bytes fall about 34%. These are workload totals, not peak RSS or allocation counts attributed solely to one function. The raw timing ranges overlap; allocation reductions are stronger evidence than a universal speedup claim.

The isolated pendulum checker compares old/new native libraries on 128 parameter draws for both linear and nonlinear dynamics. Predictions and sampled gradient evaluations match bit-for-bit, and independent DOP853 checks pass. The initial batched prediction timings are approximately twice as fast. This excludes sampling and other postprocessing, so it is not a twofold study speedup.

Raw measurements, exact timing ranges, fingerprints and numerical errors are in `performance-audit-20261101/comparison.json`, `pendulum-validation.json`, `spatial-candidate.json`, and the autodiff before/candidate logs. The benchmark programs and comparison scripts are included.

## Validation and operational notes

Completed intermediate validation: 160 core unit tests, ArviZ estimator fixture, all three kernel fingerprint tests, Python integration compilation, and 15 compact-autodiff gradient/sampling tests plus its documentation test. New parity tests cover both structured covariance families, dense/block metrics, arrowhead metrics with and without a path subspace, streaming disagreement diagnostics and summary thresholds. A further state-pool test checks live-clone protection and slot recycling.

Final validation:

* Research-feature full suite (`cargo test --tests --features research --no-fail-fast`): **356 passed, one failed, one ignored** across 23 test targets.
* The failure, `cost_weighted_acceptance::refined_leaves_shrink_the_adapted_step`, also fails on original checkpoint `acea9c8a` with **exactly the same default and cost-weighted step vectors**. It assumes at least three of four chains shrink their adapted step; this seed/platform gives two on both revisions. The test has not been weakened or changed. See `cost-weighted-baseline.log` and `tests-complete-all.log`.
* Default-feature core unit tests, diagnostic fixture and fingerprint tests: **160 passed, zero failed, one ignored**.
* Compact-autodiff: **15 integration tests and one doc test passed**. Default-autodiff also passed the same 15 integration tests and its documentation test.
* Python integration `cargo check` passed; Rust formatting and diff-whitespace checks passed. Native pendulum old/new and independent-solver validation passed. Spatial candidate preflight passed but its performance result was negative.

Windows MSVC linking was unavailable. A superseded full-test build linked extremely slowly on the Windows-mounted directory; final validation uses a Linux-native target directory. This changes build storage, not repository sources or tests. All jobs are local; no AWS capacity, deployments, publications or trading actions were added.

No predictive, posterior-efficiency, decision-value or profitability claim follows from these engineering measurements.
