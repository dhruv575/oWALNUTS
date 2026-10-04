# Mixed-target cost profile

The compiled public T1000/G4 mixed block32 density-and-gradient call took a
median 80.50 microseconds across five blocks of 1,500 calls. Identical dispatch
controls took 0.394 microseconds for a no-op and 0.482 microseconds when also
zeroing the gradient buffer. Compilation took 3.09 seconds. Both contained
processes exited successfully; total profile and separate parity cost was
11.80 seconds.

The profile uses two archived starts and three archived posterior positions,
with no new sampling or random streams. The independent JAX density and the
canonical density plus coordinate Jacobian agreed at all five points; maximum
gradient discrepancy was approximately 1.57e-12. Exact commands, bindings,
positions, values, gradients, graph inventory and timing blocks are retained.

The earlier full sampling study averaged about 83.3 microseconds per retained
target call, including trajectory and other work. The similar scale suggests
model evaluation dominates that workload, but different measurement scopes and
position mixtures prevent treating the difference as an exact Rust-overhead
estimate. This is exploratory profiling, not a new sampler speed result.

The next development step is to inspect algebraically equivalent density
expressions under automatic differentiation. Any candidate requires independent
value/gradient checks and fresh full-workflow validation; this profile changes
neither the failed speed criterion nor the planned resource-screen recipe.
