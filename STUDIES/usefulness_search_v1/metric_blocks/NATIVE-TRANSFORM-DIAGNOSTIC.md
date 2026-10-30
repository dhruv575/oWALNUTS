# Recovering the native affine metric

The failed four-seed screen motivates separating metric learning from kernel
behavior. Do not promote the rejected scaled policy or tune its acceptance gate.

Tagged nutpie0.16.11 Cargo.lock pins nuts-rs0.18.3. Its crate was downloaded and
SHA256-verified against the lockfile. This establishes source provenance, not
binary build identity for the installed wheel. Upstream references:
- https://github.com/pymc-devs/nutpie/blob/v0.16.11/Cargo.lock
- https://docs.rs/crate/nuts-rs/0.18.3/source/src/transform/low_rank.rs

The low-rank stats exporter stores scales and square-root eigenvalues, but no
eigenvectors. The transformed Hamiltonian can additionally record original and
transformed positions and gradients. A fixed affine map x=A*z+mu can therefore
be recovered from full-rank paired positions and checked on unused positions and
via the gradient identity g_z=A^T*g_x. Its implied covariance is A*A^T. Recovering
this map is established linear algebra, not a new estimator.

Exposed arK seed940700001 uses 200 warmup and 100 discarded probe draws, four
chains, native low_rank cutoff2/gamma1e-5. Recording enabled/disabled yields exact
retained trajectory parity. Fit each chain's map on the first50 positions and
validate the remaining50. Require a constant transformation_index, full design
rank, design condition<1e8, positive covariance eigenvalues, and normalized
maximum position/gradient residuals<1e-10. All four pass: position residuals at
most1.845e-15 and gradient residuals at most2.540e-14, design conditions<2.37.
This is instrumentation qualification, not posterior accuracy evidence.

Next steps before a mechanism comparison:
1. Generalize reconstruction qualification to the other five targets. Preserve
   rank failures, nonconstant transforms and API failures; do not loosen gates.
2. Qualify any frozen-metric injection with an analytic Gaussian covariance and
   gradient/energy checks. A metric needs consistent momentum and position
   conventions; numerical equality of a matrix alone is insufficient.
3. Compare frozen geometry and matched initialization, keeping metric-learning
   cost separate but fully charged in workflow totals. If the native public API
   cannot hold the learned transform fixed, use a reviewed isolated backend
   harness and establish parity before attributing a difference to the kernel.
4. Any useful improvement needs fresh replication and application controls.
   Sharing a learned metric is a diagnostic, not a novel contribution or goal
   completion. Native pilots and all discarded recovery draws are real costs.

Cloud remains stopped under the budget constraint. Work is bounded and local.

## Six-target qualification update

The identical reconstruction check now passes the other five targets as well:
24/24 chains across all six targets. Each model worker exits successfully and
drains; raw enabled/disabled traces and source hashes are preserved. These are
exposed short runs, including models whose posterior accuracy screen failed.

An independent algebra/target-gradient check verifies 72 transformed versus
original-coordinate leapfrog steps (24 maps, step sizes .0001/.001/.01), using
momentum covariance M=(A*A^T)^-1 and p=A^-T*r. Maximum normalized kinetic,
position or momentum discrepancy is 2.226e-12 under a frozen1e-8 tolerance.
This Python check does not execute the WALNUTS kernel.

Five existing Rust dense-metric tests also pass in an isolated offline locked
build: deterministic precision-metric accounting, sequential/parallel physical
coordinate parity, error ordering, inactive budget-control parity and rotated
geometry adaptation. The build/test took31.46s, peakRSS862MB and638MB cache.
This checks existing implementation coverage, not native metric-transfer parity.
The next needed artifact is a frozen per-chain-metric/step-size research runner
and an analytic-target injection check before a matched-geometry comparison.
