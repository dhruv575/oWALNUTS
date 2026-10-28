# Exact-coordinate-change stress panel

All three T=12 all-zero fits passed every physical mu,log_sigma,beta,z diagnostic
and the additional b diagnostic, with zero retained divergences or depth hits.
The target and sampling budget are unchanged from the corresponding original
NUTS cases; seeds differ as declared. The change is beta=exp(mean(h)/2)*b with
the original beta prior and the exact Jacobian, not a replacement prior.

At caps .5/1/2, the four chain medians of mean(h) were approximately -27.3/-62.1/
-201.0 respectively. At cap 2 this is beyond the regions reached by both earlier
failed methods (NUTS about -60 to -63; slice about -164 to -177). New diagnostics
are encouraging but do not establish fidelity without an independent reference.
Physical beta remains representable despite being extremely small.

The 72-case independent Stan/autodiff target check passed: maximum density error
8.732e-11 and gradient error 5.685e-11. The supervised sampling campaign completed
in 18.171 seconds, peak RSS 5,952,888,832 bytes, output 21,004,471 bytes, all groups
drained and sources unchanged. Individual sampling phases were .209/.214/.249
seconds, excluding compilation and serialization; these are not a WALNUTS speed
comparison or precision-matched benchmark.

The 20,553,250-byte full archive matched its remote SHA256. Both parity and sampling
source bindings were checked. All three raw NUTS traces were reopened locally;
shapes/finiteness checked and ArviZ coordinate tables independently recomputed
from saved draws, matching the remote CSVs. Retained divergence/depth event counts
were also reproduced. The archive includes full warmup and retained draws.

Next establish a genuinely independent control in these better coordinates,
then move the admitted target into a declared real-market prior-sensitivity and
predictive study. Do not continue accumulating synthetic passes in place of
market evidence. Prior-cap justification, observation assumptions, economic
decision value, profitability and paper novelty are still separate open gates.
