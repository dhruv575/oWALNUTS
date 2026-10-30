# Real count-series data freeze and exact controls

Source: pinned PyMC examples notebook and MIT license in source/PROVENANCE.json.
Parse its literal counts and executable year range without executing notebook
code. Retain the two missing values. The code's years1851..1961 are authoritative
for this version; do not append1962 based on prose. Preserve that discrepancy.

Historical split fixed before any predictive scores: train years<=1930;
evaluate1931..1961, excluding missing labels from likelihood/scoring, never
replacing them with zero. No rolling updates. The full public sequence has
already been visible; this is a historical holdout, not blinded new data.
GP input x=20*(year-1851)/(1930-1851), using fixed training endpoints only.
GP priors remain rho~Gamma(25,4), alpha~halfNormal(0,2), zero-mean log intensity,
noncentered standard-normal latent, covariance jitter1e-10. No maps initially.

Exact model controls: constant Poisson rate with Gamma(shape1,rate1) prior;
one changepoint uniform over integer training years1851..1930 inclusive, with
independent Gamma(1,1) early/late rates, early iff year<=changepoint. Integrate
both rates analytically and enumerate all changepoints, retaining the boundary
with no late observations. Future rates use the late regime. Controls require
no MCMC. Missing observations contribute no exposure or count to likelihood.

This stage only prepares data and exact training posteriors. Do not score
heldout outcomes yet. Freeze GP reference/inference/strong-approximation budgets
and predictive integration/MCSE rules before opening the scoring stage. Require
qualified accuracy and whole-workflow costs; no benefit from beating a weak
model or failing control. Candidate inference methods: raw WALNUTS, qualified
native NUTS, strong importance correction; preserve all calibration failures.

Planned application quantities: latent-rate uncertainty and historical future
count prediction, separate from algorithm accuracy. Model comparison must include
exact controls and report paired per-year predictive log scores with integration
uncertainty. This single historical series does not support population-wide or
operational safety claims, profitability, uniqueness, or a claim of novelty.
