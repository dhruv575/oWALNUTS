# Shared-target sampling pilot (not accuracy validation)

Native 43-parameter linear population target matches checked Python assembly
at 12 points (max scaled gradient discrepancy <4e-15). A gradient-free analytic
density matches log-density differences to <2e-13, so importance baselines need
not pay for gradients. Whitening transformation parity is verified.

Rate exchange is exact only for zero-baseline subjects (9/12). A scaled-objective
optimization finds a secondary qualified mode; the unscaled optimizer's false
convergence and the initial overbroad symmetry assertion are preserved. Local
Laplace log mass ratio is -21.87, an unverified approximation rather than proof
the secondary region has negligible posterior probability.

Before expensive qualification, two bounded implementation/mixing pilots:
WALNUTS and NUTS, whitened by primary-mode Hessian, target acceptance .99,
max depth 12, four chains, 1000 warmup/1000 retained, one core each. Seeds
930100001 (WALNUTS), 930100002 (NUTS). Chains 0/2 start near primary and 1/3
near secondary mode. 300s, 2GiB RSS, 16MiB sampled output cap per job. Preserve
all results; no reruns. Report callback errors, divergences, depth hits, basic
parameter diagnostics and rate-order occupancy. This pilot cannot select a
winner or qualify a reference. Independent calibration/reference/validation
seeds, functionals and thresholds must be frozen before the next phase.
