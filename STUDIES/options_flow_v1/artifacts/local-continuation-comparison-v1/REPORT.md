# Continuation workflow comparison

All nine frozen cells completed; independent checks of source/runtime identity,
physical starts, all-coordinate health, endpoint precision, stopping, adaptation,
callback accounting and costs pass. This uses three development-selected local
fixtures and fresh chain seeds, not a fresh population reliability cohort.

| Fixture | Restart seconds | oW continuation seconds | NumPyro seconds | Outcomes |
| --- | ---: | ---: | ---: | --- |
| 00 | 10.67 | 12.37 | 56.10 | All pass |
| 03 | 45.59 | 34.20 | 64.77 | All fail |
| 05 | 82.81 | 54.31 | 92.12 | All fail |

Costs include imports, compilation, parity, adaptation, sampling, evaluation,
serialization and controller work. All failed costs remain in the denominator;
there are no successful-workflow ratios for fixtures 03 or 05. On fixture 00,
continuation is 1.159 times the restart cost, and NumPyro is 4.537 times the
continuation cost. One successful selected fixture cannot establish broad speed.

On fixture 00, both oW workflows first pass at 4,000 draws per chain. Restart
sampling costs 3.148 seconds versus continuation's 1.652 seconds, but output
and other workflow overhead erase that saving. The continuation 4,000-draw
serialization phase alone takes 2.333 seconds. This motivated a separately
authored serialization optimization; these results have not been adjusted by
subtracting hypothetical savings.

Continuation reduces repeated adaptation/sampling work but does not resolve the
observed difficult posterior geometry. The next experiments must test the
optimized complete workflow and the demanding order-flow target with unchanged
precision requirements. No interval calibration or market-utility claim follows
from this comparison.
