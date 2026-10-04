# Conditional-whitening gradient hypothesis

The current symbolic model constructs four scans: stable information filtering, forward substitution for v, backward substitution for the guide mean, and backward substitution for the sampled innovation. Generic reverse differentiation adds further scans. Source inspection establishes this structure, not quadratic complexity or an allocation bottleneck.

The first exact simplification is h = L^-T(v+z), replacing m=L^-T v and delta=L^-T z followed by addition. This remains valid when the factors and v depend on both sampled scales. It removes one backward solve without approximating the density.

Potential reusable primitives are lower and transposed bidiagonal solves, with compiled linear loops and analytic first-order vector-Jacobian products. For y=L^-1 b and output cotangent g, db=L^-T g, dd=-db*y, de_i=-db_(i+1)*y_i. For y=L^-T b, db=L^-1 g, dd=-db*y, de_i=-db_i*y_(i+1). These generic O(T) operations require length, dtype, positive-diagonal and T=1 contracts. Differentiating these VJPs for higher-order derivatives is a separate support decision; first-order sampler gradients must never silently claim higher-order support.

For f_next=w+r*f_prev/(r+f_prev), the reverse derivatives are df_next/df_prev=(r/(r+f_prev))^2 and df_next/dr=(f_prev/(r+f_prev))^2. A reverse accumulator must combine direct cotangents on every f with propagated cotangents, accumulate dw at every recurrence, and include f0=w+anchor_precision. Stable ratio formulas avoid forming an overflowing r+f_prev. The mathematical recurrence is smooth at r=f_prev despite min/max implementation branches.

All guide dependence must remain differentiated: w=exp(-2log_obs), r=exp(-2log_rw)/dt, factors, b, mean and the exact log Jacobian -sum(log(diagonal)). The likelihood remains normalized Student-t. No fitted truth or posterior-derived transformation enters these coordinates.

Do not implement or assert a speed benefit until a quiet target-only profile isolates setup versus repeated compiled value-and-gradient calls, checks T scaling and allocations, and inspects the actual optimized gradient graph. The observed case00 candidate has 162s parity and 475s sampling, so fixing unrolled parity alone cannot remove most of its measured cost. Preserve the existing full workflow costs.

Any prototype requires independent canonical-density-plus-Jacobian checks, independent JAX gradients and finite differences over both log scales, irregular dt, T=1/T=2/T=128 and larger paths, strongly unequal precision ratios and tie cases. Then compare identical physical starts and unchanged diagnostic/endpoint gates with all compilation, parity and failed attempts charged. This is an unimplemented design hypothesis, not a demonstrated generic sampler improvement.
