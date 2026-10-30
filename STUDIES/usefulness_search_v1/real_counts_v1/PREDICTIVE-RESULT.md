# Verified negative application result

The frozen historical forecast test does not establish predictive advantage for
the GP. Mean pointwise log scores (higher is better):GP -1.44693082,exact constant
rate -1.69698550,exact changepoint -1.40315692. GP minus changepoint is-.04377391
nats/year,with descriptive calendar-block95% interval[-.13625025,.05059295].
GP minus constant is+.25005467,interval[-.19991960,.66445439]. Both intervals
include zero. Reference Monte Carlo SE of mean log score is.00033004,separate
from temporal sampling uncertainty. This is one exposed public historical series.

Reference predictive qualification passed for all30 observed future counts,
including quadrature and cross-group checks. All36 raw predictive outputs were
independently replayed; original-model basis reconstruction checked conditional
moments at up to8 points/job. Combined diagnostics, exact SciPy negative-binomial
controls,and the block bootstrap were independently recomputed. Score audit passed.

Inference results remain separate: the fresh serial training study qualified5/6
fits. WAL rep1 missed maximum MCSE/refSD(.02827 versus.025); aggregate time ratios
were suppressed. Individual complete workflow times:WAL52.60--53.89s,native74.33--
75.84s,importance6.23--6.25s. These are fixed-budget observations,not a validated
competitive ranking. Both4096-proposal importance fits subsequently missed the
predictive log-MCSE threshold; both earlier16384-proposal importance fits passed
predictive accuracy. Both native fits passed. WAL rep0 passed;rep1 retained its
training failure despite passing predictive-specific checks. No failed criterion
was erased by a different endpoint.

Preserved implementation failures: initial generated-quantities checker omitted
the mandatory RNG handle; AWS startup passed lists instead of ndarrays; three
importance prediction jobs hit strict positivity assertions on underflowed tiny
probabilities. Reviewed repairs kept scientific settings and samples unchanged,
saved separate outputs,and retained original failures. Log probabilities now
document underflow; weighted quadrature convergence gates were unchanged.

Conclusion: do not advance this historical-count forecast as a WALNUTS use case
or claim an algorithm-specific advantage. It is valuable negative evidence for
the manuscript. Do not tune another budget/model against these exposed scores
to manufacture success. Next candidate must justify a need for posterior
exploration against strong cheap controls before another large campaign.

Final score audit used180s timeout/BLAS1,not separate RSS/output supervision.
The prediction jobs,repair jobs,and aggregation used their documented monitors.
