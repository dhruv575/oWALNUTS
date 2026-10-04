# Conditional-whitening target cost

All four fresh CPU-0 processes completed with unchanged bound sources and zero
active descendants after cleanup. Existing compiler caches were retained.
Five blocks of 300 calls used three fixed positions at each length.

| Periods | Compile seconds | Mean microseconds per value/gradient call |
| --- | ---: | ---: |
| 32 | 10.94 | 111.81 |
| 128 | 10.42 | 359.60 |
| 512 | 12.24 | 1522.31 |
| 1000 | 10.55 | 3003.14 |

The observed scaling is approximately linear. These measurements do not support
a quadratic-complexity explanation. The per-call cost is nevertheless material
when a trajectory requires many evaluations. The loop includes ctypes dispatch;
compilation and first calls are recorded separately. This is not an MCMC speed
comparison and cannot establish posterior accuracy or mixing.

Separate JAX scan validation passed at all twelve fixed positions: maximum
absolute gradient difference 8.53e-12 and density difference 2.51e-11. This
checks first-order target agreement at those positions, not all states.
Exact source snapshots, plan bindings, process records and validation results
are retained alongside this report. The next candidate removes one redundant
backward solve using the exact identity h=L^-T(v+z); its benefit is unmeasured.
