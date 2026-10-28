# Independent conditional reference design

The four synthetic NUTS fits passed finite diagnostics. An independently
implemented transition mechanism remains necessary for stronger fidelity
evidence. Candidate: alternate Gaussian-prior elliptical slice updates of
the core coordinates with exact conditional price updates in physical X.

Elliptical slice sampling is established methodology, not a new contribution:
Murray, Adams and MacKay (2010), https://proceedings.mlr.press/v9/murray10a.html.
Apply it to the standardized joint Gaussian prior coordinates corresponding
to mu, log(sigma), beta and z, conditional on X. Center and scale the three
hyperparameters by their declared prior means and standard deviations. The
non-Gaussian factor is the return likelihood; do not include Gaussian priors
again in its slice threshold. Deterministic blocks are allowed provided each
uses the correct conditional Gaussian prior and the whole likelihood.

For a physical price coordinate X_i within its finite cell, its conditional
density is proportional to f_i(X_i-X_(i-1)) times f_(i+1)(X_(i+1)-X_i), with
the second term absent for i=T. A uniform-in-cell proposal can be accepted with
probability equal to this product divided by the product of the corresponding
Student-t peak densities. Each density is bounded by its zero-residual peak,
so the ratio is at most one. Drift belongs in both residuals with the proper
sign. Accepted proposals are exact conditional draws, conditional on ordinary
floating-point accuracy. No Jacobian appears in physical X; transform to u
only for comparison with stored NUTS coordinates.

Sequential Gibbs updates preserve the joint target. Alternating even/odd
coordinates can be vectorized because each conditional depends only on its
neighbors; same-parity coordinates are conditionally independent. Update the
second parity using the newly updated first parity. Do not update all sites
simultaneously using stale neighbors and call that Gibbs sampling.

Rejection and slice loops require attempt caps and outer resource supervision.
If a cap is reached, abort and preserve the failed chain; treating a truncated
conditional sampler as a successful update would change its kernel. Low
acceptance can make this reference impractical, which must be reported.

Before admission: compare conditional densities with the existing joint target,
validate boundary and neighbor indexing, and compare T1 output with the saved
independent rejection reference. Then freeze a bounded multi-chain panel with
fresh audited seeds and all-coordinate diagnostics. This is a reference design,
not yet an implemented or validated long-window oracle.
