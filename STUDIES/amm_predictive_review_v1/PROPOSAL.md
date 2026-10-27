# Next research: predictive quantities and usable posterior updates

2026-10-27. Independent design review; proposal only, not preregistered evidence.
No remote compute, market acquisition, trades, or deployment performed here.

## Objective

Make a posterior-driven AMM research loop computationally practical and statistically
proper. A posterior reference match, predictive calibration, and a pricing decision
are different claims. This proposal addresses the first two interfaces; it does not
claim that spreads are optimal, executable, or profitable.

The immediate highest-value work is to finish WP96/WP97 and verify what their
reported quantities actually mean, before another broad speed sweep.

## Findings that matter now

1. WP96/WP97 gate P50/P95 of next-period *Student-t scale*, not of the next return.
   For a posterior draw theta = (mu, sigma_h, beta, h_last), let
   m = mu + rho*(h_last-mu). Then h_next|theta ~ Normal(m,sigma_h^2),
   scale_next=exp(h_next/2), and return_next|h_next,theta ~ t5(beta,scale_next).
   A P95 scale is not a P95 return, a spread, or a loss limit without an additional
   decision model. Conditional return variance is (5/3)*exp(h_next), not exp(h_next).
2. The WP95 Python documentation example instead computes exp(m/2), the conditional
   median scale. Taking its posterior quantile omits future volatility innovation.
   Known-parameter examples in oracle-results.json understate the true scale P95
   by 15.17% at sigma_h=.2 and 28.03% at sigma_h=.4. The wording and stationary
   boundary example were corrected on main at `35c4aedc`.
3. Generic shifting of noncentered innovations does not preserve the latent path.
   The new stationary initial innovation must be
   z0_new = rho*z0_old + sqrt(1-rho^2)*z1_old; then shift the later innovations.
   This preserves the retained h path, not the new posterior distribution. Any
   diagonal-mass carry is an initialization heuristic, not a covariance transform.
4. WP96's frozen pass excludes latency and observes every 25th tick. All periodic
   re-adaptation ticks are observed; early post-shock ticks and intervening failures
   can be missed. Its success would support sampled-origin posterior accuracy, not
   every-tick operational reliability. Changing a finite window changes the target;
   it is not exact full-history Bayes. Its shift case also changes true global
   parameters while fitting a stationary model inside a window.
5. WP97 uses already-inspected simulation and real-return streams with fresh sampler
   seeds. This confirms Monte Carlo reproducibility on those streams, not fresh-data
   generalization. Cross-tick dependence means 1/sum(w^2) is a weight-concentration
   diagnostic, not an autocorrelation-adjusted effective sample count. Four-chain
   sd/sqrt(4) is a noisy uncertainty diagnostic, not a validated stopping criterion.
6. Both references primarily gate Rhat of h_next after independent innovation is
   added. This can mask poor mixing of mu/log_sigma/h_last. Their sampled-reference
   failure checks also require the reference, so they cannot themselves be an online
   production abstention rule. Supplemental audits of compact draws should retain
   the original verdict and separately assess global/endpoint diagnostics, actual
   MCSE, divergences, and missing-cell denominators. Agents are doing those audits.

## Completed independent implementation checks

Run `python STUDIES/amm_predictive_review_v1/predictive_oracle.py`.

Thirty deterministic checks pass using the installed NumPy/SciPy environment:

- exact lognormal conditional scale CDF, median, mean and quantiles;
- predictive-return quantiles from independent adaptive integration versus
  32/64/128-node Gauss-Hermite integration, including a broad two-component mixture;
- full-mixture scale P95 differs from quantiles of conditional medians;
- eight noncentered window-remap path checks, rho in {0,.5,.95,-.7}.

These are formula/implementation checks; they provide no market calibration result.
At fixed posterior draws, exact marginalization of future Gaussian innovation gives

F_scale(s) = sum_i w_i Phi((2 log(s)-m_i)/sigma_i), s>0.

Its quantile is a scalar monotone root. Predictive return CDF is

F_return(x) = sum_i w_i E_Z[T5((x-beta_i)*exp(-(m_i+sigma_i Z)/2))].

Use quadrature for the inner expectation, checked against independent integration.
Do not call quantiles of exp(m_i/2) Rao-Blackwellized predictive quantiles: averaging
the *CDF* and then inverting is the appropriate mixture calculation.

## Immediate bounded diagnostic, requiring no new sampler cells

On recovered WP96/WP97 compact posterior draws, create a new supplemental directory:

1. At twelve preselected ticks per available reference stream, reconstruct predictive
   scale quantiles from the analytic mixture CDF; compare to the frozen noise-added
   estimate. Selection is positional, never largest observed errors: first, last,
   and ten evenly spaced available *planned* ticks. Missing ticks remain missing.
