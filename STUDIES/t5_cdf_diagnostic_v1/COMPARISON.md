# Saved-draw arithmetic comparison execution supplement

After validation02 passes, use all four host tick NPY files from attempt02,
verified against their adjacent results.json compact_identity hashes. Freeze a
copy of processor source (SHA fffc989bb6b59f4f2f055b1199f9e391fc49a5a97ea3fc436b1a348bb88875fd).
Execute three repetitions per tick per implementation, alternating order by
repetition (SciPy/exact, exact/SciPy, SciPy/exact), in one process with BLAS and
OpenMP threads pinned to one. JIT module import/compilation measured separately.
Each timed invocation reconstructs both GH64/128 processors, computes all three
return quantiles for each, and the same cross-order CDF/endpoint checks as the
resident summary. Keep all draws and fixed tolerances/cache/chunk. Do not include
scale quantiles (unchanged ndtr arithmetic) or native sampling in these timings.
Report all24 invocations, failures, quantile differences, cross-order checks,
per-tick medians, and code/data hashes before/after. Overall arithmetic deadline
300 seconds. No remote work or deployment. Local timings are not host total ticks.
