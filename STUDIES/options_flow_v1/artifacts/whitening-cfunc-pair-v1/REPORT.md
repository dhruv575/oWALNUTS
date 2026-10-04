# Exact combined-solve target profile

All eight frozen cells completed with unchanged source/runtime bindings and
zero active descendants after cleanup. Independent JAX value/gradient checks
passed for the three fixed positions in every cell. Original and combined
implementations used identical data and positions.

| Periods | Original median microseconds/call | Combined median microseconds/call | Original/combined |
| --- | ---: | ---: | ---: |
| 32 | 100.895 | 75.043 | 1.345 |
| 128 | 399.954 | 281.178 | 1.422 |
| 512 | 1512.398 | 1173.144 | 1.289 |
| 1000 | 2743.213 | 2093.359 | 1.310 |

These are medians of five 300-call blocks in one fresh process per cell, with
balanced original/combined ordering across lengths and existing compiler
caches retained. They are exploratory callback measurements, not independent
replicated speed estimates or MCMC workflow speedups. Compile, first-call and
full process costs remain recorded separately.

The exact identity h=L^-T(v+z) reduces repeated target cost on these points.
It does not fix poor mixing, change the target, or justify promoting whitening
as a default. The next workflow comparison must charge compilation, parity,
warmup, all retained work and failures, using the unchanged precision gates.
