# Fixed proposal bank: mechanism repaired, cheap control wins

2026-10-30. Correctness checks and the frozen oracle-bank mechanism gate pass.
This does **not** satisfy the usefulness goal: discovery was bypassed, and
importance sampling is substantially cheaper on the tested synthetic targets.
No production sampler/default changes, application or novelty claim.

The fixed proposal retains components after the last walker leaves a region.
Its full-mixture Hastings correction passes SciPy density parity (max error
1.42e-14), accepted-flux parity (7.11e-15), and exact-start one-sweep stationarity
on 12000 independent four-walker replicates (max absolute z 1.35). These are
limited implementation checks. The proof and frozen protocol are in PROTOCOL.md.

All 128 fresh jobs completed in 17.68s after validation, with inputs unchanged,
process groups drained, and zero callback errors/divergences/depth stops.
Sixteen independent replicates per dimension and arm start in the broad region.
Oracle centers supply both regions; equal bank weights and identity factors
do not supply the true weights or narrow-region scale. Probability truth is
0.2000253. Standard errors/RMSE below use whole-run replicate estimates.

| Dimension | Method | Estimated positive probability (SE) | Probability RMSE | Mean target calls |
|---|---|---:|---:|---:|
| 1 | WALNUTS local | 0 (0) | .2000 | 138061 |
| 1 | WALNUTS + fixed bank | .1928 (.00821) | .0326 | 114943 |
| 1 | Bank-only independence MH | .1977 (.00761) | .0296 | 800 |
| 1 | Bank importance sampling | .2000 (.00500) | .0194 | 800 |
| 8 | WALNUTS local | 0 (0) | .2000 | 159464 |
| 8 | WALNUTS + fixed bank | .1986 (.01019) | .0395 | 154038 |
| 8 | Bank-only independence MH | .2203 (.01031) | .0448 | 800 |
| 8 | Bank importance sampling | .2049 (.00535) | .0213 | 800 |

Augmentation passes both prespecified probability gates and removes the earlier
occupancy restriction in this limited example. However, importance sampling
uses roughly 144--193 times fewer target evaluations than augmented WALNUTS
and has lower empirical probability and first-coordinate mean RMSE. This is
not universal dominance: some second-moment/other-coordinate errors are smaller
with local MCMC. All functionals and observed uncertainty are retained in
analysis01/SUMMARY.json. Only 16 replicates and one target family are studied.
Importance effective sample sizes have medians 322 (d1) and 154 (d8), with
minimum 296 and 51 respectively; these are diagnostics, not accuracy proofs.

Thus the example supports the proposed mechanism but gives no reason to prefer
WALNUTS to a cheap corrected approximation. A NUTS comparison cannot rescue
that absent computational justification; no NUTS superiority/inferiority claim
is made. Costed discovery remains untested, and this oracle result must not be
reported as successful mode discovery. Do not scale this synthetic campaign.

Raw samples/weights, all jobs, installed sampler modules, package versions,
source hashes and monitor are preserved in the private archive. Exact-version
restore receipt is archive/S3-VERIFICATION.json; remote originals retained.
Validation output supervision covers its log; its small JSON is separately
archived. Experiment output caps include the full job directories. RSS/output
limits are sampled, not hard quotas. Root free ~1.2GiB; work stays in tmpfs.

Next: return to the previously identified latent-GP count candidate and inspect
data provenance and failed functional diagnostics before proposing a batch.
Compare against appropriate latent-Gaussian methods and tuned NUTS if warranted.
Do not assume a synthetic benchmark is an actual application or omit cheap
approximations. Fixed banks remain research tooling for a future case where
independent importance correction demonstrably fails; no broad discovery study
is justified solely by this oracle result. Goal remains active.
