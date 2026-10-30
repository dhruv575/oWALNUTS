# Posthoc intensity coverage audit

Saved draws from the failed bounded validation were re-evaluated on24 quantities: rho,alpha,11 log intensities and11 intensities. This is not fresh validation and does not change the original all-fit failure.

Both reference summaries agree exactly on shared means/SDs, with maximum MCSE difference1.40e-14. The24-quantity reference passes its stored convergence thresholds. The stricter descriptive accuracy rule uses mean error<=.1 reference SD, relative SD error<=.1 and combined-MCSE z<=4.

| Workflow | All checks | Accuracy checks |
|---|---|---|
| raw/walnuts_dense | 8/8 | 8/8 |
| raw/low_rank | 7/8 | 8/8 |
| affine/walnuts_dense | 8/8 | 8/8 |
| affine/diag | 8/8 | 8/8 |
| bounded/walnuts_dense | 8/8 | 8/8 |
| bounded/low_rank | 7/8 | 8/8 |

Only the two previously recorded native divergence failures remain. No intensity accuracy or convergence failures were added. This does not establish practical advantage, fresh predictive validity, novelty or end-to-end speed. No original outcome or threshold is overwritten.
