# A minimal order-flow stochastic-volatility workflow

**Proposal, not executed evidence.** Build a one-asset, heavy-tailed return model with latent volatility before adding a large cross-contract hierarchy. The point is useful return uncertainty and a falsifiable computational comparison. Neither a weak flow coefficient nor a negative prediction result makes the sampler useless. Existing exact regression remains a baseline/oracle, not a substitute for this demanding latent-path problem.

This follows the wiki's prospective targets, immutable outcomes, matched starts and retained negative results (`wiki/methods.md`). Existing `dynamic_masked_target.py` explicitly snapshots runtime arrays and resets adaptation for a changed posterior; continuation currently promises one immutable target. Those contracts constrain any hybrid implementation.

## Observable target and causal inputs

At fixed 30-minute receipt-clock origins t, predict

\[
r_{t+1}=\log(M_{t+1}/M_t),
\]

where M is the independently subscribed BTC-PERPETUAL bid/ask midpoint. This is neither a BTC index return nor executable PnL. Use only open, uncrossed, fresh received quotes. Preserve missing anchors, unknown flow, gaps and unissued forecasts in the scheduled denominator. Local receipt freshness is explicit; it is not proof of exchange quote age or a price change.

Let z_t contain an intercept, the preceding observed 30-minute return, signed/total raw option amount (zero only in a known empty bin), and log(1+total amount), all available at the origin. The flow window is the preceding 15 minutes; amounts are not delta exposure. Fit standardization on the training prefix only and freeze it for a declared evaluation block. Future returns, option marks, and future flow do not define current features. Unknown flow cannot silently become zero; compare a price-only forecast on its own eligible origins and all models on the common eligible intersection.

## First model: static mean, latent volatility

Use fixed nu=5 initially:

\[
r_{t+1}\mid h_{t+1},\beta \sim t_\nu(z_t^\top\beta,\exp(h_{t+1}/2)),
\qquad
h_{t+1}=\mu+\rho(h_t-\mu)+\sigma_h\epsilon_{t+1},\quad\epsilon\sim N(0,1).
\]

Stationary h_0 has variance sigma_h²/(1-rho²). The Student-t argument above is **scale**, not variance: observation variance conditional on h is exp(h)*nu/(nu-2). Use a diagonal proper Gaussian prior on beta, proper priors on mu/log sigma_h, and either prospectively fixed rho or a transformed proper prior bounded inside (-1,1). Specify numeric prior scales after checking prior-predictive plausibility in native 30-minute log-return units, before fitting outcomes. Do not transplant the synthetic options study's volatility scale blindly into market returns.

Missing observation rows omit the return likelihood but retain every volatility transition on the scheduled grid. A missing mean covariate makes that row ineligible for the flow likelihood unless an explicit covariate model is added. Do not compress irregular rows into unit-spaced latent time. Initially use one-step forecasts; multi-step forecasts require an explicit future-covariate scenario or a separate covariate model.

For each posterior draw, simulate h_{T+1}, then Student-t observation noise. Quantiles of these simulated returns are **posterior predictive intervals**. Quantiles of beta are parameter **credible intervals**. Quantiles of z_T' beta are credible intervals for conditional location and are narrower because they omit observation noise. None is automatically a frequentist **confidence interval**. Repeated-dataset parameter coverage or time-ordered predictive coverage must be measured for its own declared estimand; sampler Monte Carlo error is a further, separate uncertainty layer.

The smallest implementation is the fully normalized joint density with a noncentered AR path and static beta, sampled by oWalnuts and a matched independent reference. Preserve the exact likelihood constant and transformation Jacobians. This needs no new hybrid API, uses the existing immutable CFunc ownership contract, and provides a trustworthy comparator for any later block sampler.

### The ambitious extension: flow may predict risk without predicting direction

A near-zero beta-flow coefficient does **not** imply flow is useless for uncertainty. Add a separately shrinkage-regularized, low-dimensional term in the volatility transition:

\[
h_{t+1}=\mu+\rho(h_t-\mu)+\gamma' w_t+\sigma_h\epsilon_{t+1},
\]

where w_t contains centered log(1+raw volume) and absolute flow imbalance, available at t. This is a model of scale/tail risk, not causal market impact. The initial Gaussian AR prior is then a declared baseline-state prior conditional on the observed covariate history, not a claim of unconditional stationarity under arbitrary w. Keep nu fixed initially to avoid confounding a time-varying tail parameter with volatility on short data. Later compare a fixed-nu heavy-tail model against Gaussian observation noise; do not infer tail calibration from central 90% coverage alone.

Predeclare the four combinations of flow in mean/scale: neither, mean only, scale only, both. Inspect held-out interval score and tail exceedances at frozen probability levels, plus coverage in prospectively defined high/low-volume and volatility groups. Group cutpoints come from training only; report their sample counts and widths, and multiplicity when making simultaneous claims. A scale-only model can be valuable even when directional prediction remains weak. Too few tail events yields unresolved tail evidence, not permission to pick a less demanding tail after inspection.

