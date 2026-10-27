# Predictive-value screen: independent design review

2026-10-27. Proposal/review only, not a frozen execution plan and not scored
outcomes. Coordinate the final plan in STUDIES/predictive_value_diagnostic_v1;
first inspect existing forecast studies to avoid redundant artifact work.
No new sampling or remote compute is required by this design.

## Separate the three claims

At a common origin, reference log score minus causal baseline log score measures
retrospective model value, subject to reference approximation. Warm log score minus
reference log score measures inference approximation impact. Their sum equals warm
minus baseline exactly. Keep this decomposition at every origin. None establishes
profit, executable quotes, adverse-selection protection or an inventory policy.
A numerically exact but predictively poor posterior is not a useful forecast.

WP97 posterior at tick t conditions on y[:250+t]. Its NEXT label is y[250+t], not
y[249+t], the newly assimilated observation. Both archived streams contain labels
for all ticks1..100: simulated data have1100returns and real data682. Exclude tick0
uniformly if retaining the original100-update study scope. Use unpooled K200 joint
mu/log_sigma/beta/h_last draws, all three original sampler seeds, and the selected
reference attempt/kept chains under original rules. Do not optimize seeds, origins,
chains or reference attempts using predictive scores. Missing rows remain in their
planned100-per-stream denominator; pairwise availability must be explicit.

The simulated and real streams are separate populations; three sampler seeds are
not three independent observed streams. The real forecast interval spans only100
successive30-minute returns, approximately50hours. Previous use of these data for
method development prevents a clean unseen-data generalization claim even when
each individual forecast respects its causal information boundary.

## Stable predictive density and coherent PIT

For each joint posterior draw, m=mu+.95*(h_last-mu), sigma=exp(log_sigma),
h=m+sigma*z. With normalized Gaussian quadrature weights w_j and z_j:

log g_i(y)=logsumexp_j(log w_j + log t5(y; beta_i, exp(h_ij/2)))
log p(y|past)=logsumexp_i(log g_i(y))-log(number of retained draws).

Use log t5=log(8/(3*pi*sqrt(5)))-h/2
             -3*logaddexp(0,2*log(abs(y-beta))-h-log(5)).
At y=beta, the log-absolute term is -infinity and logaddexp returns0.
This is the log of the posterior mean density, not the posterior mean log density.
Do not compute small densities and then take their logarithm or clip scores.

PIT is the posterior mean of the same GH-integrated t5 CDF at that observed y.
Use unchanged validated exact-t5 CDF, GH64/128, full joint draws and normalized
weights. Proposed pre-output numerical checks: absolute64/128 log-density difference
<=1e-6 nats and PIT difference<=1e-6; validate independently before adopting these.
A failure is an explicit unavailable numerical output, never silently fewer rows.
Log scores are in nats per log-return observation; absolute density scores depend
on units, while paired differences with identical units do not.

Deterministic implementation checks before observed scoring:

- At common beta, p(beta)=mean_i c5*exp(-m_i/2+sigma_i^2/8), a known exact moment;
  PIT(beta)=.5 for a common location, including a mixture of volatility components.
- Direct independent adaptive integration on fixed narrow/broad sigma mixtures,
  recording integration error and a tail bound, not just agreement between orders.
- Finite-difference derivative of predictive CDF agrees with predictive density
  on fixed fixtures, with two step sizes and declared truncation tolerance.
- Translation and positive-scale equivariance: shifting y/beta preserves PIT and
  log density; scaling y/beta by a and shifting m by2log(a) preserves PIT and
  subtracts log(a) from log density. Mixture permutation must not change results.
- Nu=5, finite positive scales, normalization and extreme IEEE handling are checked.

For independent Gaussian-tail truncation at |z|<=L, t5 density is bounded by
c5*exp(-m/2-sigma*z/2). The omitted integral is at most
c5*exp(-m/2+sigma^2/8)*[Phi(-L+sigma/2)+Phi(-L-sigma/2)].
This supports an explicit absolute integration-error bound; very small predictive
densities also need relative-error control through scaled/log-space integration.

## Small causal baseline family

Primary baseline: rolling250-observation Student-t5 location/scale MLE, using
exactly y[t:t+250]. Freeze deterministic multistarts, optimizer limits and convergence
checks before outputs. Candidate starts are mean/median locations crossed with
std*sqrt(3/5) and MAD/t5.ppf(.75) scales. Optimize location/log-scale; floor scale at
1e-8 log-return units and report every floor hit. A failed fit remains missing;
any fallback must be specified before outcomes, not invented to improve scores.
Use a scaled location coordinate to avoid severe optimizer conditioning.

