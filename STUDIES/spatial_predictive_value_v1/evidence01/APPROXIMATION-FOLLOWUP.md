# Training-only optimizer precision followup, before heldout access

All original MAP starts reached the same density and a positive Hessian, but
the best fit's max gradient .00279 missed the source's .001 stationarity check.
Preserve that failed approximation. No heldout outcome has been accessed.

Refine the best original MAP with at most 20 full Newton steps, each using
the same central-difference Hessian (1e-4). Up to 20 halving backtracks, requiring
finite nonincreasing negative log density (absolute rounding allowance 1e-10).
Keep the .001 gradient and strictly positive Hessian gates unchanged. No
eigenvalue clipping. If this fails, leave the approximate predictor unavailable.
If it passes, use the originally frozen Gaussian draws and defensive importance
settings/seeds, then freeze scoring against this separately labeled followup.
The same 900s/2GiB/64MiB lane limits apply. Charge both attempts to setup cost.
