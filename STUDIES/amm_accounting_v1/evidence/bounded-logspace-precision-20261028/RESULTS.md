# Direct log-space density validation

The captured finite proposal has a mathematically finite log density despite
the physical scale underflowing in double precision. Direct signed log residuals
avoid reconstructing physical beta or observation scales. With h_i=mu+sigma*a_i
and s=mean(h)/2, compute the standardized residual as the signed difference of
y_i*exp(-h_i/2) and b*exp(s-h_i/2), retaining their logarithms. The difference
s-h_i/2 is formed directly as sigma*(mean(a)-a_i)/2 to avoid cancellation of mu.
The original physical-beta prior and s Jacobian are retained.

At the captured proposal, a 90-decimal-digit mpmath evaluation gives log density
-238656474121.149190431130699016. The double result differs by 0.00014258. Five
selected derivatives agree within the declared tolerances, with maximum observed
absolute error 4.533e-11. All thirteen tests passed: representable parity for
three dimensions and three caps, this captured proposal, and all-coordinate
arbitrary-precision derivative checks on three additional underflow fixtures
with mixed zero/nonzero observations and negative/zero/positive b.

The AWS independent Stan check additionally passed 72 representable cases,
max density error 8.732e-11 and gradient error 5.412e-11; see the sibling
bounded-logspace-stan-20261028 evidence. Stan scale underflow is not used as the
oracle for the captured proposal; that comparison uses arbitrary precision.

This is a Python density/gradient validation, not a repaired native callback or
a successful sampling rerun. The direct implementation deliberately raises on
unrepresentable output/gradients. Positive-scale overflow and the native ABI's
recoverable-rejection policy need explicit treatment before another panel.
Do not reinterpret arbitrary NaNs as genuine zero-density points.
