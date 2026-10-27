# Exact Student-t5 CDF: arithmetic diagnostic

The stable exact t5 implementation passed the fixed validation and reproduced
saved-draw predictive quantiles to 1.05e-17 absolute. On this Windows machine it
reduced return-summary arithmetic by roughly 3.9–4.6 times. This is not a host
end-to-end timing result, inference qualification, or change to sampler/defaults.

## Numerical evidence

The original elementary/reciprocal implementation failed strict monotonicity:
a 9e-18 smaller-tail jump at the branch boundary. Attempt01 source and
validation.json are preserved, with its pre-execution plan. It was not used for
saved-draw comparison. REFINEMENT.md records the positive-series replacement.

The final version evaluates the central formula and a 64-term positive tail
series. Hypot avoids squaring huge arguments; sequential multiplications preserve
representable tiny tails. There is no fastmath, material clipping, changed
posterior, or changed quadrature order. Exact-arithmetic relative truncation is
bounded by 2^-64 in the series region; floating-point rounding dominates.

Validation03: 244,017 fixed grid points; max CDF/SF absolute error3.34e-16;
max relative smaller-tail error3.13e-15 for reference tails>=1e-300; zero grid
monotonicity violations; exact symmetry within recorded precision. Independent
quadrature and 90-digit integral checks passed, including tails near1e-250.
3,924 grid tails underflowed to zero; 4,000 were excluded from the relative test
because the reference tail was below1e-300. Positive CDFs can round to one;
the separate SF retains small tails. NaN propagates with NumPy's expected invalid
warning, infinities map to0/1, both signed zeros map to1/2.

Reviewer requested the final pass Boolean also include already recorded IEEE,
known-value, symmetry and quadrature error checks. validation03 enforces these
without changing thresholds; validation02 remains preserved. The saved-draw run
had just started after manual inspection of those passing values when this review
arrived. Validation03 completed before accepting comparison results. This timing
is recorded honestly rather than describing the stronger Boolean as pre-run.

## Same-draw local comparison

All four original host compact draws are read-only, hash checked against their
host manifest before and after. The exact original numerical processor is copied
as processor_snapshot.py. Only its stdtr function binding changes. Both versions
use every chain/draw and identical GH64/128 nodes, weights, brackets, root and
cross-order checks, chunk512 and64MiB caches. No sampling was performed.
Three repetitions per tick alternate implementation order as COMPARISON.md states.
All24 invocations succeeded. Local return-only arithmetic medians in seconds:

| Tick | SciPy | Exact t5 | Max P5/P50/P95 difference |
|---|---:|---:|---:|
|1|1.634|0.358|5.96e-19|
|2|1.689|0.392|1.73e-18|
|3|2.059|0.529|0|
|4|2.707|0.691|1.04e-17|

Each timer includes reconstruction of both GH processors, quantile inversion and
cross-order checks. It excludes unchanged scale quantiles, native sampling,
imports/JIT and JSON persistence. Import/JIT time is recorded separately.
Wall-clock drift across this local run is material; these are small paired
measurements, not stable throughput estimates. Do not add local arithmetic to
previous AWS sampler timings to claim a total tick. The AWS instance was stopped;
no remote work was used. A separately reviewed short Linux arithmetic replay
would be needed to measure that environment, followed by a separate integrated
resident measurement before any end-to-end cost claim.

## Reproduction and provenance

Executed locally with C:/dev/owalnuts/target/python-workflow-env/Scripts/python.exe,
Python3.14.7, NumPy2.5.2, SciPy1.18.1, numba0.67.0, mpmath1.4.1.
Commands: python validate.py (three separately preserved validation outputs),
python compare.py (once; refuses existing output). Original validator source is
in commit80a21079; intermediate in37205a91; final source beside validation03.
compare.py pins BLAS/OpenMP threads toone before imports. Exact UTC, versions,
input paths/hashes, executed source hashes and all24 results are in comparison.json.
Plans were committed0d053674, refinement6056daaa, comparison37205a91 before use.
The baseline processor SHA is fffc989bb6b59f4f2f055b1199f9e391fc49a5a97ea3fc436b1a348bb88875fd.

No market-making profitability, calibration or posterior-accuracy conclusion
follows from this arithmetic identity and cost diagnostic.