Second primary baseline: Student-t5 EWMA variance with lambda=.94 fixed in advance.
Location mu0 and scale s0 are fit using only the first250returns. Initialize
v0=(5/3)*s0^2; after each newly observed return update
v_t=.94*v_(t-1)+.06*(y[250+t-1]-mu0)^2.
Forecast location stays mu0 and Student-t scale is sqrt(3*v_t/5), with the same
explicit floor. The5/3 factor is essential: Student-t5 scale is not standard deviation.
Third primary baseline: reuse the existing exact Normal-Inverse-Gamma AR1 price
forecast, replacing the optional static t5 control. With n=250+t observed returns,
training target indices are k=max(1,n-256),...,n-1; predictors are [1,y[k-1]] and
responses y[k]. Forecast design is [1,y[n-1]]. The first origin has250mature pairs,
then at most256; the existing minimum-history20 requirement is satisfied.
Standardize the lag predictor only using training mean/population sd (ddof0);
replace sd<=1e-12 by1 exactly as the original implementation. Never standardize
using the forecast outcome or rescale the response. Use a0=3,b0=.0002, prior
coefficient covariance100*sigma_noise^2*I, in the standardized design. The posterior
predictive Student-t has df=2*a and scale=sqrt((b/a)*(1+x_new*V*x_new)); the1+
observation-noise term is required. The conditional-mean credible distribution is
not the forecast distribution. The positive residual expression for b avoids
cancellation. Sources: market_uncertainty_v1/historical_evaluation/evaluate.py
and forecast_baseline/forecast.py. No lambda, window, floor, fitting rule or
baseline is chosen from scored outcomes; report all three, not the winner alone.

MLE negative log likelihood gradients for residual r=y-mu and scale s are
 d/dmu=-(nu+1)*sum r/(nu*s^2+r^2),
 d/dlog(s)=n-(nu+1)*sum r^2/(nu*s^2+r^2).
Validate implementation against finite differences before observed fitting.
The growing SV posterior and rolling baseline use different history policies but
both are causal; report that distinction as part of what is being compared.

## Precision, calibration and serial uncertainty

Keep per-draw integrated density/PIT values in original chain/draw order. For density,
let a_i=exp(log g_i-max(log g)). A chain-aware estimate of MCSE(log p) is approximately
MCSE(mean a)/mean a; scaling cancels. For PIT, estimate MCSE of the mean per-draw
integrated CDF. Prespecify the estimator and report per-chain log means/PIT as
additional disagreement diagnostics. Reference precision is descriptive; do not
select origins/chain subsets to manufacture a passing forecast subset. Short warm
chains do not justify adaptive precision stopping or a calibrated MCSE guarantee.

Report reference-minus-baseline and each warm-seed-minus-reference paired score
series, per-stream means, totals, worst origins and ten consecutive10-origin block
means. Fix descriptive block-bootstrap sensitivity lengths5/10/20 before outcomes,
with fixed seed/repetition count in the final plan. Resample complete origin vectors
so all baselines, common reference and three warm seeds remain paired. Averaging
seed-specific log scores is not the log score of a mixture across seeds; label
which statistic is used. Never inflate the observed-data sample to300labels.

With only100serially dependent outcomes, bootstrap/HAC intervals need stationarity
and dependence assumptions that may be dubious. Label them descriptive sensitivity,
not confirmatory p-values, a fresh-data guarantee or a market superiority result.
Report PIT histogram/mean and central90% event coverage from .05<=PIT<=.95 without
costly quantile inversions. No iid PIT/KS test. Better coverage alone can be bought
by overly broad forecasts; proper log score supplies the accompanying sharpness
penalty. A larger future fresh synthetic/multi-stream or chronological holdout
study is necessary before a calibration claim.

## Prior-evidence context

The parallel source audit found older SV forecasts improving historical interval
scores versus this exact NIG baseline, but that older SV target uses rho=.9 and
an intercept-plus-lag design, versus currentrho=.95/intercept-only. Those results
do not transfer automatically to the current posterior. All later archived real
labels were previously exposed to forecast studies; do not describe an artifact
screen as fresh discovery of market value. Its narrow question is whether the
current target and its warm approximation retain forecast value against the fixed
causal benchmarks, with proper log-score and PIT accounting.
