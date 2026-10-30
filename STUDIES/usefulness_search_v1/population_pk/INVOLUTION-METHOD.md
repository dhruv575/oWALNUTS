# Model-aware Metropolis moves: derivation before testing

This uses established involutive Metropolis theory, not a new generic method:
Neklyudov et al., *Involutive MCMC: a Unifying Framework* (ICML 2020), Eq. 5,
https://proceedings.mlr.press/v119/neklyudov20a/neklyudov20a.pdf.

Write the physical log parameters as a=log ka, e=log ke, v=log volume/kg.
The rate exchange is S(a,e,v)=(e,a,v+e-a). S squared is identity and det DS=-1.
For each subject q=mu+diag(tau)z. Holding hyperparameters fixed, the local move
is z'=diag(tau)^-1(S(q)-mu); its absolute Jacobian determinant is one. The
population hyperparameters and remaining subjects are unchanged.

The global move sends mu to S(mu), swaps log tau_a and log tau_e, keeps tau_v,
swaps each z_a,z_e, and sends z_v to z_v+(tau_e/tau_v)z_e-(tau_a/tau_v)z_a.
Applying it twice returns the original coordinates. The Jacobian is block
triangular in (mu,log tau,z,log sigma): the mu and log-tau blocks each have
determinant -1, each of 12 subject blocks has determinant -1, and sigma has
determinant1. Thus total determinant1. Cross derivatives of z with respect
to log tau do not change this block-triangular determinant.

Neither the priors nor nonzero-baseline likelihood are presumed invariant.
Accept each proposed exchange with min(1,exp(log pi(Tx)-log pi(x))). The pairwise
accepted flux equals min(pi(x),pi(Tx)), establishing detailed balance for the
volume-preserving involution. Nonfinite proposals reject; current density must
be finite. A fixed composition with a valid local HMC/WALNUTS kernel preserves
pi, although the composition need not itself be reversible. This does not prove
ergodicity or adequate mixing. An affine whitening change cancels from the
Jacobian, so the same acceptance ratio applies after transformation.

Moves must modify the state used by the next transition. Relabeling recorded
draws after sampling is not this algorithm. A state-dependent choice among
moves would require additional justification; use a fixed global move plus
a uniformly selected subject, independent of state. No tuning from retained
draws. Both WALNUTS and NUTS must receive the same move schedule and baselines.
