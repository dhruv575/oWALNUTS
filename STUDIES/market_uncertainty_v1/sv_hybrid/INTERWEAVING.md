# Development interweaving extension

`interwoven.py` extends the existing augmented Gibbs/elliptical-slice prototype
for the intercept-only, no-flow target. It does not replace the archived T32
benchmark or reinterpret that prototype's precision failures. No comparative
performance result exists for this extension yet.

The approach is motivated by established centered/noncentered interweaving in
SV models, rather than a new algorithm claim. Kastner and Frühwirth-Schnatter
(2014), [CSDA 76, 408–423](https://arxiv.org/abs/1706.05280), describe why
parameterization affects SV sampling and how interweaving can help. The exact
blocks below are derived for our fixed-rho Student-t model; this is not a
replication of their complete sampler. The inherited latent update uses
[elliptical slice sampling](https://proceedings.mlr.press/v9/murray10a.html).

## Transition

First execute the unchanged noncentered hybrid sweep: sample observation
precisions, beta, standard-normal latent innovations and noncentered globals.
Then compute the physical latent path h. Keeping h and beta fixed, draw mu
from its exact Gaussian conditional and update log_sigma by the existing
randomized stepping-out slice kernel. Finally map the same h back to innovations.

Let r=rho, s=exp(log_sigma), n=len(h), and mu~N(m0,v0). The Gaussian conditional
has precision

`A = 1/v0 + ((1-r*r) + (n-1)*(1-r)^2)/s^2`

and mean

`(m0/v0 + ((1-r*r)*h[0] + (1-r)*sum(h[i]-r*h[i-1]))/s^2)/A`.

At fixed h and the updated mu, the log_sigma conditional, up to constants, is

`-n*log_sigma - 0.5*exp(-2*log_sigma)*S - 0.5*((log_sigma-l0)/lsd)^2`,

where `S=(1-r*r)*(h[0]-mu)^2 + sum((h[i]-mu-r*(h[i-1]-mu))^2)`.
The observation likelihood and auxiliary-precision law depend on h and beta,
so they are constant during these two updates. The `-n*log_sigma` term is
essential: the centered density includes the coordinate Jacobian
`log|dz/dh| = -n*log_sigma + 0.5*log(1-r*r)`.

The return map is `z[0]=sqrt(1-r*r)*(h[0]-mu)/s` and
`z[i]=(h[i]-mu-r*(h[i-1]-mu))/s`. Composing invariant conditional kernels and
the invertible coordinate maps gives the intended invariant distribution in
exact arithmetic. This does not prove finite-chain convergence or numerical
accuracy. Slice exhaustion and numerical failure abort the attempt; neither
returns a partially updated state.

## Checks and next admission gate

Eleven existing/new tests pass. New density-ratio controls compare both
conditionals with the independently implemented full target plus Jacobian at
n=1,7,250. The remap preserves a 250-state physical path to absolute tolerance
5e-14, preserves beta, and leaves the input unchanged. A deliberately exhausted
evaluation budget raises instead of returning a partial draw. Existing tests
cover augmentation integration, Gaussian conditional beta, exact-Gaussian
stationarity controls and slice/ellipse failure handling.

Before performance claims, run a bounded fixed development fixture with
matched target/physical starts, multiple chains, all global/terminal/predictive
diagnostics, counted evaluations and complete end-to-end costs. Compare the
old and interwoven prototypes on the same fixture without discarding failures.
Choose scientific seeds and budgets only after readiness, then freeze them.
Do not occupy cores assigned to the current E72 campaign.
