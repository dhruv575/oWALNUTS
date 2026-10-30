# Native NUTS recycling control: source audit and qualification

Frozen before implementation execution, 2026-10-30. Use the preserved, checksum-verified nuts-rs 0.18.3 crate corresponding to nutpie 0.16.11's published lockfile. This source correspondence does not prove binary identity to the installed Python wheel. Build pristine and instrumented Rust controls with identical dependency lock and installed Rust stable 1.99.1; do not compare their timing against WALNUTS built with a different compiler as a final performance result.

## Selection and stopping audit

In src/nuts.rs::merge_into, an inner tree uses p=exp(other.log_size-logaddexp(self.log_size,other.log_size)); a main tree uses p=min(1,exp(other.log_size-self.log_size)). The original short circuit skips random_bool when p>=1. Preserve that exact expression and RNG behavior. Extend constructs a subtree independently of its randomly chosen candidate. A turning/diverging recursive extension is discarded by its parent, while a successfully built equal-depth subtree is merged before reporting an outer turn. Carry conditional observable means through precisely these accepted merges; failed extensions contribute nothing to the parent. Include the initial state and record the final tree at every successful draw return path.

State::write_position delegates to Point::position, and TransformedPoint::position returns untransformed_position, the same coordinates returned by Chain::draw. Evaluate observables there using CpuMath's slice copy, not transformed_position. No extra logp/gradient evaluations or random calls. Diagonal and low-rank adaptation are both covered by preflight; no other backend/flow/kinetic policy is claimed.

The conditional-expectation reasoning is the same as the WALNUTS observer audit, applied to native NUTS's actual law. This relies on native transition invariance, does not independently prove it, and does not guarantee lower long-run MSE. Recycling is established prior work, not a new contribution by itself.

## Qualification

Three analytic targets (rotated Gaussian covariance [[2,1],[1,2]], noncentered Gaussian with variances 9,1,...,1, and centered funnel with omega SD 3), both diagonal and low-rank adaptation. Four chains, 1,000 warmup plus 4,000 retained draws, no step jitter, all other native adaptation defaults. Fresh chain seeds 941500001 + 100*target_index + chain_index; starts zero except first coordinate -3,-1,1,3. Compare pristine, modified-observation-disabled and modified-observation-enabled runs. Require exact warmup/retained draws, progress records (steps, divergences, tuning and step sizes) and actual target-call counts. One finite observable vector per warmup/retained transition; functions are coordinates, squares, indicators below zero and below -2.

Known-truth Gaussian controls must have raw Rhat <=1.01, bulk/tail ESS >=400 and zero retained divergences; conditional means within .05 marginal SD, second moments within 5%, probabilities within .01. Centered funnel is a stop/divergence-path parity control, not a claimed qualified posterior. Check probability bounds and conditional second-moment Jensen inequality. Test the merge probability identities, including p=0/1, and target gradients. Keep all failures. No comparative efficacy study until the baseline is qualified.

Builds are bounded at 300 seconds/4 GiB, dependency fetch separately at 180 seconds/2 GiB. Sampling workers: 180 seconds/2 GiB/64 MiB, serial, 1-GiB free-disk floor. Preserve complete source/dependency hashes, compiler version, binaries, failed attempts and verified local archive. No paid cloud, deployment or trading.
