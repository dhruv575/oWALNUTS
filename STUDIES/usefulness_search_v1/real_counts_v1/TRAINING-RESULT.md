# Real count-data training evidence

The four-group reference passed all frozen diagnostics and pairwise agreement
checks. An independent local audit reconstructed all128000 raw posterior draws
and all160 physical functionals. Each group had zero retained divergences.
Minimum bulk ESS across groups was4398.34; no predictive qualification follows.

The two exact-target importance runs also qualified on all160 training quantities.
Raw weight ESS13271.28 and13355.78; Pareto k.2660 and.2085; maximum mean errors
.0181 and.0242 reference SD; maximum SD relative errors.0166 and.0108.
Recomputed exact target values, proposal densities and physical quantities for
all32768 samples on the original AWS runtime. The local cross-platform replay
failed strict proposal-density agreement (rep0,max absolute error.00138865,
13647 draws outside tolerance), preserved in IMPORTANCE-AUDIT-FAILURE.json.
Same-runtime replay passed unchanged tolerance. This does not establish the
precise numerical cause; the proposal uses numerical covariance factors and
must retain runtime provenance. No failed check was relaxed.

Native settings screen: acceptance.9 and.95 had55 and12 retained divergences;
both failed qualification despite passing moment/mixing checks. Acceptance.99
passed, as did fixed WAL dense.9. Independent raw-draw audit selected native.99
under the frozen rule. This selection uses exposed training data; fresh-seed
confirmation remains required. Concurrent runtime measurements are not a clean
timing comparison. Strong approximation remains a credible alternative.

No heldout labels have been scored. No practical advantage, unique application,
predictive value, profitability, or novel algorithm contribution is established.
Next: fresh serial whole-workflow confirmation with the selected native control
and strong importance baseline, then separately qualified predictive integration
and exact model-control comparison. Preserve failures and exposed-series limits.

Audits used180s process timeouts and BLAS1. Unlike sampling workers, audit
commands did not enforce separate RSS/output caps; do not describe them as
resource-monitor-supervised runs. Sampling supervision is retained separately.
