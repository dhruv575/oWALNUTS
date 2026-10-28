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

## Completed literal local development check

The fixed T32 fixture completed all eight chains: four original and four
interwoven, each with 1000 warmup and 2000 retained sweeps. Both methods use the
same physical starting state and target; their declared seed schedules are
disjoint. Methods/chains ran sequentially on the local workstation. All internal
100-second and external 120-second per-chain bounds were respected; no retries
or replacement chains occurred. AWS E72 was not co-scheduled with this work.

| Endpoint | Original bulk ESS | Interwoven bulk ESS | Original mean MCSE | Interwoven mean MCSE |
|---|---:|---:|---:|---:|
| mu | 559.0 | 3416.3 | 0.02752 | 0.01039 |
| log_sigma | 1368.8 | 2412.9 | 0.01235 | 0.00925 |
| beta | 4853.7 | 5040.6 | 0.00000456 | 0.00000446 |
| h_last | 1555.2 | 2336.7 | 0.01379 | 0.01072 |

Original worker times ranged 5.94–6.08 seconds; interwoven 6.46–6.89 seconds.
These include sampling and output compression but exclude process imports;
outer receipts preserve the additional overhead. They are not AWS timing or
end-to-end forecast latency. Full diagnostics include all 32 innovations:
maximum Rhat was 1.00775 original and 1.00541 interwoven. Compact endpoint
means and every chain's evaluation counts are in the saved summary.

This supports proceeding to readiness on a larger target, not a superiority
claim: one literal fixture has no independent posterior reference or predictive
functional evaluation. Existing scientific failures remain unchanged.

Metadata are in `evidence/interwoven-development-20261028/`. The local archive
contains all raw arrays, logs and exact executed source copies; 39 sealed files
were read back from the archive and hash-verified. The receipt gives its path
and SHA-256. The first reporting call failed because local ArviZ 1.3.0 requires
an explicit tail-ESS probability; the corrected report explicitly uses
(0.05,0.95). Sampling was not repeated or changed. This local diagnostic
environment differs from the pinned AWS environment and is labelled as such.

The raw archive is also in the private S3 research bucket. `S3-VERIFIED.json`
records its exact object version, full-byte restore SHA-256 and verification
of all 39 sealed members read from that restored archive. Local evidence is
retained; no active experiment dependency was removed.
