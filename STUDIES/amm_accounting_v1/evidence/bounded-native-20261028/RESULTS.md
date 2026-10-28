# Bounded-scale native callback admission

All 108 deterministic comparisons passed between the owned WALNUTS native
callback and the Python analytic density/gradient. The panel crosses caps
.5/1/2, T=1/12/250, all-zero/distinct sinusoidal observations, and eta values
-1000/-20/0/2/20/1000. Maximum absolute density error was 8.615e-9 and maximum
absolute gradient error 2.329e-10. Relative tolerances also apply, particularly
to the very large negative log densities at extreme eta.

Caller mutation did not change the callback's data snapshot. Nonfinite inputs
returned NaN density and gradients. Source hashes are in NATIVE-PARITY.json.
The callback includes the truncated prior normalization and eta Jacobian.
This is implementation admission, not sampling fidelity or an advantage claim.

Executed on the existing AWS instance using the pinned research environment,
one CPU, one BLAS/OpenMP thread, a 300-second timeout and 4-GiB virtual-memory
limit. Check elapsed time was 6.611 seconds. No MCMC or random seeds were used.
