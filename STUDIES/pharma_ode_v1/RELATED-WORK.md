# Practical baseline context

Checked primary sources on 2026-10-29. This pilot does not introduce Bayesian
pharmacometrics, Michaelis–Menten elimination, log-state integration or ODE
sampling. A possible contribution would require comparative evidence for the
sampler under a specified accuracy and cost criterion.

Torsten already supplies pharmacometric model/event infrastructure and
specialized solvers. Its [one-compartment documentation](https://metrumresearchgroup.github.io/Torsten/function/one-cpt/)
describes the familiar first-order absorption/elimination model. The pilot's
exact linear solution is therefore an essential baseline, not a new method.
The cited documentation is an older published version, not a claim about the
latest release or a benchmark of every Torsten configuration.

Torsten's [coupled-solver documentation](https://metrumresearchgroup.github.io/Torsten/function/coupled/)
explains reducing an ODE system by solving an independent subsystem analytically
and substituting it into the remaining numerical equations. This pilot already
does that for the absorption compartment through its exponential input.
A generalized claim about superiority over optimized pharmacometric inference
would still need comparison to specialized solver choices, sensitivity methods,
population parameterizations and parallelism. None is established here.

The [Stan public example](https://mc-stan.org/learn-stan/case-studies/convert_odes.html)
provides the computational model/fixture; its presence is not evidence of clinical
data provenance. The observed-data source is separately documented in
[R's Theoph documentation](https://stat.ethz.ch/R-manual/R-patched/RHOME/library/datasets/html/Theoph.html).
The three-subject conditional pilot is narrower than population PK inference.

Practical interpretation must separate faster inference for the same nonlinear
model, approximation adequacy, predictive value of nonlinearity, clinical
decision value, and commercial demand. This experiment measures only the first
three, subject to its reference and small-sample limitations.
