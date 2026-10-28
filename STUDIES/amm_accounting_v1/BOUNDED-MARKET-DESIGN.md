# Real-market bounded-prior development evaluation

This is a development study, not an untouched holdout. Use the already sealed
December 2025, January 2026 and February 2026 thirty-minute return panels. Those
months have been examined in earlier research, including the original improper
target's diagnostics. Do not inherit its posterior qualification or claim
unseen-data generalization. Keep repeated returns exactly as recorded: no jitter,
rounding changes or selective removal.

## Fixed observations and targets

Use all eight previously declared reference ticks per month, without selecting
origins by scores or diagnostic outcomes: December/January
1,213,426,638,851,1063,1276,1488; February
1,193,385,577,768,960,1152,1344. This gives 24 origins. For each use caps .5,1,2,
giving 72 model/origin cells. Both NUTS and WALNUTS use the same normalized bounded
prior, rho=.95, nu=5, and exact beta rescaling. No cap is chosen on these outcomes.

Use the sealed data_contract.inputs rule: window=y[tick:250+tick], current
observation y[249+tick], NEXT label y[250+tick]. Full observed history is
y[:250+tick]. Baseline fitting and posterior sampling consume history/window
only; scoring consumes the separately recorded next label. Preserve acquisition
and extracted-fixture hashes and the observation/label timestamps. The initial
EWMA fit uses y[:250] before every scored origin.

## Predictive and inference claims

Evaluate the one-step posterior mixture log density and PIT using the existing
validated GH64/128 implementation and joint(mu,log_sigma,beta,h_last) draws.
Retain numerical disagreements and failed fits in the planned denominator.
Log score is log of mean density, not mean log density. Record chain-aware
MCSE using stabilized density values, plus PIT diagnostics. No score clipping.

Keep three differences separate at every origin and cap: NUTS minus baseline
(model value conditional on reference quality), WALNUTS minus NUTS (inference
approximation), and WALNUTS minus baseline (their exact sum). Require physical
coordinate diagnostics and predictive-functional diagnostics before qualifying
a comparison. Do not treat several caps or sampler seeds as independent markets.

Use the existing frozen causal baselines: rolling 250 t5 location/scale MLE,
t5 EWMA with lambda=.94 initialized on the first 250 observations, and NIG AR1
on up to 256 observed lag/response pairs. Retain optimizer failures and scale-floor
hits, without outcome-dependent fallbacks. Fit all baselines before viewing the
new candidate scores. Descriptive per-origin/month summaries are primary; 24
sparse origins cannot establish robust calibration or broad statistical power.

The continuous point-return likelihood remains a working approximation to
recorded market closes. Proper normalization does not prove the observation
mechanism correct; ties and discreteness limit literal PIT-uniformity claims.
Do not conflate density improvements with executable economic value. No trading,
deployment or profitability claim is authorized by passing this screen.

## Execution gate

First validate and freeze all 24 causal fixtures and baseline outputs. Then freeze
sampler seeds, fixed iteration budgets, comparison rules and a bounded batch/storage
schedule before sampling. Use both engines' established 4-chain, 2,000-warmup/
4,000-retained configurations unless a documented pre-launch implementation
constraint requires a separate declared design. Preserve all failed slots.
Archive/verify completed batches before reclaiming large trace copies; do not
exhaust disk or relax reference requirements to make the study fit.

After this development screen, declare an untouched confirmation period and
precision-matched algorithm comparison. Economic evaluation additionally needs
feasible inventory/cost/fee assumptions and defensible counterfactual baselines.
Those requirements, and a submission-ready paper, remain part of the full goal.
