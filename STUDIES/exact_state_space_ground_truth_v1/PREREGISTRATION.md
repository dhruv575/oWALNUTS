# Preregistered exact state-space ground-truth study (WP4)

Frozen before execution on 2026-08-31. Evidence class: diagnostic with an
exactly known posterior; not a benchmark claim.

## Target

Gaussian local-level model in **centered** path coordinates `x_1..x_T`, all
globals fixed:

* `x_1 ~ N(m0, tau0^2)` with `m0 = 0`, `tau0 = 1`;
* `x_t = x_{t-1} + mu + N(0, sigma_x^2)`, `mu = 0.01`, `sigma_x = 0.08`;
* `y_t = x_t + N(0, R_t)`, `R_t = 0.0125 (1 + s_t^2 + 1/(v_t + 1))`;
* synthetic spread `s_t` and median-normalised volume `v_t` patterned on the
  Polyscope model, generated from data seed `2026083101` (deterministic);
* `y` simulated from the model with the same data seed; `T in {100, 1000}`.

The posterior is exactly Gaussian with tridiagonal precision
`H = Q_rw + diag(1/R_t)`. Exact mean and marginal variances come from a
tridiagonal (Thomas) solve and are cross-checked against a dense inverse at
`T = 100` in unit tests.

## Arms (fixed metric; momentum covariance `M`; kernel identical otherwise)

| Arm | Momentum covariance `M` | Facade | Equivalent to |
|---|---|---|---|
| I | identity | `sample_chains` | centered, unit mass |
| D | `diag(1 / Var_post[x_t])` | `sample_chains` | centered, adapted diagonal |
| P | `H` (posterior precision), bidiagonal Cholesky | `sample_chains_structured` | exact whitening |
| Q | `Q_rw` (prior precision only), bidiagonal Cholesky | `sample_chains_structured` | non-centered innovations with unit mass |

Convention: `p ~ N(0, M)`, `K = p' M^-1 p / 2`; structured blocks supply the
Cholesky factor `L` with `M = L L'`. Arm D uses inverse posterior variances
because `M` plays the role of a target precision.

Kernel: initial step `0.1`, depth `8`, minimum micro-steps `1`, refinement
levels `3`, max error `1.0`, divergence threshold `1000`. Warmup: 500
discarded transitions with dual-averaged step size (target acceptance `0.8`),
default initial-step search, **mass adaptation off**; 2,000 retained draws;
4 chains; 4 threads; starts drawn from the prior random walk (dispersed).

Seeds (fresh, absent from every ledger): `83001` (T=100), `83002` (T=1000),
`83003` (T=100 replicate), `83004` (T=1000 replicate). Data seed
`2026083101`.

## Preregistered predictions

Before sampling, each arm's whitened precision `W = L^-1 H L^-T` gets its
extreme eigenvalues by power/inverse iteration, and the predicted leapfrogs
per U-turn is `~1.75 sqrt(kappa)` with `kappa = lambda_max / lambda_min`
(stable step `~1.8/sqrt(lambda_max)`, half period `pi/sqrt(lambda_min)`).
Predicted depth is `ceil(log2(leapfrogs + 1))`; `>= 8` predicts a cap.

1. **Arm P** mixes at depth 2–4 at both `T`, with all coordinate z-scores at
   Monte-Carlo level (`|z| > 3` fraction below 1%) and variance ratios within
   `[0.8, 1.25]`.
2. **Arms I and D** do **not** hit the depth-8 cap at either `T`: in centered
   coordinates with informative observations the spectrum of `H` is bounded
   in `[~1/R, 4/sigma_x^2 + 1/R]` independent of `T`
   (`kappa ~ 10–20`), so trajectory length does not grow with `T`. This
   refines the program's item 3: the `~T^2` conditioning applies to innovation
   (non-centered) coordinates, which arm Q represents exactly.
3. **Arm Q** (prior-only metric = non-centered unit mass) has `kappa` growing
   like `T^2`; predicted depth `~5` at `T=100` and a **cap at depth 8** at
   `T=1000` with degraded ESS on the path level (mean of `x`).
4. Ordering of ESS per target call at `T=1000`: `P > D >= I >> Q`.

## Gates for calling a prediction "held"

* depth prediction: observed retained median depth within ±1 of predicted, or
  observed maximum-depth rate `> 50%` when a cap was predicted;
* accuracy: fraction of `|z| > 3` over coordinates `< 1%` and no `|z| > 5`;
* variance ratio: 5th–95th percentile of `Var_mc/Var_exact` inside `[0.8,1.25]`;
* health: zero retained divergences, invalid evaluations, refinement
  exhaustions on P (I, D, Q report but are not gated).

## Not authorised

No `sspd-10`/Polyscope target sampling; no source edits; no free-global
variant unless the primary completes with time to spare (it would use fresh
seeds `83011–83012` and a Kalman-likelihood grid as truth).
