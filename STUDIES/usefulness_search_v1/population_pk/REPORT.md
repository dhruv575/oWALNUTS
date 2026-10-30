# Population PK preflight: simpler model is the stronger lead

The 43-parameter hierarchical linear and 57-parameter hierarchical nonlinear
models use all 12 observed subjects, with 96 training and 24 withheld-from-fit
post-baseline concentrations. This is exposed, exploratory data, not a new
clinical validation. Population gradient checks passed at tolerance 1e-10 after
the inherited 1e-8 nonlinear preflight failed; failed checks are preserved.

All eight optimization jobs terminated normally with unchanged dependencies
and drained groups. Only 2/4 linear and 1/4 nonlinear starts met the frozen
gradient/boundary qualification. Remaining starts encountered numerical
evaluations that caused false optimizer convergence; they are explicitly
unqualified despite the optimizer success flag. No failed start was rerun.
This leaves uncertainty about optimization robustness and alternative modes.

The selected qualified modes pass tighter-BDF/alternate-RK45 audits. Nonlinear
maximum scaled gradient discrepancy is 1.29e-6 and log-prediction discrepancy
1.72e-8. Linear predictions are analytic, so its solver-toggle equality is not
an independent numerical-solver test.

Heldout log-concentration RMSE is .2489 for linear versus .5353 for nonlinear.
Linear has lower per-subject error in 11/12 subjects. Shared fitted noise
scales are .1598 and .1619. Plug-in predictive-density details are in
analysis01/SUMMARY.json. These predictions omit parameter uncertainty; MAP
values are parameterization-dependent and are not evidence ratios. Do not
claim nonlinear-model inferiority conclusively, posterior fidelity or decision
value from this preflight. It provides no reason to force an expensive ODE
application.

Next: investigate qualified posterior uncertainty for the simpler hierarchical
linear model, using a shared native target for WALNUTS and tuned NUTS, plus
Laplace/defensive importance baselines. Verify the native population gradient
against this Python assembly before sampling. Freeze parameter/forecast
functionals, reference qualification and independent seed sets first. Preserve
the nonlinear model as a negative exploratory comparison.

Full 47-member evidence archive and dependencies passed local and exact-version
S3 restore verification (archive/). All remote originals remain. No inference
algorithm has demonstrated usefulness yet; goal remains active.
