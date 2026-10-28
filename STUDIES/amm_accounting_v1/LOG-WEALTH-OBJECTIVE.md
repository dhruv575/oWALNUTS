# Conditional log wealth, posterior tail obstruction and a dominance control

Conditional finiteness does not make this an admissible posterior-predictive
objective for the current unbounded scale prior. It is not a profitability
result and does not replace the execution/accounting requirements in
`DATA-ADMISSION.md`.

## Why expected log wealth is finite in the idealized return model

Let R be the next quote-denominated log price return. In the fixed Student-t(5)
observation model, conditional on a finite latent state, E|R| is finite, whereas
E exp(a R) is infinite for every nonzero a. The latter rules out evaluating an
unbounded expected-dollar-wealth objective by an apparently converged finite
Monte Carlo mean. Posterior averaging additionally requires integrability of
the conditional first absolute moment; finite posterior draws alone do not
prove that condition.

For initial wealth W>0, nonnegative risky weight w in [0,1], and gross risky
return exp(a R), define

    log(W_next/W) = log((1-w) + w exp(a R)).

This expression lies between min(0,a R) and max(0,a R), so its absolute value
is bounded by |a R|. Thus conditional expected log growth exists under the stated
Student-t model. Stable log-sum evaluation avoids overflow in extreme tails.
This argument excludes leverage, bankruptcy, unbounded costs and zero wealth.
Gas and liquidation costs need explicit treatment before the objective is used.
Expected log growth is not expected dollar profit, nor evidence of realized
profitability; both must be reported separately.

## A pathwise control for a fee-free constant-product LP

Assume an infinitesimal passive LP share, unchanged LP supply and reserve product,
continuous alignment of the reserve price with the external price, no fees or
costs, and quote-denominated marking. The LP's normalized marked wealth is
exp(R/2). Holding the same initial equal-value token inventory instead gives
(1+exp(R))/2. The arithmetic-geometric mean inequality implies

    exp(R/2) <= (1+exp(R))/2

for every R, with equality only at R=0. Adding the same nonnegative cash allocation
preserves the ordering, as does log utility. Therefore a forecast cannot make
this idealized fee-free LP dominate its matched buy-and-hold inventory. Comparing
only against cash would miss this economically essential control.

With fees, dilution or reserve-price misalignment, use the actual marked claim
ell/S * (reserve_quote + P_external * reserve_base). The simplified square-root
formula is insufficient unless its alignment and supply assumptions hold.
Future fee revenue is not identified by a return forecast alone, and replaying
observed swaps under altered policies does not identify counterfactual demand.

## Admission implications

Before any decision evaluation, declare quote units, strictly positive wealth,
cost treatment, feasible LP entry/exit, information timing and the fee-revenue
model. Include cash, matched initial-inventory buy-and-hold, and any appropriate
fixed LP control. Verify posterior integrability rather than assuming it from
sample finiteness. This objective is a way to pose a finite research question;
it is not a shortcut around economic identification or profitability evidence.

## Posterior obstruction for the current scale prior

The model places a Gaussian prior on l=log(sigma), with positive variance and
unbounded support. Consider any compact set of physical latent states h_1:T,
mu and beta with nonzero volume and positive prior density. For finite observed
returns, their Student-t likelihood is continuous and bounded below by a
positive constant on this set. The stationary AR(1) path density is proportional
to sigma^(-T) exp(-Q(h,mu)/(2 sigma^2)); Q is bounded on the compact set.
Consequently, for sufficiently large l the unnormalized posterior density,
integrated over this set, is bounded below by

    C exp(-T l) exp(-(l-m)^2/(2 s^2)),   C>0, s>0.

Assume the posterior normalizer is finite and nonzero. The next latent state is
Gaussian with innovation variance sigma^2. Conditional on h_T,mu,sigma,

    E[exp(h_next/2)] = exp((mu + rho(h_T-mu))/2 + sigma^2/8).

The first exponential factor is bounded below on the compact set. Integrating
the second factor against the posterior lower bound gives an integral whose
integrand grows as

    exp(exp(2l)/8 - T l - (l-m)^2/(2 s^2)).

It diverges. A Student-t(5) innovation has a finite positive first absolute
moment, but its scale mixture therefore has infinite posterior-predictive first
absolute moment. Bounded beta on the same set cannot remove the divergence;
the symmetric innovations give infinite positive and negative return moments.

For 0<w<1 and positive a, log((1-w)+w exp(aR)) has a bounded negative part but
a positive tail growing linearly in R. Its posterior-predictive expectation is
therefore +infinity under these assumptions, rather than a finite optimization
criterion. For w=1, the expectation of aR is undefined because both parts
diverge. A finite empirical posterior mixture hides this far-tail obstruction.

This analytical derivation needs independent mathematical review before a
publication claim. It rules out treating conditional integrability as proof of
posterior integrability. Possible future alternatives include bounded utility,
quantile-based objectives, or a separately justified model/prior change; none
has been admitted here. Changing the prior would change the inferential target
and would require new validation rather than silently reusing existing claims.

## Binding the derivation to implementation

The no-flow target in `../market_uncertainty_v1/sv_prototype/target.py` uses
Gaussian priors directly on log_sigma and standardized latent innovations.
Its physical path starts with stationary variance sigma^2/(1-rho^2) and uses
innovation scale sigma thereafter. The equivalent physical-path density has
the sigma^(-T) factor used above; omitting this Jacobian would give the wrong
tail bound. The factor does not overcome exp(sigma^2/8).

`../predictive_value_diagnostic_v1/predictive_density.py` integrates the next
state as h_next=mu+rho(h_last-mu)+sigma*z. Its observation scale is exp(h_next/2),
which supplies precisely the conditional scale moment in the derivation.
Finite observed-label density and CDF calculations are distinct functionals;
this obstruction does not by itself invalidate those preserved pointwise
predictive calculations. It does invalidate inferring finite unbounded utility
moments from their successful numerical checks or from finite posterior samples.
