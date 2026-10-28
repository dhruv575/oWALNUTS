# Independent one-observation posterior reference

For fixed y and cap S, let theta=(mu,log_sigma,z) have the normalized bounded
prior. Draw theta from that prior. Compute h=mu+exp(log_sigma)*z/sqrt(1-rho^2).
Propose beta from Student-t_5(location=y, scale=exp(h/2)). By symmetry this
proposal density in beta equals the observation likelihood f(y|beta,h).

The proposal joint density is therefore p(theta)*f(y|beta,h). The desired
posterior is proportional to that density times p(beta). For beta~N(0,s_b^2),
p(beta)<=M=1/(sqrt(2*pi)*s_b). Accept with probability

    p(beta)/M = exp(-beta^2/(2*s_b^2)),  s_b=.002.

Accepted proposals are independent posterior draws (up to the implementation's
random-number and floating-point approximations). The acceptance probability
is Z/M, positive and <=1. This avoids Markov-chain mixing assumptions. It
does not extend directly to repeated observations, where one beta proposal
cannot absorb the full likelihood product with the same envelope.

Draw log_sigma from the upper-truncated Gaussian prior, then convert to
eta=softplus_inverse(log(S)-log_sigma), the implemented unconstrained coordinate.
Preserve the entire fixed proposal count, accepted arrays, seeds and failures.
Do not keep drawing until a favorable estimate or accepted count appears.
Normalization and Jacobian are checked by density ratios separately from
posterior comparisons. Caps .5,1,2 remain sensitivity cases, not selected priors.
