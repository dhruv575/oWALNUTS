# Posterior normalizability: exact ties in the current no-flow SV target

Status: analytical derivation and data audit; independent mathematical review
is still required. This is a model-admissibility issue shared by samplers, not
an algorithm ranking. Do not interpret passing finite-chain diagnostics as
proof of a normalized posterior for the affected inputs.

## Target and assumptions

The current model uses y_i | beta,h_i ~ Student-t(nu,beta,exp(h_i/2)), a common
Gaussian-prior location beta independent of the latent process, fixed |rho|<1,
Gaussian-prior mu, and Gaussian-prior l=log(sigma) with positive variance and
unbounded support. All priors are proper and positive at finite parameter values.
In physical latent coordinates the stationary AR path density is proportional
to sigma^(-T) exp(-Q(h-mu)/(2 sigma^2)), with a positive-definite quadratic form Q.
This includes the change of variables from standardized innovations; a proper
prior alone does not imply that the likelihood-weighted measure is finite.

## Repeated observations produce a divergent normalizer

Suppose m>=2 observations equal the same finite value a exactly. Let v have
ones at these indices and zeros elsewhere, and let q=Q(v)>0. Restrict mu and
the other latent coordinates to fixed compact sets. Restrict each tied latent
coordinate to a fixed-width box around -x, and beta to an interval of width
proportional to exp(-x/2) around a. Gaussian prior density for beta is bounded
below there for large x. The tied standardized residuals stay bounded, so their
likelihood product is bounded below by C*exp(m*x/2). Integrating beta over that
interval leaves C*exp((m-1)*x/2). Every other observed-data likelihood has a
positive uniform lower bound on the chosen compact coordinates.

Set x=epsilon*sigma^2. Uniformly over these boxes,

    Q(h-mu) = q*x^2 + O(x) + O(1).

The integral over the boxes and beta is therefore bounded below, for large l,
by a positive constant times

    exp(c*exp(2l) - T*l - (l-m_l)^2/(2*s_l^2)),
    c = ((m-1)*epsilon - q*epsilon^2)/2.

Choose 0<epsilon<(m-1)/q, giving c>0. This lower bound has divergent integral
over l. The boxes may depend on l; their h-volume is fixed, and their shrinking
beta-volume was already included. All quantities are nonnegative, so Tonelli
applies without cancellation. Under the stated exact-density model, the
posterior normalizer is infinite whenever there are at least two exact ties.

## Distinct observations have a finite normalizer in this specific model

For finite T>=2 pairwise distinct observations let d=min_{i!=j}|y_i-y_j|>0.
For Student-t location-scale density, sup_{s>0} f_nu(r;s)<=C_nu/|r| for r!=0,
where C_nu is finite. Partition the beta line by its nearest observed value.
In region i every other residual has absolute value at least d/2. Thus all
likelihood factors except i are at most (2*C_nu/d)^(T-1). Integrating the i-th
factor with respect to beta is at most one; multiplying by the bounded Gaussian
beta prior gives an upper bound M*T*(2*C_nu/d)^(T-1), uniform in the latent path.
The independent proper latent/hyperparameter prior then integrates to one.
Positivity supplies a nonzero normalizer. T=1 follows directly from the bounded
beta prior. This argument is specific to the shared location and independence
assumptions; it does not automatically cover covariate models.

Propriety for distinct observations does not imply finite predictive moments.
The separate log-wealth tail obstruction still applies on proper targets.

## Observed scope and immediate implications

An exact-float64 audit of every initial/update T250 window found:

| Month | Windows including initialization | Windows with ties | Largest multiplicity |
|---|---:|---:|---:|
| 2025-12 | 1489 | 0 | 1 |
| 2026-01 | 1489 | 155 | 2 |
| 2026-02 | 1345 | 311 | 3 |

The tied values found were zero returns. Among the fixed sentinel windows,
February tick 577 contains two zeros. The other 23 sentinel windows are
pairwise distinct in the audit. The repeated five-value literal readiness
fixture also has exact ties: its finite numerical checks remain useful for
execution/evidence plumbing, but cannot establish proper-posterior fidelity.

Retain the already frozen sampling campaign and all outcomes. Its diagnostic
and timing reports must carry this additional model-admissibility limitation;
do not silently relabel a previously passing reference as mathematically valid.
No new posterior-fidelity or economic experiment should be admitted on affected
targets until the observation model or prior is justified and revalidated.
Do not jitter away ties or drop affected windows after seeing results.

Candidate repairs are research choices, not completed fixes. A correctly
specified finite-resolution observation likelihood is bounded by one and gives
a proper posterior with proper priors, but return intervals derived from rounded
prices can be dependent and need a defensible measurement model. A bounded
innovation scale can also supply integrability bounds, but changes the prior
and requires scientific justification and new validation. Neither repair may
silently inherit the current target's empirical claims.
