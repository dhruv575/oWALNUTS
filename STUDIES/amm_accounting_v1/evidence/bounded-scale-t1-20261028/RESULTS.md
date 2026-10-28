# Bounded-scale T1 independent reference comparison

All three fixed cap cases completed and passed every MCMC coordinate diagnostic
(Rhat<=1.01, bulk/tail ESS>=400), with zero retained divergences or depth hits.
From exactly one million proposals each, the independent rejection references
accepted 374,677 / 375,733 / 376,104 draws for caps .5 / 1 / 2. Maximum absolute
coordinate-mean discrepancies were 1.049 / .563 / 1.774 combined MCSEs; none
exceeded four. These are finite-sample checks, not a general fidelity proof.

Outer elapsed time was 17.600 seconds, peak process-tree RSS 5,981,552,640 bytes
and final output 43,126,218 bytes. Every process drained and sources stayed
unchanged. The complete archive matched its remote SHA256 after download;
all source bindings and accepted-array shapes/finiteness were verified. Full
NUTS traces, including warmup, and independent arrays remain in that archive.

All cases have one observation y=0. This cannot verify a repeated-tie target
or high-dimensional geometry, and does not select a scientifically appropriate
cap. Normalized posterior existence, MCMC fidelity, market observation
approximation and predictive/economic validity remain separate questions.

Next build an independent multi-observation control and evaluate fixed repeated-
tie cases alongside distinct observations. Avoid interpreting a proper target
as automatically easy to sample: small-scale likelihood concentration may
still produce difficult posterior geometry near the upper scale bound.
