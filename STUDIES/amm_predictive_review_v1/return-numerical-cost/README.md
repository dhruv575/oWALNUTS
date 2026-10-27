# One-origin predictive-return integration cost

**Post-hoc numerical diagnostic only.** Plan `348ccc9e` and implementation
`be2afc34` were committed before these outputs. The fixed real-data origin is
WP97 tick 2: one 80,000-component reference and actual warm K=20/50/200 draws
from seed 971301. No new sampler work, reference thinning or extra origin.

At this origin, **eight quadrature nodes reproduce the 128-node predictive
return quantiles well inside the predeclared numerical tolerances**, with warm
postprocessing taking 4.47-34.62 milliseconds locally. This makes practical
return-summary cost plausible enough to investigate; it establishes neither
posterior accuracy nor an online system's latency.

## Numerical agreement and cost

All 12 low-order comparisons (8/16/32 nodes across the four input cases) satisfy
both fixed 1e-6 targets: GH128 CDF residual at each computed root, and quantile
difference normalized by the same input's GH128 P95-P5 interval width. The worst
GH8 discrepancies are 7.06e-11 in CDF and 3.08e-10 in normalized endpoints.
Each rule's own numerical root residual also satisfies the <=1e-8 check.

| Input at real tick 2 | Actual posterior components | GH8 | GH16 | GH32 | GH128 |
|---|---:|---:|---:|---:|---:|
| Reference | 80,000 | 3.466 s | 6.704 s | 12.447 s | saved comparator |
| Warm K=20 | 80 | 4.47 ms | 6.95 ms | 12.46 ms | 45.42 ms |
| Warm K=50 | 200 | 9.22 ms | 19.51 ms | 31.79 ms | 108.95 ms |
| Warm K=200 | 800 | 34.62 ms | 65.94 ms | 127.03 ms | 419.62 ms |

Times include a rule's cache initialization and three quantile solves; the
reference GH128 roots were reused from the earlier same-input smoke and GH128
was evaluated at the new low-order roots. The warm GH128 comparator was solved
on each warm cell's actual draws. These comparisons isolate numerical
integration error; warm results were **not** compared with the reference
posterior to qualify refresh accuracy.

The whole diagnostic completed in 31.870 seconds, using 294,787,840 reserved
component-node evaluations out of the fixed 400-million cap. It includes
GH128 verification work, input checks and all four cases, so its total differs
from the sum of low-order solve times. There were no missing, failed or timed
out cases, and all input hashes remained unchanged.

These are single local timings with fixed node/case order, not replicated or
optimized production benchmarks. They must not be added to sampler timings
measured on AWS to claim fused end-to-end latency. Source versions and exact
per-rule counts, cache times, roots and errors are in `results.json`.

## Memory: working process measured correctly

The actual Python process (PID 12012) queried Windows `GetProcessMemoryInfo`
directly, rather than measuring the virtualenv launch process:

- Peak working set: **203,010,048 bytes (193.61 MiB)**.
- Peak Windows pagefile/commit metric: **1,226,948,608 bytes**.
- End-of-run private-usage metric: **1,105,195,008 bytes**.
- Maximum simultaneously cached inverse-scale arrays: **102,400,000 bytes**
  (97.66 MiB), below the declared 128 MiB array-cache cap.

The working-set and pagefile/commit metrics describe different quantities; the
second is not physical resident RAM or actual pagefile I/O. They include the
Python process and imported numerical libraries, not just quadrature arrays.
The array-cache cap is **not** a total-process memory limit. Chunked scratch
matrices and start/end memory counters are recorded separately. This measures
the present diagnostic; it does not retroactively establish the earlier smoke's
uncaptured peak RSS.

## Interpretation and limits

GH8 is **not selected as a global default**. This is one previously inspected
origin, and all four inputs arise from the same data window. Broader innovation
scales, different posterior mixtures or more extreme tails may need higher
orders. A separately validated candidate could compare 8/16-node outputs and
fall back to 32/64/128, but pairwise agreement alone is not a rigorous error
bound and no such order-selection policy is qualified here.

The result separates a tractable numerical integration cost from the remaining
statistical problems: reliable posterior refresh, posterior Monte Carlo error,
predictive calibration and a useful decision rule. No automatic MCSE stopping,
sampler default, forecast-accuracy claim or trading policy follows.

## Provenance and reproduction

The reference is the identical completed-origin snapshot used by the prior
full-return smoke. The warm snapshot contains exact original tick-0/tick-2
records and full four-field draw files from source commit `a355bae5`; all
80/200/800 warm components are used with their recorded chain identity.
`warm-snapshot-provenance.json` and `warm-snapshot-files.sha256` preserve its
lineage. Final archive reconciliation remains necessary while WP97 completes.

```console
python STUDIES/amm_predictive_review_v1/return-numerical-cost/run.py --reference-snapshot REFERENCE_SNAPSHOT --warm-snapshot WARM_SNAPSHOT --out NEW_OUTPUT_DIRECTORY
```

The processor refuses an existing results file. `results.json` records source,
plan, dependency and input identities, original gate records, reused fixture
identity, all comparisons and resource counters. The original smoke and WP97
study outputs are unchanged.
