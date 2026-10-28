# Bounded-scale candidate target contract checks

All 48 deterministic comparisons against independent Stan autodiff passed:
caps .5,1,2; T=1,4,12,250; four cases including exact repeated observations
and transformed scale coordinates -20,0,2,20. Maximum absolute density error
was 1.024e-12; maximum gradient error was 1.572e-9. Both implementations include
the truncated lognormal normalization and eta-to-log_sigma Jacobian.

Separate local tests numerically integrated the transformed prior to one for
all three caps, compared normalized densities to SciPy, checked all gradients
by central differences, and checked finite evaluation at eta=+-1000. Those
extreme numerical checks are not tail-integrability proofs.

AWS comparison took 13.893 seconds including compilation, under a 180-second
timeout, four-core affinity and 4 GiB per-process address-space limit. The
three source hashes were checked against exact uploaded archive bytes and
preserved here, together with the shared library hash and raw comparison log.

No posterior sampling or empirical forecasting was performed. The bounded
prior changes the model; these tests do not select a cap, validate the market
observation approximation, establish posterior fidelity or justify economic
claims. The analytic propriety and moment argument remains separately marked
for independent mathematical review.
