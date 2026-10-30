# Public pharmacokinetic ODE triage, 2026-10-29

Question: does the likelihood-cost advantage survive on a real nonlinear
pharmacokinetic likelihood, with useful forecasts, strong sampler controls,
Laplace approximation and a simpler standard model? This is a bounded pilot,
not clinical validation or a dosing recommendation. No deployment or trading.

## Sources and models

Preserve the public Stan one-compartment oral absorption/Michaelis–Menten
elimination model and its 20-observation data file. Clinical provenance of
that fixture is unverified; label it a computational benchmark, not patients.
Model source: https://mc-stan.org/learn-stan/case-studies/convert_odes.html

Also preserve the public R Theoph data: subjects 1,2,3 by numeric ID, chosen
without outcome-based selection. This is observed data from 12 subjects; this
pilot uses three, not an entire-population claim. Source documentation:
https://stat.ethz.ch/R-manual/R-patched/RHOME/library/datasets/html/Theoph.html
CSV mirror and exact byte hashes are in source_data/SOURCES.json.

For each selected subject, condition on the measured concentration at time0,
exclude it from the likelihood, train on the next eight measurements and hold
out the final two. Baseline measurement uncertainty is not modeled and is a
limitation. Times are hours; total oral dose = reported mg/kg times weight.
The compartment volume is apparent volume under the fixed bioavailability
convention. Individual fits do not include population pooling.

Nonlinear model: dC/dt=ka*D/V*exp(-ka*t)-(Vm/V)*C/(Km+C).
Clinical working priors on log(ka,Km,Vm,V,sigma): means
(0,log5,log(D/24),log(weight/2),log.2), SDs(1.2,1.5,1.5,.7,.7).
Observation model is lognormal(logC,sigma). These proper working priors are
not established clinical priors. The public fixture instead retains its
original four independent positive half-Cauchy(0,1) priors with fixed volume2.
All prior Jacobians are included in log-parameter space.

The clinical linear-elimination baseline has an exact concentration solution,
log-prior means (logka,logke,logV,logsigma)=(0,log.1,log(weight/2),log.2), SDs
(1.2,1.2,.7,.7), identical observations/holdouts. It is a different model;
its cost and held-out score are not a same-posterior sampler comparison.

## Common likelihood and preparation

Compile one BridgeStan model with BDF tolerance1e-8 absolute/relative, 20,000
step cap, no STAN_THREADS; both samplers use the identical native C adapter,
analytic autodiff gradient, error handling and counters. Serialize Stan calls
inside each worker; four chains run sequentially on one core. Verify native
ABIs, finite-difference gradients, independent SciPy DOP853 predictions, and
BDF/RK45 tolerance1e-10 gradients before inference. Original build failures
are preserved as preflight logs, not sampler results.

Common training-only multistart log-posterior MAP and finite-difference Hessian
produce an invertible global whitening transform. Include competitive distinct
MAPs in the shared four starts. Record Hessian clipping and optimizer gradients;
invalid curvature disqualifies Laplace, but a regularized invertible transform
can still be used without changing the sampled posterior. Map draws back to
the original log-parameter coordinates before every diagnostic/comparison.

## Runs and freezing

Calibration: four nonlinear targets, eight configurations (each engine crossed
with raw/whitened coordinates and acceptance .90/.99), one disjoint seed,
750 warmup and 1,000 retained draws per chain: 32 fits. WALNUTS max_error1.
Both engines depth11. Select each engine per target by diagnostic pass, then
smallest max(MCSE/SD) across parameters and forecast features if none pass,
otherwise smallest kernel time; lexical tie-break. Freeze selection before
fresh validation. This small tuning budget is explicitly exploratory.

References: all seven nonlinear/linear cases; independent raw and whitened
NUTS .99 fits, four chains each, 1,500 warmup and 6,000 retained draws: 14 fits.
Combined eight-chain reference must have R-hat<=1.01, bulk/tail ESS>=2,000,
zero retained divergences/depth hits. Separate reference means must agree
within max(3 combined MCSE, half the validation tolerance) for every feature.
An unqualified reference blocks matched-accuracy claims for that target.
No unlimited reference extensions or outcome-based exclusion.

Validation: selected WALNUTS and selected NUTS, eight fresh seeds per nonlinear
target, 1,000 warmup/2,000 retained draws: 64 fits. Shuffle job order. All
raw parameters and forecast features require R-hat<=1.01, bulk/tail ESS>=400,
zero retained divergences/depth hits. Mean error against qualified reference
<= tolerance + 3*reference MCSE; validation MCSE <= half tolerance. Tolerances:
log-parameter means .10*reference SD, log latent concentrations .03, final-two
predictive exceedance probabilities .02. Exceedance level is half the maximum
training concentration, not a clinical threshold. Prediction times include
training and held-out times; held-out concentration VALUES never affect fits,
MAP, calibration or selection. Primary functionals are predefined.

Laplace: one four-chain independent Gaussian approximation per seven targets,
4,000 draws each, full inverse MAP Hessian, identical diagnostic and prediction
evaluation. Count all solver/invalid approximation failures. Its draw time
includes common MAP preparation; report setup, sampling, diagnostics and cold
worker time separately. It is not a posterior truth reference.

Success requires >=7/8 WALNUTS validation passes, no fewer than tuned NUTS,
>=1.5 paired kernel-time advantage with descriptive bootstrap lower bound>1,
and evidence that cheap approximation/model baselines miss a predeclared
forecast tolerance or perform materially worse. Report every target and
censor failed/unqualified cases. Do not claim clinical usefulness from six
held-out observations; report predictive log scores as small-sample triage.

Audit numerical accuracy again on a deterministic sample of retained reference
points before using those references. If solver differences exceed 10% of a
forecast tolerance or materially affect the target gradient, report numerical
qualification failure rather than hiding it. Audit 16 evenly spaced draws per
reference fit with BDF and RK45 at 1e-10; maximum log-prediction difference must
be <=.003 and max abs(gradient difference)/(1+abs(primary gradient)) <=.001.
Any failed audited evaluation disqualifies the numerical reference.

## Resources and provenance

Seed bases: calibration845000000, references855000000, validation865000000,
Laplace875000000, tests885000000; case stride100000, rep stride1000, config
index offset. Bootstrap895000000. Optimizer starts deterministic, no holdouts.
Up to twelve exclusive cores on the existing instance; each job 900s, 1GiB RSS,
64MiB output; stop admitting below 1GiB free disk or after one hour. Preserve
raw double-precision draws/predictions, failures, data/model/build hashes,
sources, resource receipts and diagnostic rows. No new infrastructure.
Previously verified duplicate transfer archives may be reclaimed only after
matching local original/restored and remote SHA256 and reading the local tar.
AWS login is expired; do not broaden the instance role to bypass access limits.
