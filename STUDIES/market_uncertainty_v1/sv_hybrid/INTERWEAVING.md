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

## Full-window literal readiness: mixed results

The separate T250 check completed all eight chains at the same 1000 warmup /
2000 retained schedule. Fresh declared development seeds and a new source
manifest were used. Each chain had a 300-second internal / 320-second external
limit. Existing T32 evidence was preserved rather than overwritten.

| Endpoint | Original bulk ESS | Interwoven bulk ESS |
|---|---:|---:|
| mu | 892.8 | 4306.6 |
| log_sigma | 2649.4 | 2776.2 |
| beta | 4530.5 | 5133.1 |
| h_last | 1391.4 | 1365.9 |

Worst innovation Rhat was 1.00865 original versus 1.01252 interwoven; minimum
innovation bulk ESS was 846.2 versus 894.4. Better mu mixing did not translate
into a uniformly better chain. No convergence verdict is introduced here.

The unchanged predictive evaluator completed GH64/128 numerical checks for
all six fixed labels/methods. Log-density MCSE for labels [-.005,0,.005] was
[.01239,.00297,.01043] original versus [.01274,.00308,.01042] interwoven.
Thus predictive precision did not materially improve on this literal fixture.
The two samplers' log-density estimates differ by approximately .02304,
-.00421 and .01679 nats respectively. No independent reference was fitted, so
neither is declared correct by agreement or by a favorable diagnostic.

Sampling used the default local NumPy 2.5.2 runtime. The first predictive call
failed before scoring because that runtime lacked Numba. A separate Python
3.11 environment could not resolve the pinned SciPy requirement (Python >=3.12).
A new isolated Python 3.14 environment successfully installed the existing AWS
numerical-package pins: NumPy 2.4.6, SciPy 1.18.1, Numba .67.0, llvmlite .49.0,
and ArviZ .23.4. Only postprocessing was rerun; no chain was rerun or discarded.
The dependency list and failed-call log are preserved. Local platform/interpreter
differences still preclude treating these timings as AWS benchmark results.

All results are in `evidence/interwoven-t250-development-20261028/`. The verified
32.3 MB local archive retains 56 sealed files, including full draws, predictive
arrays, logs, exact executed sources and analysis sources. Independent-reference
corroboration and matched predictive precision remain required before a
sampler-superiority claim. This evidence argues against choosing only mu as
the headline efficiency endpoint.

The T250 raw archive also has a private S3 copy: the exact version and restored
SHA-256 are in `S3-VERIFIED.json`. All 56 sealed members were read and checked
from the downloaded version. Original local arrays remain preserved.

## Independent T250 literal reference

The declared four-chain reference completed 2,000 warmup and 4,000 retained
draws per chain, with zero divergences. All 254 coordinate diagnostics passed
the declared Rhat/ESS flags. Its saved trace was reloaded and verified to
contain posterior and warmup draws and both diagnostic groups. The 22.75-second
outer duration includes compilation and serialization on AWS; it is not a
cross-hardware speed comparison with local specialist runs.

All eight compact specialist-minus-reference mean differences were retained.
They were at most about one specialist mean MCSE in magnitude. This descriptive
agreement is useful corroboration, not an equivalence test or proof of fidelity.
The original specialist had no flagged coordinates; the interwoven specialist
retained its z[116] diagnostic flag.

| Fixed label | Original minus reference log density | Interwoven minus reference log density | Reference MCSE |
|---|---:|---:|---:|
| -.005 | -.015424 | .007612 | .003498 |
| 0 | .002574 | -.001638 | .000829 |
| .005 | -.010604 | .006183 | .002769 |

Specialist MCSE remains as reported above; no independence-based combined
interval or selected-label winner is used. All six predictive contrasts are
available. Evidence is in `evidence/literal-reference-result-20261028/`; a
verified 93.8 MB local archive preserves 41 files, including full draws,
compiler artifacts and analysis. Matched-hardware market comparisons,
predictive precision/cost evaluation and longer-path calibration remain
necessary before algorithm-superiority claims.
