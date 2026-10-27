# Post-hoc one-origin predictive-return numerical-cost diagnostic

2026-10-27, written before this diagnostic's computations. The preceding
GH64/128 full-reference smoke already showed nearly identical quantiles at
68.51 seconds total. This follow-up is explicitly post hoc: can fewer quadrature
nodes reproduce those numerical quantities more cheaply at this same origin?
No new sampler cells, remote computations, extra origins or qualification.

## Fixed inputs and computations

- Reference: the same verified WP97 `ref-real-lo` tick 2 snapshot, all original
  kept chains and all 80,000 compact four-field draws. Reuse the saved GH128
  quantiles from the previous smoke, whose raw input hash must match.
- Warm: only actual completed `warm20-real-s971301`, `warm50-real-s971301`,
  `warm200-real-s971301` tick 2 artifacts. Preserve exact record/chain identity;
  use all their actual retained draws, never a thinned reference substitute.
- If a requested file is missing or invalid, preserve an unavailable case; do
  not switch seed, origin, attempt or dataset. Reconcile completed snapshots
  against the final archive later; no claim that the full experiment is done.
- Keep the same joint predictive-return CDF and P5/P50/P95. For the reference,
  solve GH8,16,32 in that fixed order; compare each to the saved GH128 roots and
  evaluate GH128 at the new roots. Do not refit or change the model.
- For each warm cell, in order K=20,50,200, solve GH8,16,32,128 on exactly the
  same warm draws. Compare low-node estimates to that warm cell's GH128
  estimates and CDF, not to the reference posterior. This isolates integration
  approximation, not posterior sampling error or refresh quality.

## Predeclared numerical diagnostics

Retain the existing finite-input, positive-scale/weight, dynamic-bracket and
root checks. Every solved root must have own-rule CDF residual <=1e-8.
A low-node result is numerically close on this origin only if BOTH:

1. max absolute GH128 CDF residual at its three roots <=1e-6;
2. max endpoint difference divided by GH128's P95-P5 interval width <=1e-6.

Record all nodes and errors, including failures. Do not silently add nodes,
loosen tolerance or select only passing endpoints. The GH128 calculation is a
numerical comparator, not exact posterior truth; GH64/128 agreement at the
reference does not establish a universal integration bound. A cheap passing
node count here is merely a candidate for later testing on other origins.

## Work and memory envelope

- Five-minute local ceiling after imports, checked within every CDF chunk.
- Hard budget of 400,000,000 component-node Student-t CDF evaluations for this
  diagnostic. Reserve each complete CDF call before evaluation; stop and retain
  partial results if the next call would exceed the cap. Fixture checks, when
  run, count toward that budget too.
- At most 128 MiB of cached inverse-scale matrices at once, chunk size 512.
  Release each input case's caches before moving to the next; report allocated
  cache bytes and scratch-array dimensions separately from total process RSS.
- Measure actual working Python process peak working set using the Windows
  GetProcessMemoryInfo API **inside that Python process**, recording its PID.
  This corrects the earlier launch-process monitoring failure. On other
  platforms report explicit unavailable or properly labeled native peak usage.
- Record total/each-rule local processing times, initialization/cache time,
  component/node/CDF counts, cache footprint and peak memory. These single-run,
  local postprocessing times are not optimized online benchmarks and cannot be
  added to sampler timings measured on another host as an end-to-end result.

Run only immutable snapshots, save plan/source/dependency/input hashes and
versions, verify inputs unchanged afterward, and never overwrite an existing
result. Record partial outcomes on timeout, work-cap, numerical or I/O failure.
The prior full-reference smoke and frozen WP97 results remain unchanged.