2. Only for WP97 (which stores beta), recompute return P5/P50/P95 from the full return
   CDF. WP96 and WP88 compact draws store only mu, log_sigma and h_last: their
   full predictive returns are unavailable without additional joint beta draws.
   Do not silently set beta=0, use a point estimate, or independently reconstruct
   a marginal beta: its posterior dependence is part of the predictive mixture.
   Scope their diagnostic to predictive scale. Compare 64 and 128 quadrature
   nodes and 128 versus independent integration on three fixed posterior components.
   Store CDF residuals and solver brackets; errors or failed convergence are results.
3. Report predictive intervals against realized next returns only when the input
   series contains the next observation. Mark these as retrospective diagnostic
   scores on previously used data. Preserve absence at the terminal endpoint.
4. Report conditional scale, predictive scale, predictive return, and observed return
   in separate named fields. Keep frozen study scores untouched.

Budget: 30 wall minutes on one four-core lane, max 4 GiB resident memory via chunking,
no newly sampled cells. This is a hard ceiling, not an estimated completion time.
Before the full pass, time one full-size origin including all solver evaluations
and quadrature checks, cache quadrature nodes and reusable scales, and publish the
measured workload estimate. Full 80,000-draw references at 128 nodes, 20 root
iterations and three quantiles imply approximately 614 million Student-t CDF
evaluations per origin, before the 64-node comparison. Therefore completion inside
30 minutes is unproven. If the estimate exceeds the ceiling, perform only a frozen
prefix of the planned diagnostic origins and retain the full planned denominator;
do not claim full-study coverage. Component subsampling changes the estimator and
must be labeled as an approximation with independently assessed error, never used
silently. If the diagnostic exceeds budget, keep partial outputs and report the
uncomputed denominator. Timing on a laptop is never a qualification.

## Proposed fresh qualification: predictive_functionals_v1 (ID not reserved)

Freeze PREREGISTRATION.md, protocol.json, data hashes, code, exact configurations and
seed manifest before generating/inspecting qualification outputs. The following is
a proposed finite design, not permission to relabel any existing run as qualification.

Question: does deterministic predictive-CDF marginalization reduce the Monte Carlo
budget needed for accurate predictive quantities while keeping total refresh time
bounded, on fresh stationary and regime-shift streams?

### Data and scheduled origins

- Six new 763-return streams, N=250 fixed window, 512 updates: three stationary
  streams and three independent streams with the WP96 parameter shift entering at
  tick 257. Same disclosed rho=.95, nu=5 and priors. Use proper stationary initial h.
- Candidate data seeds 981701..981706; sampler bases 981707..981712. These had zero
  exact-word hits in source/protocol/docs searches excluding artifacts on 2026-10-27.
  They are NOT reserved: full derived-seed collision verification across tracked
  artifacts and all active studies is required before freeze. Smoke seeds 991981,
  991982 are development-only and must also be collision-checked.
- Score at ticks [1,32,64,128,224,255,256,257,258,260,264,272,288,320,384,512].
  These give 96 reference origins and deliberately include consecutive shock ticks,
  unlike WP96's periodic observation schedule. No post hoc replacement of origins.
- Forecast issuance uses y[t:t+250]; realized label is y[t+250]. The 763rd return
  supplies the final tick's forecast label. Retain all 512 scheduled labels.

### Arms and frozen adaptation selection

- Use identical state-mapping and adaptation policy in all arms. Choose policy from
  the completed WP96 report before this freeze: frozen if it passes both streams;
  otherwise the passing policy with lowest worst-stream P99 (ties m100,m500,trig).
  If none passes, postpone qualification and run a labeled adaptation diagnostic.
- K=50 and K=200 per chain; four chains. Evaluate both old noise-added scale estimator
  and analytic scale-CDF estimator on exactly the same posterior draws. The full
  predictive-return estimator uses integrated Gaussian innovation and Student-t CDF.
  This paired design isolates estimator variance from changed Markov transitions.
  Both timing arms must produce the same full predictive-output family: the control
  uses noise-added scale quantiles plus the integrated predictive-return estimator,
  and the candidate uses analytic scale CDF quantiles plus that same return estimator.
  Do not compare a scale-only control's cost with a scale-and-return candidate.
- No WP97 pooling in this first qualification: keep its result separate and avoid
  simultaneous changes to temporal reuse, adaptation, and predictive integration.
  If useful later, combine only in a separately frozen experiment.

### Reference reliability and numerical gates

- Reference at each scheduled origin: four chains, fixed 2,000 warmup/20,000 retained
  draws, same target. Keep all chain outcomes. Predeclare one alternate seed attempt;
  do not silently select a subset by comparing parameter values. If chain removal
  remains necessary, name the exact existing warning rule and show full-chain and
  retained-chain diagnostics separately.
  Share each same-origin reference across candidate arms; there is no reason to fit
  a separate reference per arm. Report the resulting common-reference error and
  correlation instead of treating arm-reference discrepancies as independent.
