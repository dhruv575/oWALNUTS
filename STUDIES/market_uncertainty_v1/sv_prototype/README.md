# Flow in expected return and volatility

This research prototype implements a normalized Student-t observation target,
with static mean coefficients and a noncentered latent log-volatility path.
Separate flow coefficients enter the volatility transition. Zero-column scale
covariates give the no-flow-in-scale comparison. Mean covariates are selected
explicitly by the caller, allowing neither/mean-only/scale-only/both ablations.

`target.py` provides the density, an analytical reverse-mode gradient, and one
future posterior predictive draw including both state and observation noise.
It copies input arrays, preserves transitions through missing observations,
and rejects unknown volatility covariates rather than replacing them with zero.
The initial state is a stationary baseline-state draw plus the first known flow
effect; arbitrary flow histories do not imply unconditional stationarity.

All prior parameters must be supplied explicitly. The numerical values in tests
are development fixtures, not selected market priors. Prior predictive checking,
a sampler adapter, matched inference experiments, and chronological market
evaluation remain necessary. This NumPy implementation is not a performance
claim. The target does not permit changing data during a continuation session.

Run from the repository root:

```powershell
target/python-workflow-env/Scripts/python.exe -m unittest discover -s STUDIES/market_uncertainty_v1/sv_prototype -p test_target.py -v
```

Six tests passed: independent normalized centered-density plus Jacobian
agreement, finite-difference gradients for both scale ablations, missing-state
propagation, data ownership/missing-scale rejection, predictive noise terms,
hand-derived short-path controls, and an all-missing prior-only control.
Extreme parameter overflow handling remains part of sampler integration.
These are correctness checks,
not evidence that order flow predicts returns or produces calibrated intervals.
