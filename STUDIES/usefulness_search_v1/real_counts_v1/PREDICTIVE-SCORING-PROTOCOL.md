# Frozen historical predictive evaluation

One chronological historical holdout:1931..1961,30 observed counts,one missing
label excluded. The public series was already exposed; this is not blinded new
data. No fitting updates after1930. Use the original frozen GP, exact constant
Gamma-Poisson and exact enumerated changepoint controls. No model/seed selection
from predictive scores. Scoring is now authorized under this protocol.

Compute marginal predictive probability of each observed count by integrating
Poisson(exp(f_future)) against its conditional univariate Gaussian, then averaging
over posterior draws. Deterministic Gauss-Hermite128 and256 nodes;256 is primary.
Require weighted average absolute128-vs256 difference /primary probability<=1e-4
for every year. Failure preserves results without extending quadrature or budgets.
These are pointwise probabilities, not a joint future-sequence likelihood. No
future expected-count moment is required. Reuse the compiled, checked predictive
generated quantities, with an AWS runtime parity check before batch execution.

Reference:all128000 draws from the four independently qualified groups. For all
30 predictive-probability functionals, each group Rhat<=1.01,bulk/tail ESS>=1000;
combined16chains Rhat<=1.01,bulk>=4000,tail>=2000,per-year log-probability delta-
method MCSE<=.02. Every group pair mean difference/combined MCSE<=4 and absolute
log-probability difference<=.05. Also require quadrature convergence above.
Reference failure prevents GP/model-comparison conclusions; retain exact scores.

Evaluate both16384-proposal importance screens and all six fresh workflows,
preserving prior training failures. Per method: same weighted or MCMC mean/MCSE
estimator used in training; per-year log error<=.05,combined-MCSE z<=4,log MCSE
<=.025,and quadrature gate. MCMC Rhat<=1.01,bulk/tail ESS>=400. Require original
training qualification too; passing predictive checks cannot erase a training
failure. Importance retains original raw weights and tail/ESS requirements.

Application endpoint: mean pointwise log predictive score. Report paired yearly
differences GP minus each exact control and a descriptive95% circular calendar-
block bootstrap interval (block length5,20000 replicates,seed951800001,31 calendar
positions,missing labels excluded within each resample). Report Monte Carlo
uncertainty separately: delta-method MCSE of mean log score using each draw's
mean(p_year/posterior_mean_probability), retaining covariance across years.
Short single-series bootstrap is descriptive,not population or safety evidence.
No predictive advantage unless reference and integration gates pass and both
control comparison lower endpoints exceed zero; even that would establish only
this model's historical predictive evidence,not a unique WALNUTS advantage.

AWS:36 bounded jobs (16 reference chains,16 fresh MCMC chains,4 importance fits),
up to16 concurrent BLAS1 workers. Each300s/768MiB/32MiB;initial free disk>=1GiB.
Save raw conditional means/variances,128/256 probabilities,input hashes and
supervision. Postprocessing separately bounded300s/4GiB/32MiB. No further tuning.
Predictive postprocessing runs concurrently: its times are not serial inference
workflow costs. Preserve all failures; independent numerical/raw audit required.
