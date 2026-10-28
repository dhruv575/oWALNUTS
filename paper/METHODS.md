# Methods — working manuscript

This section describes implemented research methods. It is a draft for the
submission manuscript; statements about scientific success are reserved for the
results section and are limited by the evidence in each study.

## Statistical target

For a window of n=250 half-hour log returns y, the model is

\[
y_i\mid h_i,\beta\sim t_5(\beta,\exp(h_i/2)),\qquad
h_1=\mu+\frac{\sigma z_1}{\sqrt{1-\rho^2}},\qquad
h_i=\mu+\rho(h_{i-1}-\mu)+\sigma z_i,
\]

where \(z_i\sim\mathcal N(0,1)\), \(\rho=0.95\), and \(\sigma=\exp(\ell)\).
The independent priors are

\[
\mu\sim\mathcal N(2\log(0.005),1),\quad
\ell\sim\mathcal N(\log(0.2),0.5^2),\quad
\beta\sim\mathcal N(0,0.002^2).
\]

The Student-t parameter \(\exp(h_i/2)\) is a scale, not a standard deviation:
conditional return variance is \(5\exp(h_i)/3\). The unconstrained parameter
vector is \((\mu,\ell,\beta,z_{1:n})\), of dimension 253. The target is a
rolling-window posterior, not a filtering posterior conditioned on all past
observations. Dropped observations cease contributing to the likelihood.
This distinction also matters for interpreting comparisons with an EWMA control
that retains longer historical variance memory.

The model is implemented independently in a Stan program and a compiled
log-density/gradient callback. Existing literal-fixture parity tests establish
agreement at their checked points; they do not constitute a mathematical proof
that arbitrary implementations agree everywhere. The frozen study manifests
identify the executed sources, native binaries and runtime packages.

## Transition kernel and rolling initialization

oWALNUTS implements the WALNUTS method of Bou-Rabee, Carpenter, Kleppe and Liu
(2026). The original transition algorithm and its reversibility arguments belong
to that work. Our research concerns the concrete implementation, repeated-target
workflow and evidence required for predictive and economic use. A theoretical
stationary-kernel property does not imply that a short run initialized from a
previous target is already distributed according to the new posterior.

Each monthly path initializes four chains with 1,000 warmup and 200 retained
draws. The initial adaptation uses target acceptance 0.8 with step-size and
diagonal-mass adaptation and the configured trapped-chain guard. During subsequent
updates, a persistent session retains step sizes and metric and applies the
unchanged transition kernel to each new window. It does not run a new full
adaptation at every observation.

When the oldest return is removed, the noncentered state is remapped. The first
new innovation is

\[
z'_1=\rho z_1+\sqrt{1-\rho^2}\,z_2.
\]

This identity preserves the previous second latent log-volatility as the new
first latent value, conditional on unchanged parameters. Remaining retained
innovations shift left and the appended innovation initializes at zero. The
retained first diagonal-mass element follows the implemented heuristic rather
than an asserted exact pushforward of a full covariance matrix. Neither this
coordinate identity nor the zero append is a draw from the new posterior.
Finite-budget approximation must therefore be checked empirically.

E66 uses K=400 transitions per chain per update. E72 varies K in {400,1600}
and uses two seed schedules per month. Paired budget arms share their declared
seed schedule but consume different numbers of transitions; they must not be
treated as independent replications. Independent month histories also do not
make adjacent market months independent market regimes.

## Predictive distribution

For a stored posterior draw \(\theta=(\mu,\ell,\beta,h_n)\), next-period
log-volatility obeys

\[
H_{n+1}\mid\theta\sim\mathcal N(\mu+\rho(h_n-\mu),\exp(2\ell)).
\]

The predictive density averages the conditional Student-t density over this
future innovation and then over equally weighted draws and chains. It is not
the density evaluated at a posterior mean or median volatility. Log density is
computed as the logarithm of the mean density, not the mean log density. The
predictive CDF uses the analogous mixture, and its value at the observed return
defines the PIT. Quantiles, when evaluated, are roots of the complete mixture
CDF rather than averages of per-draw quantiles.

The existing evaluators compare 64- and 128-node Gauss–Hermite quadrature and
retain their disagreement and root residual diagnostics. Agreement between
these rules does not certify arbitrary quadrature error and does not address
posterior Monte Carlo error. Future-volatility innovation is integrated rather
than omitted from the predictive scale.

