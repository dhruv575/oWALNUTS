# Predictive value of the current SV target and its warm approximation

Design v1, 2026-10-27. **No predictive outcomes have been computed for this screen.**
The origin set, baseline family and analysis rules below are fixed before scoring.
Execution remains pending implementation fixtures, independent review, source/data
hash binding and the parent's explicit preflight/full-run authorization.
`protocol.json` is the machine-readable design authority.

This is a retrospective diagnostic on already-inspected streams, not fresh market
discovery or qualification. Earlier SV studies already reported gains against an
exact NIG price baseline, but used different targets (including rho=.9, a lagged
mean term and rolling256 histories). The present target is WP97's rho=.95,
intercept-only growing-history model. Its full-return predictive performance and
the loss caused by its K200 approximation are the questions here. The later real
tail has also been scored previously; it cannot be relabeled an unseen holdout.

## Inputs and causal origins

Use only the completed WP97 artifacts, source run `a355bae5`, from the verified
archive SHA256 `19a89ac0ac401e0700d3140e33e71637658d0cc791a52806dc3eaa38013de595`.
[ORIGIN-INVENTORY.json](ORIGIN-INVENTORY.json) binds every raw file and exact
original record, dataset, kept-chain selection and causal index. Its builder reads
metadata/hashes only; it does not fit baselines or score observations.

- Two fixed datasets: sim (1,100 returns) and real (682 BTC-PERPETUAL 30-minute
  bar-close returns), with original hashes and no new acquisition.
- Exactly ticks t=1..100 in each stream. Tick0 is excluded consistently because
  it is the special initial fit. At tick t, n=250+t observations have arrived:
  posterior inputs are `y[:n]`; the newly assimilated return is `y[n-1]`; the
  **next** label is `y[n]`. All 200 next labels exist (indices251..350 inclusive).
- Use the original selected long-reference attempt and kept chains at every
  origin: 4x20,000 retained joint draws here. Use unpooled K200 current draws for
  all three original sampler seeds per dataset: 4x200 draws each. No thinning,
  new chain selection, pooling across ticks/seeds, seed selection or new sampling.
- Compact field order is `(mu, log_sigma, beta, h_last)`, little-endian f32,
  converted to float64 for arithmetic while retaining chain/draw ordering.
- There are 200 reference and 600 warm predictive distributions but only 200
  realized outcomes across two dependent streams. Three sampler seeds are not
  three independent forecast replications. Report sim and real separately.

This maps to 1,400 forecast rows: reference, three warm seeds and three baselines
at each of the 200 origins. Each forecast stores its conditioning endpoint and
label index. Input labels may be read only for evaluation, never baseline fitting.

## Predictive density and PIT

For joint draw i, set `m_i = mu_i + .95*(h_last_i-mu_i)` and
`sigma_i = exp(log_sigma_i)`. Integrate the future Gaussian volatility innovation
and Student-t5 observation distribution, not only the scale distribution:

`g_i(y) = E_Z[t5(y; beta_i, exp((m_i+sigma_i*Z)/2))]`.

The log score is `log(mean_i g_i(y[n]))`, not `mean_i log(g_i(y[n]))`.
PIT is `mean_i E_Z[T5((y[n]-beta_i)*exp(-(m_i+sigma_i*Z)/2))]`.
Larger log score is better; units are nats per native log-return observation.
No clipping of densities, scores or PIT is allowed to conceal extreme outcomes.

Use GH128 as the primary deterministic calculation and GH64 as a complete
same-draw numerical cross-check at the observed return. Chunk512 posterior draws
at a time. At each origin/arm require absolute log-density difference <=1e-6 nats
and absolute PIT difference <=1e-6. A discrepancy is an explicit unavailable
numerical row, with both outputs retained; no adaptive fallback order or selective
rerun. Keep all draws and weights. The stable per-component log density is

`log(c5) - h/2 - 3*logaddexp(0, 2*log(abs(y-beta)) - h - log(5))`,

where `c5=8/(3*pi*sqrt(5))`; combine quadrature and posterior components with
logsumexp. The y=beta case has log(abs residual)=-infinity. This screen solves
no mixture quantiles: a density/CDF evaluation at the observed return suffices.

