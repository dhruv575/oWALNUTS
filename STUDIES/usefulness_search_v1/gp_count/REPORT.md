# GP count audit: stronger approximation succeeds

2026-10-30. This 11-observation benchmark is synthetic. The qualified reference
and conditional importance baseline agree on the 24 tested means and standard
deviations. Global Laplace and its defensive importance correction fail. These
results remove the global-approximation failure as motivation for a WALNUTS
application campaign; they establish neither decision value nor a sampler speed
ranking. The continuing usefulness goal remains active.

## Reference and global approximation

The preserved ten-chain reference qualifies after recomputing diagnostics for
rho, alpha, 11 log intensities and 11 intensities: maximum rank Rhat1.000886,
minimum bulk ESS9681, minimum tail ESS9536. This is a practical reference for
the checked functionals, not proof of complete posterior exploration.

Four-start MAP preparation costs487 gradient and260 density evaluations,0.427s
inside the worker. The selected mode passes curvature-step and gradient checks
(relative Hessian difference1.73e-7; maximum scaled gradient error1.32e-6).
All optimizer outcomes are preserved. Raw unconstrained Laplace is particularly
poor after transformation to intensity: worst mean errors5.89--21.17 reference
SD and worst relative SD errors82--2927. Its32768 iid approximation draws must
not be mistaken for qualified posterior ESS.

Four defensive global-importance replicates,32768 proposals each, all fail:
ESS2.95--91.96, Pareto k0.893--1.150, worst mean errors0.521--0.599 reference SD.
Their delta-method MCSEs are unqualified given failed weight diagnostics. One
proposal triggers a caught Stan domain exception and receives zero weight;
it is retained in the error count. No positive-weight transformations are lost.

## Conditional baseline

The stronger baseline integrates over the two log covariance parameters using
a coarse conditional-Laplace grid, mixed with the full-support hyperprior.
At each proposal it solves the concave latent conditional problem and samples
a Gaussian/Student mixture. Exact full-target importance weights correct both
approximations. This uses established Laplace marginalization ideas, not a new
sampler or a claim to reproduce a complete INLA implementation; see
[Rasmussen and Williams, section3.4.4](https://gaussianprocess.org/gpml/chapters/RW3.pdf).
The exact procedure, normalized mixture densities and gates are frozen in
CONDITIONAL-PROTOCOL.md.

| Seed | Importance ESS /16384 | Pareto k | Max mean error / reference SD | Max relative SD error | Max combined-MCSE discrepancy |
|---|---:|---:|---:|---:|---:|
| 944100001 | 13356.9 | .146 | .0283 | .0169 | 2.149 |
| 944100002 | 13343.7 | .107 | .0309 | .0214 | 2.348 |
| 944100003 | 13333.2 | .127 | .0296 | .0208 | 2.235 |
| 944100004 | 13280.8 | .082 | .0147 | .0158 | 1.105 |

All four pass every frozen gate. There are no exact-target callback errors in
these runs. Setup/preflight takes0.825s and19371 backend factor evaluations;
each production replicate takes9.76--9.89s,16384 exact density evaluations,
180224 factor evaluations, and roughly294000 conditional objective evaluations.
Those costs must all be charged; do not report only exact density calls. The
factor extraction deliberately uses the same compiled numerical factor as the
target. It is not an optimized or precision-matched timing comparison with
WALNUTS/NUTS. Reference construction, software compilation and diagnostic costs
also differ from a deployed inference workflow.

The unweighted defensive proposal is not itself a pure conditional-Laplace
posterior; its raw means are saved for inspection only. The pass applies to
importance-corrected estimates of these24 quantities, not arbitrary tails,
out-of-sample predictions, or all latent-Gaussian models. Four replicates are
limited evidence. No posterior reference is used to fit the proposal.

## Failures and reproducibility

The first launch failed because a provenance helper named inspect.py shadowed
Python's inspect module; it was renamed before inference. The first conditional
preflight stalled from subtracting nearly equal objective values. A stable
objective-difference formula fixed that without changing convergence tolerance.
The next preflight found a1.42e-5 NumPy/Stan density discrepancy from differently
rounded, ill-conditioned covariance factors. Extracting the factor from the
actual target reduced offset spread to1.19e-12 and passed the unchanged1e-6
gate. The final latent-gradient discrepancy is3.71e-8 and proposal-density
error5.32e-12. All failures, audits and source versions remain in the archive;
see AMENDMENTS.md. No production draws existed before those repairs.

Eight production jobs completed with drained process groups, unchanged frozen
inputs and peak RSS below373MB. The initial summary assigned shared global
replicate call counts to both arms; SUMMARY-v2.json correctly attributes density
calls to importance only. Raw results and scientific gates are unchanged.
Preparation supervisors scan their log directories; their separately written
small artifacts are included in the final archive. Production output supervision
covers the entire job directory; RSS/output limits are sampled, not hard quotas.

The private archive contains model/data/source, reference draws, installed
BridgeStan modules, package versions, raw weighted/unweighted samples, all
failures and monitors. See archive/S3-VERIFICATION.json for exact-version restore
verification. Originals remain remotely; the instance remains running.

Next research action: audit existing sampler work counters and failed metric
selection evidence for a concrete preventable algorithm mechanism. Do not
promote a negligible micro-optimization, rebrand a strong baseline as WALNUTS,
or launch a large real-data GP campaign from this synthetic result.
