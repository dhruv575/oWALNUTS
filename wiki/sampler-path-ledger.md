# Mutable structured metric implementation ledger

Status meanings: `done` is merged into the working tree and tested; `blocked`
means a prerequisite regression gate is not yet present; `pending` is
implementation work with a settled design.

| Stage | Status | Deliverable / exit criterion |
|---|---|---|
| 0 | done | Document current `L' q` wrapper, exact remap, and original-`q` design |
| 1 | done | Fixed-path fingerprints lock samples, diagnostics, work and RNG-sensitive counts for identity, diagonal, dense, block, structured full-path and arrowhead operator APIs |
| 2 | done | Private `MassOperator` introduced for diagonal slices/arrays/vectors and all four structured metric representations; every upstream oracle and fixed-path golden passes |
| 3 | done | Mass operator is propagated through macro leaves, spans, recursive orbit construction, traced/untraced transitions, validation, kinetic energy, leapfrog drift and generalized U-turn checks |
| 4 | done | Versioned `DirectOriginalQMass` APIs execute dense, block, structured-path and arrowhead metrics directly in `q`; all legacy wrappers and fingerprints remain unchanged by policy |
| 5 | done | Arrowhead supports efficient bounded selected-subspace `Q`, projected covariance collection, and candidate construction |
| 6 | done | Per-chain boundaries install metrics, preserve the target cache, re-search step size, report telemetry, and restart dual averaging |
| 7 | done | Deterministic shared-metric barrier merges by chain index and installs one generation across sequential or parallel execution |
| 8 | blocked | Complete checked resource admission, zero-callback preflight, controls and budget paths |
| 9 | blocked | Complete reversibility, moments, mutation, invariance, SPD/fallback, accounting, cancellation and API tests |
| 10 | blocked | Run bounded rank-two synthetic Gaussian diagnostics (never `T=1000` in this stage) |

## Baseline

On 2026-08-30, before redesign edits:

* `cargo test`: 120 passed, 0 failed, 1 ignored;
* the working tree already contained extensive uncommitted sampler changes;
* no redesign commit was created.

## 2026-08-30 fixed-core milestone

* Added six deterministic fixed-path fingerprints.
* Added coupled-metric original-`q` leapfrog reversibility/generation test.
* Added boundary state/cache invariance and zero-work test.
* Added a full coupled-metric transition test locking generation, work and RNG.
* `cargo test`: 124 passed, 0 failed, 1 ignored.
* Strict all-target Clippy initially found only hexadecimal grouping in the new
  test seed; corrected before the milestone was closed.

## 2026-08-30 original-q driver milestone

* Added object-safe metric-specific momentum refresh to `MassOperator`.
* Added a fixed original-`q` driver reusing existing state caching, warmup,
  retained, control, tracing, telemetry and accounting loops.
* Routed exact identity `DenseMass` through the direct driver and proved
  samples, diagnostics and telemetry bit-identical to the diagonal facade.
* A trial nonidentity dense migration changed its locked fingerprint because
  direct `q += epsilon M^-1 p` and the legacy `L' q` wrapper perform
  mathematically equivalent floating-point operations in different orders.
  The trial was reverted; its wrapper remains until compatibility policy
  explicitly permits that numerical fingerprint change.

## 2026-08-30 versioned direct API milestone

* Compatibility policy changed: legacy fixed APIs remain wrapper-based and
  bit-stable; direct execution has `DIRECT_ORIGINAL_Q_REVISION`.
* Added single-chain, controlled, multichain, preflight and explicitly
  budgeted direct-original-q entry points.
* Established independent deterministic fingerprints for dense, block,
  structured-path and low-rank arrowhead direct execution.
* Direct runs invoke a no-op installation seam at warmup/window boundaries;
  it retains the same borrowed operator and consumes no RNG, target work or
  telemetry counters.

## 2026-08-30 selected-subspace representation milestone

* Added `LowRankArrowheadMass::new_with_path_subspace`.
* `Q`, `Q^-1`, and `Q^-T` use O(T r + r²) storage/work without a dense path
  matrix.
* Validation requires Euclidean-orthonormal y-space basis columns and a finite
  lower-triangular `S` with positive diagonal.