Numerical fixtures before scoring cover exact density/PIT at a common beta,
independent adaptive integration with a Gaussian-tail bound, CDF derivative versus
density, translation/scale equivariance, permutation, normalization and extreme
finite-value handling. The numerical module and tests are independently owned
and reviewed; their final hashes must be bound before scoring.

## Three fixed causal baselines

All baseline choices below were settled before this screen's outcomes. Report
all three; do not choose a best-performing baseline for a headline. The static
initial Student-t control is omitted. No flow features are introduced.

1. **Existing exact NIG intercept+lag baseline.** Reuse the established recipe in
   `market_uncertainty_v1/historical_evaluation/evaluate.py` and
   `forecast_baseline/forecast.py`, whose source identities are inventoried.
   For n observations, training response indices are
   `k = max(1,n-256), ..., n-1`, rows `[1,y[k-1]] -> y[k]`.
   Predict using `[1,y[n-1]]`. Thus n=251 has 250 matured pairs and n=257 has256;
   never fetch unavailable prehistory or a future response. The minimum20 rule is
   always satisfied. Standardize only training lag predictors using their mean
   and population standard deviation (ddof0); if sd<=1e-12, use1. Apply that same
   transformation to the forecast lag; responses stay in native units.
   The prior is `a0=3`, `b0=.0002`, coefficient covariance `100*sigma²*I`.
   With posterior mean b, covariance factor V, shape a and scale B, forecast
   Student-t df is2a, location x'b and observation scale
   `sqrt((B/a)*(1+x'Vx))`. The `1+` observation-noise term is mandatory.
2. **Rolling250 Student-t5 MLE.** Fit location and scale on `y[t:n]` only.
   Four deterministic starts: mean/median locations crossed with
   `std(ddof1)*sqrt(3/5)` and `MAD/t5.ppf(.75)` scales. Floor candidate/forecast
   scale at1e-8 log-return units and record floor hits. Optimize a location
   coordinate standardized by `max(training std(ddof1),1e-8)` around the training
   median, together with log-scale in those standardized units. Use L-BFGS-B,
   maxiter500, maxfun5000, ftol1e-12, gtol1e-8, with only the scale lower bound.
   Analytic gradients minimize mean negative log likelihood. A candidate is
   eligible only if the solver reports success, all outputs are finite and the
   standardized projected-gradient infinity norm <=1e-5. At the lower scale
   bound, a positive log-scale gradient is projected to zero. Choose the eligible
   candidate with smallest training objective, ties by start order. All four
   attempts remain recorded. No eligible candidate means missing, not a fallback
   chosen after seeing predictive scores.
3. **EWMA Student-t5.** Fit initial mu0,s0 by that same MLE on only `y[:250]`.
   Initialize `v0=(5/3)*s0²`. After assimilating each new observation update
   `v_t=.94*v_(t-1)+.06*(y[250+t-1]-mu0)²`.
   Forecast location remains mu0; Student-t scale is
   `max(1e-8,sqrt(3*v_t/5))`. Record any floor hit. Lambda .94 is fixed, not tuned.
   An invalid initial MLE leaves this baseline unavailable; it does not trigger
   another initialization rule. Preserve the selected initial fit from preflight
   and reuse it in the full run.

The SV growing history, MLE rolling250 observations, and NIG rolling256 matured
pairs are different causal history policies. This is part of the comparison, not
hidden information equivalence. MLE validation includes finite-difference gradient
checks, location/scale equivariance and fixed-start failure behavior. Causal tests
perturb every observation at/after the future-label index and require unchanged
baseline predictive parameters.

## Precision and score decomposition

For each posterior forecast preserve per-draw integrated log density `log g_i`
and integrated CDF `u_i` in chain/draw order during calculation. With
`a_i=exp(log g_i-max(log g))`, report
`MCSE(log p) ~= ArviZ.mcse(a,method='mean')/mean(a)` and
`MCSE(PIT)=ArviZ.mcse(u,method='mean')`, plus chain-specific log mean densities
and mean PIT values. Constant traces have zero MCSE. Reference precision is
descriptive: no new gate drops origins or chains. K200 warm MCSE is not a validated
adaptive stopping rule. Monte Carlo uncertainty is separate from the variability
of observed forecast losses across time.

At every common origin retain the exact decomposition:

