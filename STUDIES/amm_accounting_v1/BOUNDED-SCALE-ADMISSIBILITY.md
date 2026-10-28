# A separate bounded-scale prior candidate

Status: analytic derivation requiring independent mathematical review; no prior
bound selected and no empirical results transferred. This is an alternative
research branch to the finite-price-cell observation model, not a silent repair
of the original target or a claim that data are continuously observed.

## Finite normalizer for every finite observation vector

Retain the original point-return model with fixed nu=5 and |rho|<1, independent
Gaussian priors mu~N(m,v) and beta~N(b,w), and standardized stationary Gaussian
AR innovations. Replace the unbounded lognormal innovation scale with a proper
prior supported on 0<sigma<=S for a finite declared S, independent of mu,beta.
For example, a truncated lognormal needs its normalization and bound explicitly
recorded. This changes the scientific prior; S cannot be selected merely to
make a desired comparison pass.

For any finite y and any beta, the Student-t density is at most its peak:

    L(y | h,beta) <= c_nu^T exp(-sum(h)/2).

Let C_ij=rho^|i-j|/(1-rho^2). Conditional on sigma, integrating mu and the
Gaussian innovations gives h~N(m*1, v*11' + sigma^2*C). Consequently

    E_prior[L | sigma]
      <= c_nu^T exp(-T*m/2 + (T^2*v + sigma^2*1'C1)/8)
      <= c_nu^T exp(-T*m/2 + (T^2*v + S^2*1'C1)/8) < infinity.

C is positive definite even for negative rho, so 1'C1>0. Integrating beta and
the proper bounded sigma prior preserves this bound. Likelihood positivity
on finite states supplies Z>0. Thus 0<Z<infinity for every finite observation
vector, including any number of exact ties. The bound may be numerically huge;
it proves integrability, not practical conditioning or sampler efficiency.

## Posterior predictive absolute log-return moment

Write next log return R=beta+exp(h_next/2)*epsilon, epsilon~t_5. Its conditional
first absolute moment is at most |beta|+E|epsilon|*exp(h_next/2), with E|epsilon|
finite. Multiplying by the likelihood bound above produces two terms:

    c_nu^T |beta| exp(-sum(h)/2),
    c_nu^T E|epsilon| exp((h_next-sum(h))/2).

The first integrates because beta has finite first absolute prior moment and
is independent of the Gaussian path. For the second, augment C to include
h_next. The exponent is a fixed linear functional of a jointly Gaussian path
conditional on sigma, so its exponential moment is finite and uniformly
bounded over sigma<=S by the same Gaussian moment-generating-function argument.
Dividing these finite integrals by Z proves E[|R| | y]<infinity.

This supplies the integrability needed by the previously stated nonlevered
log-wealth bound |log((1-w)+w*exp(aR))|<=|aR|, under its strictly positive wealth
and bounded-cost assumptions. It does not create expected-dollar-wealth
moments: the Student-t log-return still has no nonzero exponential moment.
Nor does it establish fee revenue, counterfactual demand or realized profit.

The bounded finite-price-cell likelihood also permits posterior predictive
absolute-moment bounds when paired with this bounded-scale prior: its event
likelihood is <=1, so any finite prior predictive absolute moment remains
finite after conditioning on a positive-probability observed-cell event.
That separate change still needs an observation-model justification.

## Exact range of predictive absolute moments

The same argument extends beyond the first moment. For any 0<p<nu, define
C_p=max(1,2^(p-1)). The elementary inequality
|x+z|^p<=C_p(|x|^p+|z|^p) gives

    E[|R|^p | beta,h_next]
      <= C_p (|beta|^p + E|epsilon|^p exp(p*h_next/2)).

After multiplying by the likelihood peak bound, the first term integrates
because a Gaussian beta has every positive absolute moment. In the second,
the exponent is a'h_aug with a=(-1/2,...,-1/2,p/2). Its prior expectation,
conditional on sigma, is exactly

    exp(m*sum(a) + [v*sum(a)^2 + sigma^2*a'C_aug*a]/2).

Positive semidefiniteness and sigma<=S give a finite uniform bound. Since the
posterior normalizer is positive and finite, every posterior predictive
absolute moment of order p<nu exists. Conversely, for p>=nu, every conditional
Student-t distribution with finite location and strictly positive scale has
infinite p-th absolute moment. Translation and positive scaling do not change
the tail exponent. Tonelli then makes the posterior predictive moment infinite.

Thus for the current nu=5 candidate, the absolute moments exist exactly for
0<p<5: in particular variance and fourth moment are finite, while the fifth
absolute moment is infinite. This conclusion holds for every finite observed
vector under the stated bounded-scale and Gaussian-prior assumptions. It does
not imply stationarity of real market returns or adequate finite-sample power.

For any nonzero t, conditional E[exp(t*R)] is still infinite because a Student-t
tail cannot offset exponential growth in the corresponding direction. Tonelli
again preserves this divergence under posterior mixing. Finite variance of log
returns therefore cannot justify finite expected gross returns or expected
dollar wealth. This extension is an analytic derivation, not independent
mathematical review or a numerical verification of the theorem.

## Scientific admission remains open

Choose a scientifically defensible scale range using declared prior-predictive
volatility behavior and external knowledge, then perform bound sensitivity,
calibration and held-out comparisons. A hard upper bound excludes some
volatility dynamics. It must be assessed against shocks, regime changes and
the sampling interval rather than justified by posterior diagnostics alone.
This derivation prevents an unnecessary inference that a finite-cell model
is the only possible repair; it does not select between candidate models.
