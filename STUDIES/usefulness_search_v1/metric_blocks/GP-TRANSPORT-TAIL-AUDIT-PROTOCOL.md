# Exposed native-transport failure diagnosis

Inspect all eight native quadratic validation fits, including the five failures. The available unconstrained draws are selected transition endpoints, not the rejected divergent proposals. A divergence flag labels a transition; associations with its selected endpoint cannot establish where integration failed or prove a causal mechanism.

For each endpoint compute original q with the fixed map and the exact analytic map Jacobian. Report its singular-value range/condition number, maximum absolute z, rho=exp(q1), and alpha=exp(q2). Retain per-point arrays. Summarize each chain and divergent/nondivergent transition cohorts: count, median/max Jacobian condition, median/max largest singular value, coordinate ranges, fixed retained step, mean tree acceptance and step count. No hypothesis tests, iid bootstrap or posterior correctness claims on failed chains. Include zero-divergence fits and all chains.

Independently central-difference the decoder Jacobian at first/middle/last points of each fit, fixed perturbation1e-5 and scaled error<=1e-6. The Jacobian is of the explicit map only, avoiding noisy GP density differences. Reuse exact preserved map parameters, no fitting or new sampling. Check that per-transition divergence counts equal stored summary counts and that inputs remain hash-identical. This diagnosis cannot amend the failed validation or justify deleting any draw.

Bound180 seconds/2 GiB/64 MiB, BLAS1. Use findings to choose between inspecting divergent proposals, a map-tail regularization experiment, or a precision-budget study. Do not assume that lower bulk geometry discrepancy implies benign tails.
