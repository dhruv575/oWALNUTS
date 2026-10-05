# Specialist stochastic-volatility comparator

Research prototype only. This implementation does **not** call oWALNUTS and has
not undergone a convergence or performance campaign. Four mathematical/edge
tests pass, including numerical integration of the normalized augmented density.

The Student-t law is represented by lambda~Gamma(nu/2, rate=nu/2),
y|lambda,h,beta~Normal(x beta, exp(h)/lambda). Its observed-row conditional
lambda is Gamma((nu+1)/2, rate=(nu+residual² exp(-h))/2). Missing rows have no
auxiliary variable; their lambda array entry is an ignored placeholder one.
The beta block is Gaussian with precision prior_precision+X' diag(lambda exp(-h)) X.
An elliptical-slice step updates every standard-normal process innovation z.
Scalar slice steps then update mu, log_sigma and gamma with lambda and z fixed.
No observation is dropped from the latent recurrence. The initial forced-mean
contract is inherited from Target.path, not replaced with stationary forced mean.

Elliptical slice removes only the standard-normal z prior from the normalized
joint before evaluating its likelihood. Scalar stepping-out uses a randomized
left/right allocation; finite stepping-out budgets are part of that algorithm,
while shrinkage/ellipse exhaustion raises and aborts, never silently accepts.
Unexpected numerical failures raise. These policies can cause operational
failure and must remain in any future experimental denominator.

Primary method: Murray, Adams and MacKay (2010),
https://homepages.inf.ed.ac.uk/imurray2/pub/10ess/ . The heavy-tailed observation
augmentation does not make log volatility Gaussian: ordinary FFBS is not an
exact update for h here. This simple implementation recomputes full densities
and is deliberately not optimized. Strong global/path dependence can mix slowly;
valid invariant blocks alone do not establish posterior accuracy.

Next bounded test, only after prospective review: same fixed synthetic fixtures
as the joint-coordinate procedures, separate seeds, matching physical starts,
all parameter and predictive endpoint diagnostics, and total costs including
all slice likelihood evaluations. For changed rolling data start a new target;
never mutate an active oWALNUTS session or reuse cached energy/gradient across
conditional distributions. No market coverage or latency claim follows from the
current mathematical controls.

## Completed fixed T32 diagnostic

The single bounded diagnostic is archived in
`../artifacts/sv-hybrid-t32-v1/`. Four hybrid chains completed the fixed
1000 warmup and2000 retained sweeps in29.91 worker seconds. Canonical health
passed, but endpoint MCSE/width failed for sigma (.02973) and terminal h (.02481).
The full-joint NumPyro reference passed in5.48 worker seconds. All attempt costs
and failures are retained. There is no eligible speed comparison; hybrid chains
were sequential and reference chains parallel. No further tuning was performed.
These results do not validate market intervals or make an efficiency claim for
this unoptimized specialist comparator.
