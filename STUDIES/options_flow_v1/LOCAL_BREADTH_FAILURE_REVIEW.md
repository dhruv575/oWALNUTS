# Exploratory breadth failures: local-level 00 and flow 22

Read-only review of completed cells, 2026-10-03. No new numerical imports,
sampling, tests, trace calculations, or parameter tuning were performed. This
document does not alter any planned cell, denominator, threshold, or seed.

## Local-level 00 is a shared computational failure

The fixture is `artifacts/breadth-v1/fixtures/local_level-00.json`: T=128,
Student-t degrees of freedom 5, unit time increments, an exogenous initial-state
anchor of zero, and a prior-predictive draw of both scale parameters. It is not
the empirical-Bayes first-observation anchor convention. Initialization uses the
existing observed-path starts with deterministic chain offsets; it does not use
generating truth.

Both completed precision controllers exhausted the fixed 1000,2000,4000,8000
retained-draw tiers per chain and failed. They are stored under
`artifacts/breadth-v1/cells/local_level-00-autodiff` and
`artifacts/breadth-v1/cells/local_level-00-numpyro`. Every tier has zero reported
retained divergences. Zero divergences therefore does not establish usable
sampling in this example.

At the final 8000-draw tier:

| Diagnostic | oWALNUTS autodiff, centered | NumPyro, centered |
|---|---:|---:|
| sigma_obs rank R-hat | 1.03124 | 1.04057 |
| sigma_obs bulk ESS | 116.98 | 94.97 |
| sigma_obs tail ESS | 171.04 | 129.82 |
| sigma_rw rank R-hat | 1.00473 | 1.00760 |
| sigma_rw bulk ESS | 850.14 | 698.18 |
| terminal latent rank R-hat | 1.01023 | 1.00950 |
| maximum endpoint MCSE / width | .021755, terminal latent | .024849, sigma_obs |
| next-observation endpoint MCSE / width | .003836 | .004158 |

The oWALNUTS candidate also fails rank R-hat on several other latent coordinates
(`q_14`, `q_27`, `q_37`, `q_53`, `q_55`, `q_72`, `q_74`, `q_93`, `q_101`, and
`q_127`), despite large bulk ESS for many of those coordinates. NumPyro has the
same qualitative issue on many latent coordinates, as well as `h_initial` and
`h_mean`. `q_128` is log observation scale, not another latent path value.
Rank R-hat and bulk ESS measure different features; high location ESS does not
override a scale/mixing warning. Per-chain width differences are a plausible
explanation, but have not been calculated in this read-only review.

The candidate sigma_obs endpoint ratio is .018034, below the nominal 2% limit,
while its R-hat and ESS still fail badly. This is a concrete reason to retain
both health and precision gates. Conversely, both next-observation intervals
look numerically precise under the current estimator while the posterior fit
is unhealthy. Observation-noise draws cannot certify latent or scale mixing.

The oWALNUTS controller charges 18.007 seconds across all four restarted tiers;
the NumPyro controller charges 68.746 seconds. These are recorded costs of two
unsuccessful procedures, **not time-to-success or a usable speedup**. Each remains
one failed planned cell with its complete cost in the intended denominator.

## Why a centered recipe can win a fixed pilot yet fail here

The pilot used fixed, moderate generating scales. This fixture draws scales
from their declared log-normal priors and produces a different realized
allocation of variation between path increments and measurement noise.
For diagnostic context only, the stored generating scales are sigma_obs
0.117107 and sigma_rw 0.285361. The final unhealthy fits put sigma_obs means
near .054 and sigma_rw means near .362; their approximate 90% intervals are
[.013,.112] / [.315,.408] for oWALNUTS and [.015,.112] / [.315,.407] for NumPyro.

These numbers suggest investigating the low-observation-noise region and the
tradeoff between latent-path roughness and observation residuals. They do not
prove a biased sampler: a generating parameter need not lie inside every 90%
posterior interval, and the fits have not established convergence. Agreement
between two unhealthy fits does not make either an accuracy reference. Generating
truth must not become a metric, initialization, or future tuning input.

In centered coordinates the likelihood can concentrate the full latent path
near the observed path as sigma_obs becomes small. Moving sigma_obs then changes
the allowed width of many residual coordinates together. A diagonal metric
learned at one scale need not traverse this changing width efficiently. A
flexible random-walk scale also permits competing allocations of local movement
to the path versus noise. This is a plausible posterior-geometry mechanism
consistent with the shared slow sigma_obs direction; trace/correlation evidence
is still needed before treating it as established.

