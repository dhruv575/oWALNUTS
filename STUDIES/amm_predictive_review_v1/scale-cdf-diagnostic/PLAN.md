# Bounded archived scale-CDF diagnostic

Written before computing this diagnostic's outcomes, 2026-10-27. Post-hoc
implementation/estimator diagnostic on previously inspected WP88 data, not a new
qualification study. No sampling, remote compute, or archived-file mutation.

## Fixed selection and comparison

- Datasets: sim-N250, real-N250, in that order.
- Ticks: 2, 50, 100, in that order; no outcome-based substitution.
- One original gated reference at each of these six origins.
- Warm cells: K=50,100,200; seeds 880101,880102,880103; 54 planned warm rows.
- Use every stored compact draw (mu,log_sigma,h_last), its original chain
  selection and the original WP88 innovation seed/index mapping. Reference files
  select their recorded kept chains. Warm files already contain the carried chain
  set; preserve their original noise-row behavior from WP88 analyze.py.
- Compute the analytic posterior-mixture scale CDF
  F(s)=mean(Phi((2*log(s)-m_i)/sigma_i)), m_i=mu_i+rho*(h_last_i-mu_i),
  sigma_i=exp(log_sigma_i). Invert at probabilities .5 and .95 with Brent's method
  on log scale. No thinning, conditional-median substitution, quadrature, or beta
  imputation. Compact draws omit beta, so no predictive-return computation.
- On exactly the same warm draws compare the original noise-added quantiles
  (NumPy default linear quantile, WP88 eps stream) and the deterministic mixture
  quantiles against the reference deterministic-mixture quantiles. Also show the
  reference original-noise versus deterministic difference.
- Descriptive tolerance indicators use WP88's 2% P50 / 5% P95 bars jointly.
  They are not WP88's full pass rule: no new latency, drift or sampling-health
  qualification is inferred. Missing/invalid rows stay in 54 and count as not
  within tolerance in denominator summaries; no imputations or reruns.

## Validation, uncertainty and resources

1. Before reading draw outcomes, validate the CDF against exact one-component
   lognormal quantiles and an identical-component mixture; validate monotonicity
   and root residual <=1e-10. Then validate the first reference CDF similarly.
   Later references and warm rows retain numerical residuals and brackets.
2. Require finite draws and finite positive sigma; reject bad shapes and duplicate
   tick records. Bounds are min(m-12*sigma), max(m+12*sigma) for log-volatility,
   which bracket the selected probabilities. Solve log-volatility quantiles and
   exponentiate half the root; solver atol=1e-12, rtol=1e-12.
3. Reference uncertainty remains posterior Monte Carlo uncertainty after removing
   future-innovation simulation. Report a chain-aware delta-method estimate where
   available: ArviZ MCSE of g_i=Phi((log-vol quantile-m_i)/sigma_i), divided by the
   scale density mean(2*phi(z_i)/(q*sigma_i)). Preserve per-row caveats: one shared
   same-sampler reference per origin, no independent-sampler validation, and its
   MCSE estimate is asymptotic. No automatic stopping or pass-confidence claim.
4. Preserve input SHA256s (protocol, original analyzer, logs and selected raw files),
   source/plan hashes, package/platform versions and original chain metadata.
5. Five-minute computation ceiling, processing dataset then tick then K then seed.
   Check the deadline before every origin/row and inside CDF evaluation. Preserve
   unprocessed rows as budget-exhausted. Local end-to-end origin processing time
   includes file I/O, hashes, reference diagnostics and all nine warm comparisons;
   it is not sampling latency or production quoting performance. Also report the
   local deterministic solver timing solely to assess postprocessing cost.

The output supports only a decision whether analytic scale-CDF marginalization
merits a fresh, independently reviewed experiment. Three ticks per dataset cannot
establish a passing transition budget, calibration, or AMM usefulness.