* The legacy unit-Schur constructor and all old/direct fingerprints remain
  unchanged.

## 2026-08-30 projected warmup diagnostic

* Added a versioned single-chain projected-arrowhead warmup facade with
  Welford accumulation over exactly six leading globals and bounded-rank
  base-whitened path projections.
* Candidate construction deterministically regularizes and inverts the
  selected covariance, lifts its Cholesky factor through
  `new_with_path_subspace`, installs only at completed slow-window boundaries,
  and reports typed installation/fallback telemetry.
* Boundary execution retains numeric `q`, discards momentum between
  transitions, restarts dual averaging after successful nonterminal
  installations, and performs cancellation checks around candidate building.
* This is not yet stage 5/6 completion: boundary step search and the shared
  chain barrier are not implemented, and the segmented driver does not carry a
  target cache between transitions (the current kernel reevaluates each
  transition's initial state).
* Preregistered rank-two diagnostic
  `STUDIES/rank_two_projected_gaussian_v1` installed rank two for all four
  seeds. Geometric ESJD ratio was `1.117667130666921`; lag-one inefficiency
  improvement was `1.821555667693483`. The preregistered health gate failed
  because every pair contained at least one maximum-depth stop. Per protocol,
  no `T=1000` pilot was frozen or sampled.
* Validation after this work: `cargo test` 130 passed, 0 failed, 1 ignored;
  strict all-target/all-feature Clippy passed; `git diff --check` passed apart
  from Git's existing Windows line-ending notices.

## 2026-08-30 persistent single-chain boundary milestone

* Added cached traced and untraced transition entries and a persistent
  single-chain context carrying one `SmallRng` stream and the selected
  position/log-density/gradient cache.
* Projected-arrowhead warmup now uses that context across every warmup and
  retained transition. It performs exactly one initial target evaluation,
  refreshes momentum each transition, preserves the cache when replacing the
  owned active mass at slow-window boundaries, and freezes mass after warmup.
* Legacy and fixed direct APIs do not opt into the cache and retain all locked
  numerical fingerprints.
* Validation: 131 tests passed (one ignored benchmark), strict all-target
  Clippy passed, and diff checking reported only existing Windows line-ending
  notices.
* The unchanged rank-two synthetic gate still failed only its maximum-depth
  health requirement. Geometric ESJD ratio was `1.1634339990539178` and
  lag-one inefficiency improvement was `1.7836738169201478`; all four seeds
  installed a metric. No T=1000 pilot was frozen or executed.
* Boundary reasonable-step search remains the next single-chain item; the
  pooled deterministic multi-chain barrier follows it.

## 2026-08-30 cached boundary-search milestone

* Added a generic structured-metric reasonable-step executor over cached
  `EvaluatedTransitionInput`, `&dyn MassOperator`, persistent `SmallRng`,
  execution control, bounded target calls, proposal observations, and additive
  work accounting.
* Probe momenta are drawn once and reused across candidate steps. The cached
  position log density and gradient are never reevaluated; recoverable target
  failures reject probes while fatal errors, panics, malformed outputs,
  cancellation, deadlines, and observer panics remain structured failures.
* Projected-arrowhead installations now run the executor before restarting
  dual averaging and expose typed `StepSearchEvent` diagnostics. The legacy
  diagonal initial-step adapter remains unchanged to preserve its random and
  floating-point fingerprints.
* Tests: 131 passed, 0 failed, 1 ignored; 37 public-facade tests passed. Strict
  all-target/all-feature Clippy and `git diff --check` passed.
* The versioned rank-two synthetic rerun changed only adaptive boundary
  search. ESJD improved `1.074881054762435` and lag-one inefficiency improved
  `1.7142981657145606`, with metric installation on all seeds. The health gate
  still failed due to maximum-depth stops, so no `T=1000` pilot was frozen or
  run.

## 2026-08-30 pooled multi-chain milestone

* Added `sample_chains_projected_arrowhead`: each chain retains independent
  RNG, evaluated-state cache, step size, dual averaging, and window summary.
  A transition-index barrier completes every chain before fixed chain-order
  Welford merging and one shared metric installation.
* Sequential and bounded-Rayon paths produce identical samples, diagnostics,
  telemetry, shared metric, and per-chain cached boundary searches. Errors set
  the existing lowest-chain cancellation latch and all partial outputs are
  discarded.
* Versioned pooled synthetic artifact `rank_two_projected_gaussian_v2`
  installed every metric and improved geometric ESJD `1.0956681899064264` and
  lag-one inefficiency `1.829257894360377`. It still failed health: adaptive
  maximum-depth counts were 56, 50, 54, and 47 (baseline 116, 115, 134, 124).
  Final steps were 0.739, 0.677, 0.589, and 0.688.
* No `T=1000` pilot was frozen or sampled. The next mechanism is to distinguish
  benign depth saturation from unhealthy trajectory truncation using
  energy-error/U-turn diagnostics before preregistering any depth intervention.

## 2026-08-30 trace-only depth instrumentation

* Public transition diagnostics now retain the final already-executed outer
  U-turn predicate dots, their conservative minimum margin, and physical macro
  trajectory length. Existing depth, stop, Hamiltonian extrema, maximum energy
  error, divergence, leaves, and target-call fields complete the bounded
  fixed-size depth record.
* Instrumentation reads existing traced events only. It performs no shadow
  integration, callback, control check, observer event, or random draw.
* Fresh-seed depth replay 73001--73004 passed exact zero-callback preflight.
  Only 82/234 (`35.04%`) adaptive capped transitions met the preregistered
  finite/nondivergent/energy-tolerance/positive-margin criterion, below 90%.
  Although ESJD improved `1.1679` and lag-one inefficiency `2.0275`, depth+1
  was not supported. No depth-4 or T=1000 execution occurred.

## 2026-08-30 stop-precedence audit

* Both traced and untraced kernels evaluate the generalized outer U-turn
  predicate after every successfully built root, including the final allowed
  depth. Candidate selection occurs before stop classification by design;
  coincident final-depth turns are classified `OuterUTurn`, not
  `MaximumDepth`. Stop causes are mutually exclusive.
* The apparent 35% result was an analysis defect: it counted a conjunction
  including an incorrectly assumed 0.1 energy tolerance (the configured
  tolerance is 1.0), not the U-turn margin alone. Fresh seeds 74001--74004
  showed all 238/238 maximum-depth transitions had nonnegative final margins
  and finite, nondivergent energies. True depth-3 truncation was 12.40%.
* A preregistered fresh-seed depth-4 run reduced adaptive truncation to 38/1920
  (`1.98%`) while retaining ESJD improvement `1.1413` and inefficiency
  improvement `1.7468`. It failed the preregistered <=1% truncation gate, so
  T=1000 remains unauthorized.
* Diagnostic additions versioned legacy, direct-original-q, and projected
  algorithm identifiers. Dynamics, selection, RNG, callbacks, and work did
  not change.

## 2026-08-30 final depth-5 synthetic intervention

* Fresh seeds 76001--76004 passed zero-callback preflight. Adaptive true
  truncation fell to 1/1920 (`0.052%`) and every per-seed rate was <=1%.
* Moment gates passed. Geometric ESJD improved `1.1858` and lag-one
  inefficiency improved `2.0438`.
* Adaptive execution used 13,979 target calls and 13,348 built leaves versus
  baseline 19,369 calls and 17,016 leaves (27.8% and 21.6% less,
  respectively). Depth-4 did not persist these counters, so no fabricated
  cross-artifact work delta is reported.
* Full health failed because at least one transition was divergent. Therefore
  the intervention failed, no T=1000 pilot was frozen, and T=1000 remains
  unauthorized despite passing truncation, moment, and efficiency gates.

## 2026-08-30 divergence ownership replay

* Fresh depth-5 seeds 77001--77004 persisted adaptive and baseline divergence
  traces separately after unchanged-counter preflights. Each arm had four
  divergences: the same chain-local transition 1 in initial-fast warmup,
  before any metric window. Every event stopped by refinement exhaustion at
  depth 1 after two attempts; delta-H ranged from `1.19e3` to `2.68e5`.
  Therefore the prior failure was not baseline-only, boundary search,
  projected adaptation, target nonfinite output, or retained sampling.
* The single preregistered intervention raised target acceptance from 0.8 to
  0.9 at unchanged depth 5. Fresh seeds 78001--78004 still produced three
  identically owned adaptive/baseline transition-1 divergences. Truncation and
  moments passed and efficiency improved, but zero-divergence health failed.
  No further knob or T=1000 run was authorized.

## 2026-08-30 phase-separated health contract

* Health contract `phase-separated-v1` reports warmup and retained failures
  independently. Retained divergences, invalid evaluations and refinement
  exhaustions are fatal; retained truncation is capped at 1%. Initial-fast
  adaptation failures remain visible and bounded but do not silently become
  retained failures.
* Fresh seeds 79001--79004 at the unchanged depth-5/target-acceptance-0.8
  algorithm passed: zero retained divergences, invalid evaluations,
  refinement exhaustions and maximum-depth stops; moments passed; ESJD
  improved `1.0949` and lag-one inefficiency `1.5815`. Each arm retained its
  reported initial-fast divergence ownership.
* A T=1000 pilot was not fabricated: this repository contains no
  T=1000-specific true-cap telemetry or concrete objective rank-two basis and
  resource preflight from which to choose its depth independently. Synthetic
  depth 5 was deliberately not mapped to T=1000.

## 2026-08-30 T=1000 objective basis and preflight

* Deterministically derived the full 2x1000 y-space basis from Hessian
  `904386ca...ce93844` and frozen metric `4b3136f6...c52ccd` using single-thread
  NumPy/LAPACK SVD, stable descending order, and largest-coordinate-positive
  sign canonicalization.
* Basis hash is
  `375ce05fbce1aea4fc79b8bcaaf950f7d04a44737f13ec6e9612e24195ef0f1c`.
  Leading singular values are `19095.467710575605` and
  `1712.2518286690838` (relative second `0.08966797014983774`); remaining
  relative values are below `2.5e-13`. y-space Gram error is `5.55e-16`,
  weighted raw-basis Gram error `1.11e-15`, and full reconstruction residual
  `7.75e-12`.
* Frozen two-seed T=1000 diagnostic uses the existing a=.75 partial-block
  control and pooled rank-two arrowhead at depth 8. Production preflight
  reported dimension 1006, four chains, 18,000 transitions,
  101,018,480 worst-case target callbacks, and zero callbacks started under
  the 113,000,000 admission ceiling. Sampling remains disabled.

## 2026-08-30 NextStat 0.10.1 clean-room study

* Recorded the AGPL-3.0-or-later/commercial boundary, official wheel hash,
  allowed public inputs, and paper/API provenance in
  `wiki/nextstat-0.10.1-clean-room-study.md`. No NextStat implementation source
  was inspected or copied and no sampler source was changed.
* The matched public-API artifacts show that NextStat's advantage is mixed:
  the vendor's published Eight Schools decomposition is about 1.14x
  ESS/leapfrog and an implied 1.78x leapfrogs/s, not a pure sampler or pure
  density-throughput effect.
* A post-hoc, non-evidence public-API rerun of frozen seed 130038102 found
  predominantly negative lag-one functional correlation, explaining bulk ESS
  above 4,000 draws, while tail and squared-functional ESS remained lower.
  Depth was 4 for 86.875% of transitions, no transition reached the depth-8
  cap, E-BFMI was 0.948--1.039, and leapfrog-count serial correlation was
  negligible.
* Betancourt's biased progressive selection is publicly documented and can be
  independently derived. oWALNUTS already uses normalized recursive subtree
  joins and the corresponding biased-progressive outer join, so the smallest
  preregistered experiment is a reverse ablation against normalized outer
  multinomial selection, with tail and squared-functional noninferiority
  gates.
* LAPS means Late-Adjusted Parallel Sampler, a separate many-chain
  MCLMC/MAMS-style algorithm published by Robnik et al.; it is not NUTS
  progressive sampling and is not implicated in the measured `sample_nuts`
  result. No LAPS implementation or expensive evidence run is authorized.

## 2026-08-30 clean-room outer-selection implementation

* Added a research-only outer-orbit policy with exact normalized multinomial
  and existing biased-progressive arms. Recursive subtree selection,
  trajectory construction, stopping, adaptation, callbacks, and production
  default are unchanged.
* The implementation uses log-sum-exp normalization and one uniform draw in
  both arms. Closed-form, deterministic 10,000-point frequency, extreme-weight,
  draw-accounting, and explicit default-bit-identity tests pass alongside the
  existing reversibility, detailed-balance, stationarity, work, and
  sequential/parallel determinism suites.
* Validation: 134 tests passed, 0 failed, 1 ignored. The Eight Schools evidence
  run did not start because no frozen scripted protocol containing starts,
  fresh seeds, common ESS estimators, aggregation, and health/posterior gates
  yet exists. This preserves freeze-before-sampling and leaves the 1.10
  advancement criterion unevaluated.

## 2026-08-30 T=1000 pooled-arrowhead paired diagnostic v2

* The v1 protocol lacked explicit sampler-source hashes. A mechanical v2 rebind
  froze current `walnutpie.rs`, `kernel.rs`, and `Cargo.lock` hashes, retained
  the rank-two basis, arms, settings, caps, and gates, and replaced both seeds.
* Exact production preflight again started zero target callbacks. Both paired
  seeds then ran baseline partial-block and pooled rank-two arrowhead arms.
  Both arms failed the frozen convergence and true-cap gates on both seeds;
  pooled adaptation installed all 4 metric windows without fallback and had no
  divergence, invalid evaluation, or refinement exhaustion.
* The pooled arm's retained true-cap rates were 91.99% and 86.92%, versus
  6.54% and 15.23% for baseline. Worst functional R-hat exceeded 1.5 in every
  arm/seed and minimum bulk ESS was below 9 except pooled `nu` on the second
  seed (169.5). The diagnostic therefore does not robustly qualify and no
  larger confirmation was frozen or executed.

## 2026-08-31 paper adaptation milestone

* Added the opt-in JMLR Appendix C mode `WarmupConfig::with_paper_adaptation`
  (`PaperAdaptationConfig`, revision
  `walnutpie-paper-adaptation-kquantile-gamma-v1`): K-quantile `delta` rule
  at the initial-fast boundary and nonterminal slow-window ends, and
  `Gamma`-targeted dual averaging of `h` on the per-transition unrefined
  macro-leaf fraction (`refinement_level_attempts[0] - [1]`, over `[0]`).
  Dual averaging restarts after each `delta` or mass installation.
* Orbit energy range uses the transition's `H_max - H_min` over accepted
  leaves plus invalid/exhausted attempts; refined-away coarse attempts and
  valid reverse coarsening replays are not included.
* Typed `PaperAdaptationUpdate` telemetry, checkpoint `unrefined_fraction`
  and `max_error_after`, admission accounting for updates and the energy
  buffer, and fail-closed rejection on the dense adaptive and projected
  facades. Paper mode requires at least two refinement levels.
* Default warmup and every fixed-path fingerprint are unchanged.
* Tests: 100 library + 41 public facade, 0 failed, 1 ignored. Strict
  all-target/all-feature Clippy, `cargo fmt --check`, and `-D warnings`
  rustdoc pass.
* Funnel smoke (10-D, depth 10, eight levels, `Delta = 2`): the `Gamma` rule
  holds window unrefined fractions at 0.78–0.81 and grows `h` from 0.1 to
  about 0.46; the K-quantile rule keeps `delta` at about 1.1–1.7 because the
  observed orbit inflation `K` is only 1.3–2.8. The published funnel
  `delta = 0.21` therefore corresponds to a smaller `Delta` than the
  default 2 in this kernel; `Delta` is the knob for the reproduction study.
* Not done: no evidence run; paper mode is not wired into the dense adaptive,
  projected or pooled drivers; deep configurations still need budgeted
  admission because the conservative bound is unchanged.

## Non-negotiable invariants

* An active metric generation is immutable for an entire transition.
* Metric installation never changes numeric `q`, cached log density, or cached
  gradient.
* Momentum is freshly sampled after every installation.
* No metric update occurs after warmup or before a completed window boundary.
* Failed candidates preserve the previous generation.
* Existing facade behavior is not changed until a golden oracle proves exact
  compatibility.
* Shared reductions and error selection are ordered by chain index.
* Preflight and telemetry do not consume target callbacks or RNG.
