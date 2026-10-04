# Optional centered-slope, noncentered-path investigation

Status: prospective static prototype. No numerical tests, fits or performance
measurements have run for `flow_mixed_coordinates.py`. Existing defaults and the
frozen six-cell comparison remain unchanged, including all failed outcomes.

The long-flow restart arm reached 8000 draws with a healthy, zero-divergence
screen but missed the tau endpoint requirement: MCSE/width 0.02190794 against
0.02. Earlier 4000-draw uncertainty involved both tau and beta_bar. These facts
motivate an investigation; they do not establish a coupling mechanism or imply
that more draws or a coordinate change would pass reliably.

## Exact transport

The existing canonical coordinates are
`q=[b, log(tau), mu, log(sigma), z_alpha[G], z_beta[G], h[T]]`, with
`alpha_g=0.3*z_alpha_g` and `beta_g=b+tau*z_beta_g`.

Use optional coordinates
`u=[b, log(tau), mu, log(sigma), z_alpha[G], beta[G], z_path[T]]`.
The inverse to canonical coordinates is

```
z_beta_g = (beta_g-b)/tau
h_0 = mu + sigma*z_path_0/sqrt(1-rho^2)
h_t = mu + rho*(h_(t-1)-mu) + sigma*z_path_t
```

The forward transform uses `beta_g=b+tau*z_beta_g` and standardized stationary
AR residuals. Both transforms preserve all physical parameters, canonical starts
and fourteen physical functionals when G=4.

Order globals first, then groups/path: the Jacobian is block triangular despite
global derivatives. Its slope diagonal contributes `tau^-G`, while the path
diagonal contributes `sigma^T/sqrt(1-rho^2)`. Thus

```
log |d q / d u| = -G*log(tau) + T*log(sigma) - 0.5*log(1-rho^2).
```

In particular the beta sign is negative. Combining this with the original
normalized density yields the direct normalized target used in the module:
unchanged global priors, iid standard normal z_alpha and z_path,
`beta_g ~ Normal(b,tau)`, and unchanged Student-t likelihood
`y_tg ~ StudentT(nu, 0.3*z_alpha_g + beta_g*x_tg, exp(h_t/2))`.
The module uses this direct form; adding the Jacobian again would double count it.

## Hypothesis and limits

With informative within-group predictor variation, the likelihood may tightly
identify beta_g, so the original `b+tau*z_beta_g` representation forces the global
hierarchy and local standardized slopes to move together. Centering beta_g can
remove that likelihood-induced dependency. But T=1000 alone is insufficient:
predictor magnitude/variation, noise scale, collinearity with group intercepts,
and time-varying volatility determine actual slope information.

Centering instead creates strong prior coupling when tau is small or predictors
are weak. Only G=4 group slopes inform the hierarchy, so tau may remain broad or
near zero even with accurately estimated slopes. This can worsen geometry.
It may be unsuitable for the sparse masked-market panel; the prototype explicitly
supports dense data only. Mixing observations versus conditional prior information
is the relevant diagnosis, not selecting a transform from synthetic truth.

Once quiet, inspect saved chainwise b/tau/z_beta/beta correlations and conditional
spread, effective information from observed x and scales, and tau tail excursions.
Unhealthy draws are diagnostic observations, not posterior truth. Keep the
unmodified full-NC arm and the stronger optimized reference as comparators.

## Marginalization alternatives

Integrating beta_g directly is not conjugate under the Student-t likelihood. A
normal/Gamma scale-mixture expansion permits conditional Gaussian integration of
each beta_g but introduces T*G residual precision variables (4000 at T1000,G4).
That larger state and altered geometry need their own justification; numerical
quadrature would require explicit error/gradient controls and cannot silently
replace the exact target.

In centered-beta coordinates b alone *is* analytically integrable because its
prior is Normal(0,0.5) and beta|b,tau is Gaussian. The marginal group covariance is
`tau^2*I + 0.25*11'`. Conditional reconstruction of b has precision
`4+G/tau^2` and mean `(sum(beta)/tau^2)/(4+G/tau^2)`.
This is an exact later option, but it changes dimension and needs a declared RNG
stream for b reconstruction and proper endpoint-MCSE accounting. It does not
remove the tau boundary problem. Do not combine it into the first coordinate test.

## Prospective verification and screen

The authored tests check batched roundtrips, every physical functional, Jacobian
sign against an independent full autodiff determinant, equality of normalized
densities and gradients via a separately expressed transform, and public PyMC
versus independent JAX gradients at multiple log-tau scales. T1 and T7 boundary
cases and nonrepresentable positive scales are included. Run these only after
the current timing job ends; add a T1000 parity point before any long trial.

Then freeze a small development comparison with identical physical starts and
unchanged default tuning, full costs, all fourteen functionals, all forecast cells,
zero retained divergences and the same endpoint threshold/cap. Compare both full-NC
and mixed coordinates under both public CFunc continuation and optimized NumPyro,
using a fresh balanced seed/order. Do not extend the current failed run's tiers or
choose a winner based only on tau's observed improvement. A new result is an
exploratory geometry screen, not calibration or broad usability evidence.
