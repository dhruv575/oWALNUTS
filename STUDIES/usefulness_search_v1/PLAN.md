# Continuing usefulness search

Objective: demonstrate an actual application advantage over strong alternatives,
or a substantive tested improvement to WALNUTS. Runtime alone is insufficient.
No deployment, trading or external paper submission. Preserve all negatives.

First unit: audit posterior-distribution gaps in the completed ODE pilot using
preserved draws. Examine every log parameter, not only the known noise-scale
failure: mean, variance, and lower/upper tail probabilities at MAP +/-1.645
Laplace marginal SD. Thresholds derive from training-only MAP curvature, not
from posterior reference quantiles. Report reference R-hat/ESS/MCSE for these
new functionals and compare the two independent reference fits using the
quadrature sum of their individual MCSEs. This is exploratory follow-up; it
does not rewrite the pilot's stricter frozen reference gate or its failed
practical-success result. No patient reference becomes primary-qualified here.

Next screen: test whether ordinary importance correction or a defensive
heavy-tailed proposal cheaply repairs Laplace's full-posterior errors. Include
value-only density cost, weight degeneracy and independent-seed uncertainty;
do not force the approximation to lose by charging unnecessary gradients.
Freeze proposal budgets and thresholds before execution. If cheap correction
works, deprioritize the low-dimensional ODE candidate.

Application candidate: latent GP count inference. Historical gp_pois_regr
results motivate investigation but are exposed, and default NUTS divergences
are not evidence against well-tuned NUTS. Inspect data provenance, priors and
model code; then compare tuned samplers, Laplace/importance approximations and
appropriate latent-Gaussian methods on uncertainty quantities with a stated
application interpretation. Synthetic data remains labeled synthetic.

Algorithm track: profile reverse-check work and avoidable schedule construction.
An incumbent reverse traversal appears to construct a vector used only by a
research alternative. Verify with allocation/CPU measurements, preserve exact
draws, random consumption and oracle parity, and require held-out timing tests.
A negligible micro-optimization does not satisfy the overall improvement goal.

Every inference job remains bounded and evidence archived. Use the existing
instance; review storage headroom before launching. Current source code and
prior source freezes remain unchanged during the exploratory audit.