Conditional coverage is an empirical diagnostic on these declared groups, not a distribution-free guarantee for every possible conditioning event. The limitations are substantive even for independent data; see [Barber, Candès, Ramdas and Tibshirani, The limits of distribution-free conditional predictive inference](https://arxiv.org/abs/1903.04684). Dependence and changing market regimes further prevent invoking ordinary exchangeable conformal guarantees; [Conformal prediction beyond exchangeability](https://arxiv.org/abs/2202.13415) explicitly treats robustness to these violations rather than granting arbitrary-dependence coverage.

## What exact conditional sampling can and cannot do

Introduce Student-t precisions lambda_t ~ Gamma(nu/2, rate nu/2):

\[
r_{t+1}\mid\lambda_t,h_{t+1},\beta
\sim N(z_t'\beta,\exp(h_{t+1})/\lambda_t).
\]

Given beta,h and an observed return, lambda_t has Gamma shape (nu+1)/2 and rate (nu+(r-z'beta)²exp(-h))/2. Given h,lambda, static beta has an exact weighted Gaussian regression conditional. This is an inexpensive exact block, not FFBS.

If evidence later justifies beta_t following a Gaussian state transition, then conditional on h,lambda and transition parameters, the beta path is a **linear Gaussian state-space model**. Kalman filtering followed by backward sampling gives exact FFBS draws for that block, including missing observation updates. [West and colleagues' conditionally Gaussian dynamic-model treatment](https://www2.stat.duke.edu/~mw/rpmwRSSC2001.pdf) provides the relevant framework. This extension adds nonstationary mean flexibility and identifiability risks; do not add it solely to create an FFBS benchmark.

**The log-volatility block is not linear Gaussian even after Student-t mixing.** Its likelihood includes h and exp(-h). Ordinary Kalman FFBS on h is therefore not exact. Log-squared residual mixtures, such as [Kim, Shephard and Chib's stochastic-volatility construction](https://www.nuffield.ox.ac.uk/economics/papers/1996/w26/Chib8.pdf), approximate a non-Gaussian disturbance with a normal mixture. Any such approximation needs explicit correction or approximation-error assessment; zero residuals and extreme values cannot be hidden by arbitrary offsets. Initial hybrid scope should use exact gamma/Gaussian updates plus an oWalnuts transition for the genuine nonlinear volatility conditional, compared with the full-joint implementation. No claim of exact independent posterior draws follows: this remains correlated MCMC.

## Required conditional-target API contract

Do not mutate CFunc data behind an active continuation session. A Gibbs update to beta or lambda changes the target seen by the h kernel even if dimensionality is unchanged. Cached potential/gradient and any cached trajectory state must be invalidated/recomputed at that boundary. Keep q only, discard momentum/trajectory caches, and apply the next transition to the new conditional with fixed retained-sampling tuning. Per-chain conditional buffers must be owned or immutably snapshotted; no shared mutable user_data across parallel chains. A block step needs a target-generation identity recorded with diagnostics and callback accounting.

A warmup phase may adapt the block kernel within the overall chain; retained transitions must use a frozen tuning/metric policy. Re-adapting at every Gibbs update is not an automatically valid stationary MCMC kernel. Conversely, replacing the entire historical dataset creates a different posterior: start a new fitting procedure with fresh adaptation, unless a separately validated sequential algorithm is used. Compilation reuse is distinct from posterior/session reuse.

Minimal future API work: an internal research-only `conditional_step(q, immutable_context, frozen_tuning, rng, budget)` that guarantees reevaluation on context change and retains no conditional-dependent cache. Test an analytic Gaussian two-block Gibbs target, alternating deliberately different contexts, against a cache-disabled oracle; test parallel buffer independence, generation mismatches, failure/cancellation lifetime, and global callback budgets. Do not expose this as production continuation until invariance and ownership tests pass.

## Falsifiable comparisons and stopping scope

1. **Model value:** exact Gaussian regression; Student-t constant-volatility regression; price-only SV; flow-in-mean, flow-in-scale, and combined SV. Compare interval score, width, conditional coverage, tail exceedances, observed/issued fractions, and predeclared day/regime slices on common origins. A wider model does not win merely by covering more observations. Keep no-flow/negative-flow findings.
2. **Sampler value:** full-joint oWalnuts versus the strongest matched reference on exactly the same target, starts and prediction definition; then a hybrid variant if implemented. Charge adaptation, compilation, block updates, reporting and all failed attempts. Require adequate diagnostics and interval Monte Carlo precision before comparing usable time. The hybrid must improve reliable end-to-end uncertainty delivery, not just one cheap conditional draw.
3. **Causal validation:** freeze calendar fit/calibration/test blocks and recipe before test outcomes. Preserve actual issuance timestamps; historical as-of replay is labelled separately. Delayed labels are joined only after maturity. Use blockwise uncertainty or multiple genuinely distinct periods rather than independent-binomial assumptions for dependent returns. A 48-hour capture supplies at most 96 scheduled half-hour intervals, with fewer eligible labels; it is a feasibility run, not broad regime calibration.

Implementation order is deliberately short: immutable full-joint SV density and independent gradients/simulator; prior-predictive scale check; small same-target sampler correctness check; chronological receipt replay with honest insufficient-history outcomes; a bounded prospective interval comparison once enough labels exist. Exact beta/lambda conditionals and an internal cache-reset block step are the subsequent research optimization, not prerequisites for testing the market model. No sampling or acquisition was performed for this design.