- For mu, log_sigma, beta, h_last and predictive-CDF functionals require rank Rhat
  <=1.01, bulk and tail ESS >=400, and zero retained divergences. Require estimated
  scale quantile MCSE <=0.2% for P50 and <=0.5% for P95; predictive endpoint MCSE <=
  0.5% of the reference 90% interval width. Estimate functional MCSE using chain-aware
  autocorrelation/batch methods and a delta-method quantile inversion, not weight ESS.
  For scale CDF at q, use per-draw g_i(q)=Phi((2 log(q)-m_i)/sigma_i) and density
  f_i(q)=2*phi((2 log(q)-m_i)/sigma_i)/(q*sigma_i). Estimate chain-aware variance of
  the mean CDF and divide by the squared mean density. Fix and validate the
  autocorrelation/batch estimator before freeze; short K=50 chains do not justify
  an untested asymptotic MCSE or an ESS-based automatic stopping claim.
- Validate the primary oWALNUTS reference against independent nutpie at four fixed
  origins per stream [64,256,272,512] (24 origins), same density/priors and independent
  seeds. A 3-combined-MCSE difference is a descriptive flag, not an automatic
  family-wide rejection rule. Before freeze specify the full endpoint family,
  simultaneous-error rule and fixed follow-up budget. Chance flags cannot trigger
  selective extra seeds or an undeclared veto. Preserve disagreements and follow-up;
  unresolved material differences block reference trust. Do not average samplers
  to erase disagreement.
- Return CDF quadrature 64-versus-128 discrepancy <=1e-6 at solved endpoints, and
  root residual <=1e-8. Failure invalidates that quantity; do not widen tolerance.

### Mechanical decision and scope

- Keep WP88 scale accuracy bars: P50 <=2%, P95 <=5% relative to qualified reference.
- New return endpoint bar: P5/P50/P95 absolute error <=2% of reference P95-P5 width,
  assessed jointly. This is a proposed engineering tolerance, not a trading optimum;
  freeze it before outputs. Report endpoint errors separately so wide intervals
  cannot hide an inaccurate center.
- Practical tick pass requires both quantity families, no failure/nonfinite output,
  and complete target construction+remap+adaptation+sampling+CDF/quantile time <0.4s.
  At least 92/96 scheduled origins and >=15/16 in each stream must pass. Failed
  references, missing and timed-out cells remain in 96, never disappear.
- Claim lower transition budget only if K=50 analytic passes and measured median
  total time is <=0.8 times K=200 noise-added control; report full P95/P99, startup,
  peak RSS and memory growth, and every re-adaptation spike. If K=200 control fails,
  do not describe relative speed as a qualified practical improvement.
- Over all available 512 next-return labels, report empirical coverage, width,
  proper interval score and PIT per stream and pre/post-shift. This is finite
  synthetic model-checking, not real-market calibration. A shifted stream is
  misspecified relative to the stationary-window fit; failure there is informative.
  With only three independent streams per regime, do not use 3,072 dependent ticks
  as independent calibration replications or claim tail-risk qualification.
  Include two named score/width controls: a privileged true-generator predictive
  distribution using the simulated current latent and next-period true parameters
  (an oracle, not an available market strategy), and a causal rolling Student-t5
  baseline with location=median(last 250 returns), scale=MAD/t5.ppf(.75).
  Declare zero-MAD behavior before freeze. PIT values are serially dependent; do
  not use an iid PIT test or call better coverage alone a predictive improvement.
- No real-market superiority, profitability, inventory policy or deployment claim.

### Resources and stop conditions

Two four-core lanes only; no extra instance. Hard cap 120 wall minutes after build,
8 GiB combined experiment memory and 2 GiB new compact artifacts. A diagnostic smoke
must estimate the complete runtime before freeze, including the full-size reference
CDF inversions and all 6 x 512 x 2 online predictive summaries, not sampling alone.
Chunking controls memory but does not reduce the number of CDF evaluations. An
unvalidated node count or component subset cannot rescue a budget silently. If the
full plan cannot fit, reduce the design
before freezing, never after observed outcomes. Use detached processes with PID,
start/end/exit manifests and an overall deadline; no polling shell owns compute.
Commit sources before copying; hash remote executable and inputs. Archive negative
and failed outcomes, preserve original WP96/WP97 artifacts, download summaries and
raw compact draws with SHA256 verification. Stop unused compute after queues drain.

## What should happen after this study

A successful computational qualification permits an honest reusable predictive
summary API and a bounded replay study. Next predictive validation needs genuinely
unseen chronological data blocks and benchmark forecasts, immutable origin records,
explicit missing-data handling and declared regimes. Execution/fill mechanics,
inventory exposure and adverse selection belong to a later decision-model study;
none is established by posterior sample agreement.