## Reference and approximation diagnostics

Independent reference fits use the same model through nutpie/BridgeStan. E66
uses four chains, 2,000 warmup and 4,000 retained draws per chain. E70 uses fresh
seeds and 16,000 retained draws, leaving the other settings unchanged. Its 24
points are the original fixed schedule, including the original reference failures.

For the original joint gate, rank Rhat must be at most 1.01 and bulk and tail
ESS at least 1,000 for each recorded parameter/predictive functional. There must
be no retained divergence; predictive PIT MCSE must be at most 0.005 and
log-density delta-MCSE at most 0.01. These are operational diagnostics rather
than a proof of posterior correctness. Extending a run also creates more
opportunities to observe a rare divergence, so pass counts alone do not measure
precision improvement.

If \(d_{c,s}\) is the conditional predictive density contribution, the
log-density MCSE diagnostic is estimated as

\[
\operatorname{MCSE}(\log\bar d)\approx
\operatorname{MCSE}(\bar d)/\bar d.
\]

Density contributions are rescaled by a common log-density maximum for numerical
stability; chain identity is retained for the mean-MCSE calculation. PIT MCSE
is computed from the CDF contributions. These estimates describe finite-chain
uncertainty and are not validated stopping rules. Candidate/reference differences
and each side's uncertainty are reported separately, with failing references
flagged rather than silently serving as ground truth.

## Evidence and uncertainty boundaries

Four types of uncertainty are distinguished: future-outcome uncertainty under
the predictive model, finite-posterior-sampling uncertainty, numerical integration
error, and empirical uncertainty in forecasting or decision performance over
dependent market observations. Improving one does not establish improvement in
the others. Earlier historical score studies use their frozen circular-block
intervals and sensitivity block lengths; those intervals are not guarantees
against arbitrary longer dependence or a substitute for fresh replication.

Historical close-time conventions do not establish live availability or fills.
All failed fits, missing slots and changed operational attempts remain in their
study denominators and provenance. A study introduced after inspecting prior
outcomes is labelled exploratory even when its subsequent computational schedule
was fixed before execution.

## Economic quantities and accounting

The Student-t log-return model has an infinite positive exponential moment,
even conditional on finite parameters. Thus expected future price and some
unbounded dollar-payoff objectives are not finite. A finite empirical mixture
of posterior parameter draws does not remove this observation-tail property.
Finite realized backtest values do not establish finite model-based expected P&L.

E67 instead considers the bounded long-downside variable
\(Y=\max(1-\exp(R),0)\in[0,1]\), with retaining versus converting at a fixed
hypothetical cost. That repeated-endowment decision is not a self-financing
trading strategy and omits upside opportunity cost. E68's cost sensitivity is
exploratory and cannot choose an economically justified cost by its best result.

E69 introduces a separate pathwise constant-product accounting oracle with
carried reserves and retained input fees. It checks conservation and the
separation of inventory exposure from trading P&L. It has no calibrated
uninformed demand, gas, protocol-fee, integer-token or executable venue model.
It therefore provides accounting infrastructure, not AMM profitability evidence.

## Primary references and source anchors

- Bou-Rabee, Carpenter, Kleppe and Liu (2026), *The Within-Orbit Adaptive
  Leapfrog No-U-Turn Sampler*, JMLR 27(113), 1–64:
  https://www.jmlr.org/beta/papers/v27/25-1452.html .
- Milionis, Moallemi, Roughgarden and Zhang, *Automated Market Making and
  Loss-Versus-Rebalancing*, version 6: https://arxiv.org/abs/2208.06046v6 .
- Target: STUDIES/independent_sv_reference_preflight_v1/model.stan and
  STUDIES/resident_predictive_harness_v1/sv_target.py.
- Continuation: STUDIES/prior_predictive_validation_v1/resident_adapter.py;
  E72's exact source-change audit is in STUDIES/warm_budget_factorial_v1.
- Predictive and reference diagnostics: STUDIES/fresh_real_value_v1/run_reference.py,
  STUDIES/reference_precision_extension_v1 and STUDIES/candidate_reference_audit_v1.

Before submission, replace working source paths with stable repository revisions
and versioned archive identifiers, complete the literature review, and independently
review the mathematical and empirical claims. No theorem of novel sequential
tracking accuracy is claimed by this draft.
