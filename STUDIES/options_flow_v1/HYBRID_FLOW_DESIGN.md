# Hybrid group-slope coordinates (untested proposal)

Use sampling coordinates `u = [bbar, logtau, mu, logsigma, zalpha[G], beta[G], innovations[T]]`. Keep the four global priors exactly as currently specified. Reconstruct canonical `zbeta_g = (beta_g-bbar)/exp(logtau)` and reconstruct `h` from the existing stationary AR innovations. Keep `alpha=.3*zalpha`; its scale is fixed, so this block needs no change or additional Jacobian.

The complete sampling-to-canonical log absolute determinant is

`T*logsigma - .5*log(1-rho*rho) - G*logtau`.

The off-diagonal dependence on global variables does not alter this determinant: the transform is block triangular. Relative to the existing fully path-noncentered density, only the group transformation contributes `-G*logtau`. Equivalently implement the fully normalized density directly with `beta_g ~ Normal(bbar, exp(logtau))`, independent standard-normal `zalpha` and innovations, the unchanged global log-coordinate priors, and the existing Student-t likelihood with location `.3*zalpha_g + beta_g*x_tg`. Do not also add the group Jacobian to this Normal density; that would count it twice. No exp(logtau) Jacobian is added for the global prior because that prior is specified directly on logtau.

For a fixed canonical initial matrix, transform each group slope to `beta=bbar+exp(logtau)*zbeta`; reuse the exact path innovation inverse. Output canonical draws with the inverse group transformation so diagnostics, prediction, and interval gates stay identical. Bind coordinate recipe in source/report/parity identity; keep block-size32 compilation and its costs visible.

Evidence motivating the experiment is limited to stored long-target gate reports: beta_bar and tau endpoints fail at1000/2000, tau alone fails at4000 (max MCSE/width .0247402836), and all pass at8000 (tau .0164027586). Posterior correlations have not been measured. The hypothesis is that a long likelihood identifies physical group slopes, inducing costly bbar/tau/zbeta dependence under group noncentering. Group centering may reduce that dependence. The latent process remains noncentered in this proposed experiment; its superiority is not established universally.

Required checks before timing: compare normalized hybrid density against canonical density plus the complete Jacobian at arbitrary finite points, including nonzero globals and varied scales; check gradients independently, stationary T=1 and general T, and both transport round trips. Verify independent JAX/NumPyro and PyMC targets. No truth, fitted correlations, or pilot-selected parameter values enter the transform.

Prespecify the same physical starts, all14 functional plus4 observed-forecast endpoint gates, all-coordinate health, and full restart/continuation cost accounting. Compare both backends under the same hybrid recipe and preserve failed outcomes. Repeat across prior fixtures, including low-information and small-tau regimes where centered hierarchy funnels may be worse. Treat the long fixture as development data; neither a win on it nor this derivation establishes calibration or general speed improvement.