- model comparison: `logp_reference - logp_baseline`;
- approximation impact for each seed: `logp_warm_seed - logp_reference`;
- their sum: `logp_warm_seed - logp_baseline`.

Also report absolute warm/reference log-density and PIT differences. A positive
warm/reference observed score gap is not proof of a more accurate posterior.
Do not average seed densities into a K600 mixture. Any displayed seed average
must be labeled an average of three seed-specific log scores.

Report per-stream score means/totals and all paired differences, cumulative
differences, ten consecutive10-origin block means, PIT histogram (ten equal bins),
mean PIT, lag1/lag5 PIT autocorrelation, tail counts and central90% event coverage
from `.05 <= PIT <= .95`. This coverage needs no quantile inversion. No iid PIT/KS
test, profitability claim or extrapolation from these100 adjacent returns.

For descriptive dependence sensitivity only, use circular moving-block bootstrap
lengths5/10/20 and2,000 replicates. Seed27109701 for sim and27109702 for real;
consume each dataset's RNG in increasing block-length order. Resample complete
origin vectors, keeping reference, all three warm seeds and all baselines paired.
Use ceil(100/L) uniform block starts, wrap modulo100 and truncate to100 indices.
Report percentile2.5/97.5 bounds for paired mean score differences for every length,
without choosing the tightest interval or using significance as a decision gate.
These sensitivity intervals assume useful local stationarity and are not an
unseen-data guarantee. Seed bases had zero exact-word hits in tracked source and
artifacts before this design was written.

Missing or invalid rows stay in the planned100-per-stream availability count.
A full-panel mean/comparison is null unless all required100 rows are valid;
available-pair descriptive summaries may be shown separately with denominators.
Do not impute a score for abstention without a declared decision loss. No outcome
is replaced. There is no sampler/default/market qualification verdict in this
diagnostic; results inform whether model work or inference fidelity deserves the
next fresh-data experiment.

## Two-origin preflight, full-run budget and artifacts

After fixtures, source binding and explicit authorization, run exactly sim tick1
then real tick1 once as the timing preflight. Each origin computes the reference,
all three warm seeds and all three fixed baselines. Hard limit120 s and2 GiB RSS.
Do not choose a different origin or rerun to obtain a faster estimate. Save these
two complete origin vectors and initial EWMA fits for reuse in the full run.

Let T be elapsed wall seconds for the two-origin preflight, including input
admission, baseline initialization and per-origin arithmetic but excluding module
imports (import/setup wall is recorded separately). Remaining work is99 origin
pairs. The fixed full-run budget is `ceil(1.5*99*T + 120)` seconds, floored at300 s.
If it exceeds1,800 s, do not start the full screen; report budget-not-demonstrated.
Otherwise that computed value is the hard full-run deadline. The preflight must
complete its expected schemas and numerical checks to proceed; predictive score
signs or magnitudes never control continuation. The full run processes ticks2..100,
sim then real per tick, using every planned origin. No new sampling, AWS action,
market acquisition or trading occurs. Initial execution is local, not a cloud
latency qualification. New outputs capped at50 MiB; raw source draws are referenced,
not duplicated. No multi-process sampler/worker pool is needed.

Use a bounded parent supervisor with PID/start/end/exit and resource records.
Checkpoint each full origin vector atomically into a new directory, never overwrite
completed output, and record interrupted/pending origins explicitly. The evaluator
also checks the absolute monotonic deadline between chunks/fits. Timeout/failure
retains partial outputs and prevents a full-panel claim. Numerical source/tests,
baseline source/tests, evaluator, protocol, origin inventory, environment versions
and dependency identities are hashed and committed before the first scored origin.

Planned output per origin: dataset/tick, causal indices/input hashes, reference
attempt/kept-chain identity, three warm seeds, per-arm status/logpdf/PIT/order checks/
MCSE/chain summaries, baseline distribution parameters/fit diagnostics/training
bounds/floor flags, observed next return, score decomposition and elapsed/RSS.
The final report retains all1,400 planned forecast-row statuses, all200 origins,
prior exposure, missing denominators and the unchanged baseline family.

Local environment currently verified: Python3.14, NumPy2.5.2, SciPy1.18.1,
ArviZ1.3.0. Exact versions and numerical fixture results are re-bound at final
execution freeze; any change before scoring is recorded, not assumed equivalent
to WP97's original Linux timing environment.
