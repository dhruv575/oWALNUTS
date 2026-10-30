# Two-stage integration feasibility: no curved-target candidate qualifies

This is an exact-stationary one-trajectory screen, not a cold MCMC or WALNUTS result. Each comparison uses the same8192 independent phase points, integration time and eight fresh gradient evaluations. All gradient, reversibility, determinant and concatenated-leapfrog checks passed. Neither published two-stage coefficient satisfies the frozen advancement rule.

| Target / baseline step | Baseline acceptance | BCSS accepted-jump ratio (95% interval) | Minimum-norm ratio (95% interval) |
|---|---:|---|---|
| gaussian c=0.0 / 1.0 | 0.5427 | 1.6963 [1.6678,1.7255] | 1.2625 [1.2345,1.2918] |
| banana c=2.0 / 0.1 | 0.9354 | 1.0198 [1.0163,1.0233] | 0.9954 [0.9908,1.0000] |
| banana c=5.0 / 0.03 | 0.9680 | 1.0211 [1.0200,1.0222] | 1.0217 [1.0203,1.0233] |
| banana c=5.0 / 0.1 | 0.3104 | 0.4855 [0.4641,0.5077] | 0.2899 [0.2709,0.3087] |
| funnel c=0.0 / 0.1 | 0.9378 | 0.9981 [0.9957,1.0003] | 0.9938 [0.9909,0.9965] |
| funnel c=0.0 / 0.3 | 0.7522 | 0.9778 [0.9720,0.9832] | 0.9457 [0.9389,0.9522] |

The Gaussian improvement does not transfer to the curved-target settings in this grid. The stronger banana grid jumps from baseline acceptance.968 to.310, so it contains no point in the qualifying[.5,.95] band; this is a coverage limitation, not evidence that all intermediate steps fail. At the tested moderate banana and funnel points that qualify, neither candidate clears the1.05 lower-bound gate. At larger steps numerical instability can make both methods worse. These findings do not exclude tuning different coefficients, a denser grid, or model-specific use.

Two zero/zero ratios at banana c=5,h=.3 were NaN in the raw JSON because all phase points were rejected. Raw evidence remains unchanged; REVIEWED-SUMMARY.json labels these undefined and uses strict JSON null. They cannot pass the gate and are not silently dropped. Finite-path energy quantiles are explicitly conditional on numerical finiteness; all failures contribute zero accepted jump. Intervals are exploratory paired bootstrap, not adjusted for32 comparisons.

Published method attribution: Blanes, Casas and Sanz-Serna, Numerical Integrators for the Hybrid Monte Carlo Method, DOI10.1137/130932740; https://www.gicas.uji.es/Fernando/MyPapers/93274-gg.pdf . Symmetric kick/drift compositions preserve volume and reversibility algebraically; numerical checks are supplementary. No novelty or practical-usefulness claim. Production unchanged.

Next reviewed work: close the coverage gap with an independently calibrated step at baseline acceptance.8 for each curved target, keeping equal gradient budget and using fresh phase points. Freeze coefficients, calibration budget, selection rule and validation gate before execution. Only a qualifying validation should trigger full sampler implementation. This is a targeted follow-up to missing coverage, not a reclassification of the failed initial screen.

Resources: worker completed in4.04s, observed peakRSS63.5MiB, evidence16.2MiB. AWS authentication expired on the status recheck; last verified instance state was budget-stopped and no restart was attempted. Local C drive had about212GiB free. Goal remains active.
