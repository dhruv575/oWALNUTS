# Population PK numerical and model preflight

Use the preserved Theoph snapshot (12 subjects), with baseline concentration
conditioned as before. Train on the first eight post-baseline observations per
subject; reserve the last two for descriptive prediction. All data are publicly
available and subjects 1--3 were previously examined: this is exploratory,
not a new blinded validation. No clinical or decision-value claims.

Compare hierarchical linear elimination (43 unconstrained parameters) with
hierarchical Michaelis-Menten elimination (57). Each log structural parameter
has population mean mu and subject effect tau*z, z~normal(0,1), tau~half-normal
(0,.5). Volume and Vmax are per kg. Population-mean priors follow the individual
pilot: log ka N(0,1.2), log volume/kg N(log(.5),.7); linear log ke N(log(.1),1.2);
nonlinear log Km N(log(5),1.5), log Vmax/kg N(log(.15),1.5). Shared log observation
sigma N(log(.2),.7). These are working assumptions, not clinical calibration.

Reuse archived native likelihood/gradients with their artificial parameter prior
removed analytically; do not rebuild or alter that dependency. Validate the
assembled population gradient by finite differences before optimization. Audit
each selected mode with tighter tolerance and alternate solver. No numerical
failure is silently scored as a good fit.

Four deterministic training-only starts per model (seed 928100001): prior
center and three Gaussian perturbations of size .2 in unconstrained coordinates.
Optimize each independently with L-BFGS-B, maxiter 500, bounded jobs 300 seconds,
1GiB RSS, 8MiB output. At most eight single-core jobs; disk floor 1GiB. Preserve
all failures. Require max abs gradient <.01 for an optimization qualification;
report bounds and alternative modes. Model objective values are not evidence
ratios and are not compared across dimensions.

Only after selecting the best qualified training mode per model, report heldout
log-concentration RMSE and plug-in log predictive density by subject, with
paired differences. These MAP predictions omit parameter uncertainty and do not
qualify an inference algorithm or establish the value of nonlinear elimination.
If numerical/optimization preflight succeeds, next freeze a posterior comparison
including tuned NUTS, WALNUTS, Laplace/defensive importance and the simpler model.
Reference qualification, fresh seeds, uncertainty functionals and the practical
success rule must precede that next experiment.

Numerical preflight amendment, before any optimization: inherited likelihood
tolerance 1e-8 failed the fixed 1e-4 scaled gradient-error requirement at the
perturbed nonlinear starting point (error .000991). Tolerance 1e-10 passes
both points (maximum .0000587); linear error is below 2e-9. Use 1e-10 for all
fits and retain failed preflight logs. No gate is relaxed. MAP audit must still
compare tighter BDF and alternate RK45 results before interpreting predictions.