The existing noncentered implementation whitens **random-walk innovations with
sigma_rw**. It does not directly whiten observation residuals with sigma_obs.
Prior noncentering can help when the path is weakly observed, but with informative
observations it can introduce strong likelihood coupling across innovations.
It is therefore not justified to assume that simply switching to the existing
noncentered arm fixes this particular failure. Nor does this one prior draw
invalidate the centered recipe in the different pilot regime.

## Follow-up experiments after the frozen batch ends

1. Diagnose the completed cells using per-chain log-scale traces, residual and
   increment energy, chain-specific endpoint estimates, autocorrelations, depths,
   and adapted step sizes. Check whether sigma_obs occupancy differs among
   chains and whether movement of residual energy tracks the slow scale. Preserve
   the original failed reports and record any additional analysis separately.
2. Compare centered and the existing process-noncentered coordinates on both
   backends as an explicitly exploratory mechanism control, with identical
   canonical starts and complete failed-fit costs. Do not silently replace the
   originally planned arm or extend its budget until it happens to pass.
3. If the observation-scale mechanism is supported, a separate candidate is
   observation-residual coordinates `h_t = y_t + sigma_obs*z_t`. This uses fixed
   training observations, not truth. Its Jacobian is T*log_sigma_obs and cancels
   the observation scale normalizers; the random-walk/initial priors must still
   be evaluated at the reconstructed physical path. Such a transform could move
   stiffness into the process prior, so it is a testable alternative rather than
   an announced solution. Require independent density/gradient/Jacobian parity,
   exact start/draw conversion, matching reference coordinates, and fresh-seed
   confirmation if it shows promise. No such implementation was made here.
4. Broader prior regimes remain necessary. Freeze any recipe-selection rule using
   available training data or declared warmup diagnostics, not generating scales
   or whichever candidate wins this cell. Charge diagnostic/pilot selection work.

## Flow 22 is a different failure mode

`artifacts/breadth-v1/cells/flow-22-autodiff-noncentered` reaches the maximum tier
with a healthy report and zero divergences, but fails the endpoint rule:
beta_bar ratio .024873 and tau ratio .021651. Their bulk ESS values are 5424 and
7597, tail ESS 3448 and 4833, and rank R-hat 1.00150 and 1.00062 respectively.
The larger errors are on the upper endpoints. Other selected functionals and
forecasts pass their endpoint checks.

That is a precision-budget failure, not the local-level scale-mixing failure.
It illustrates why an ESS threshold alone cannot guarantee a fixed quantile
error relative to width. Endpoint-specific distribution shape and the MCSE
estimator matter. The independent endpoint-replication experiment in
`ENDPOINT_VALIDATION_PLAN.md` is the appropriate next validation of that claim;
an arbitrary geometry change or threshold relaxation is not established by
these observations. The original cell remains failed under the declared policy.

### Post-run scale diagnosis (exploratory)

`artifacts/local-00-scale-diagnostic-v1.json` binds both 8000-draw raw inputs
and reports by SHA256. No new sampling was performed. The diagnostic uses
observations and retained draws, not generating truth. Both posterior fits
remain unhealthy; neither is treated as a reference truth.

The pooled correlation of log observation scale with log residual RMS is
0.988 in both fits (within-chain correlations 0.981–0.992). After dividing
residuals by observation scale, that correlation falls to −0.116 for AD and
−0.104 for NumPyro. Log observation scale autocorrelation at lag 100 reaches
0.579 and 0.565 respectively. The fraction of each chain below observation
scale 0.02 ranges from 3.4–19.3% for AD and 4.2–18.2% for NumPyro. These
descriptive cutoffs were chosen after observing the failure, not used as gates.

This supports testing observation-residual coordinates
`h = y + exp(log_sigma_obs)*z`: the exact Jacobian cancels the observation
scale normalizer, making its Student-t factor independent of observation
scale. It does not establish faster mixing: the latent random-walk prior now
couples these coordinates, and the observed log-scale correlation remains
−0.423 (AD) and −0.441 (NumPyro). The candidate therefore needs independent
normalized-density and gradient parity followed by a frozen paired experiment.
Existing centered results and failure denominators remain unchanged.
