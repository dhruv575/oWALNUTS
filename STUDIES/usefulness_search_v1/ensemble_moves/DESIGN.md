# Reviewed next mechanism: ensemble-assisted independence MH

Motivation: bounded_init's Lotka failure is unchanged from unbounded scaling;
the affected chain has substantial movement and a normal step in a separated
basin. Clipping did not activate. This is not a zero-movement trap. Do not force
chains into a higher-density basin without a probability correction: density
height alone does not determine mode probability.

Established context, not a novelty claim: Goodman and Weare (2010) formulate
ensemble sampling on a product target and update each walker conditional on the
current complementary ensemble. Walker trajectories can be dependent even though
the invariant distribution factors. See Sections 1--2:
https://msp.org/camcos/2010/5-1/camcos-v5-n1-p04-p.pdf.
Mixtures of multivariate t proposals are also established MH machinery; the
adaptive scheme of Tran, Pitt and Kohn is related but different:
https://arxiv.org/abs/1305.2634. High-dimensional ensemble behavior needs explicit
validation; known failure examples caution against inferring convergence from
apparent agreement: https://arxiv.org/abs/1509.02230.

Proposed research-only composition (derivation):

Let X=(x_1,...,x_C), Pi(X)=product_i pi(x_i). Fix positive-definite proposal scales
S_j before retained sampling, initially using each chain's warmup metric converted
to position covariance after auditing that convention. For updating walker i,
hold the other walkers fixed and define

q_i(y | X_-i) = sum_{j != i} t_5(y; x_j,S_j)/(C-1).

Choose j uniformly, draw the corresponding multivariate t candidate, and accept
with min(1, pi(y) q_i(x_i|X_-i) / [pi(x_i) q_i(y|X_-i)]).
Evaluate the full mixture in both directions, not just the selected component.
For fixed X_-i, accepted flux is
min(pi(x_i) q_i(y|X_-i), pi(y) q_i(x_i|X_-i)), so the conditional kernel preserves
pi. Sequentially updating one walker at a time preserves Pi. Compose with local
WALNUTS transitions that each preserve pi at fixed tuning. A deterministic or
state-independent random scan is valid. Simultaneous coupled proposals with stale
complements are not justified by this proof and are forbidden in this prototype.

No selection based on density rank, no forced rescue, no learned-scale updates
from retained states. Nonfinite proposals reject and are counted; invalid current
density is an error. This proof establishes invariance, not finite-run mixing or
usefulness. Local moves may run in parallel; ensemble updates must be sequential.
All target/proposal work is charged. Include the same augmentation for a strong
NUTS control before making a WALNUTS-specific claim.

Next implementation gates, before an application batch:
1. Deterministic proposal-density checks against scipy's multivariate t and
   forward/reverse accepted-flux checks in several dimensions.
2. Stationarity tests initialized from exact independent draws, including an
   unequal-weight, unequal-width mixture whose broad lower-density mode has most
   of the mass. Check means, variances, mode probabilities and cross-walker moments.
3. Fixed-kernel integration audit: actually change the next local transition's
   starting position and refresh gradients; never relabel completed draws.
4. Independent-ensemble replication for any MCSE/ESS claim. Within one ensemble,
   walkers share temporal dependence; do not treat them as independent chains.
   Analyze per-sweep ensemble-average functionals and replicate entire ensembles.
5. Exposed Lotka replay may check mechanics only. Any efficacy screen must freeze
   fresh seeds, known-target tail controls, failures, cost/accuracy gates and strong
   comparison arms first. No deployment/default change is authorized by a pilot.

This is a proposed experiment, not a demonstrated improvement. The bounded
initialization experiment remains a failed screen regardless of this next result.
