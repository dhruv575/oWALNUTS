# Latent GP count candidate: provenance and next gate

2026-10-30 source audit. The existing PosteriorDB `gp_pois_regr-gp_pois_regr`
benchmark is **synthetic**, not an actual use case. Its data metadata explicitly
says "Simulated data from a Poisson GP model." There are 11 counts at equally
spaced coordinates -10 to10, with 13 unconstrained parameters: log length scale,
log amplitude and 11 whitened latent Gaussian coordinates. Priors are
rho~Gamma(25,4), alpha~half-Normal(0,2), whitened coordinates~N(0,I). The kernel
is squared exponential with a 1e-10 diagonal jitter; observations are Poisson
with log intensity f. There is no supplied held-out or decision endpoint.

Authoritative files on the existing research instance:
- `/home/ubuntu/infra/posteriordb/posterior_database/data/info/gp_pois_regr.info.json`
- `data/data/gp_pois_regr.json.zip` under the same database root
- `models/stan/gp_pois_regr.stan` and `models/info/gp_pois_regr.info.json`
- `posteriors/gp_pois_regr-gp_pois_regr.json`
- `reference_posteriors/draws/info/gp_pois_regr-gp_pois_regr.info.json`

Metadata points to the Stan benchmark repository; this audit uses the preserved
database files, not an assumption about a current external dataset. The stored
reference has 10 chains, 1000 saved draws each, from 20000 iterations per chain,
10000 warmup and thinning10, adapt_delta .99, depth15. Reported reference
diagnostics are good across rho, alpha and f. Recompute diagnostics for any new
functional; do not blindly inherit the reference label for intensity tails.

Historical local evidence is mixed, not universal failure. All nine GP cells in
late_metric's repaired screen pass; the table's 0/3 values count dense choices.
In reconsider, one GP seed (927100002) fails identically in all three arms:
Rhat1.0135, tailESS331.6, bulkESS519.0, no divergences. This does not establish
an advantage over strongly tuned NUTS or a need for a new sampler mechanism.

Next reviewed action: a small frozen Laplace/defensive-importance audit against
the preserved reference, including rho, alpha, f and intensity exp(f), with
full MAP/discovery cost and independent importance replicates. Verify numerical
gradients/curvature and qualify new reference functionals first. If cheap
correction works, drop this benchmark as motivation for an expensive application
campaign. If it fails, compare tuned native NUTS and an appropriate latent-
Gaussian method before seeking a real count-data application. Do not manufacture
a use case by relabeling this 11-point synthetic benchmark.
