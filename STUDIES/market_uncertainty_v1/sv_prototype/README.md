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
are development fixtures, not selected market priors. Market prior review,
matched inference experiments, and chronological market
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

`adapter.py` now snapshots the validated target into an owned Numba CFunc for
oWALNUTS. Twelve tests passed, including independent JAX and finite-difference
parity, ownership after caller mutation/deletion, simultaneous native calls,
and numerical boundary handling. Nonfinite or overflowing evaluations return
NaN value/gradient as a fatal callback error; they do not silently substitute
zero posterior density. Use the separately built parallel continuation runtime
for experiments; the old attested runtime is unchanged.

The first actual inference pilot exposed an adapter bug: an extreme but finite
proposal made the innovation scale underflow to zero, while the original target
still had a finite density and gradient. The adapter now accepts this finite
limit. A bounded diagnostic then reached a different, genuine exponential
overflow in raw coordinates. Both failures, the exact proposals and regression
evidence are preserved in `artifacts/sv-underflow-diagnosis-v1` in the parent
study directory. The initial four-fit experiment is also retained: both public
fits failed, while both references passed; no speed comparison is eligible.

`whitened.py` implements the exact affine change from standardized prior
coordinates to physical parameters, including its constant Jacobian and gradient
transport. It changes geometry, not the posterior or physical starting points.
Two tests cover density/gradient transport, starts and callback lifetime. A
separate matched inference experiment evaluates this candidate; pointwise tests
alone do not establish that it solves the adaptation failure.

`reference.py` implements the same normalized posterior independently in JAX
with an associative latent-path calculation and a NumPyro NUTS kernel. Three
tests with multiple model-shape subcases passed, including missing rows and
zero-residual gradients. Correctness tests do not establish sampler agreement.

`synthetic.py` supplies four mean/scale ablations and a separately implemented
simulator; four tests passed. Covariates are a fixed causal forcing schedule,
not an endogenous market flow process. The illustrative priors are explicitly
in native 30-minute log-return units. A diagnostic with 128 prior draws of 256
returns per ablation produced no nonfinite values, but the 99th percentile of
absolute log returns was about 0.031 and maxima about 0.13. Those are exposed
scale assumptions, not accepted market priors or calibration evidence. Exact
inputs and sources are preserved at `target/sv-prior-diagnostic-v1`.

`market_inputs.py` builds the four ablations from receipt features, with a caller
declared lookback and minimum history. It uses only matured labels and past
training rows for scaling, retains missing-outcome state transitions, and rejects
unknown volatility forcing rather than replacing it with zero. Three tests
passed. It trusts the causal feature producer; a live caller must bind that
producer and its receipt evidence. Standardizing each training prefix changes
the physical coefficient prior, so the prior is explicitly defined on the
standardized design. This builder alone does not fit or issue a market interval.
