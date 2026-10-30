# Additional Fisher arm on broad01 pilots

Frozen before model comparisons. Reuse the 24 broad01 pilots and its previously
reported candidate/dense/auto controls; no new independent seeds or replication.
Fit the existing dense Fisher estimator using all400 pilot positions and scores,
gamma0, via the qualified80-digit implementation. Charge400 additional gradient
calls and all fitting time. Install symmetrized inverse covariance only if SPD
and ||C M-I||<=1e-7. Fit failure counts as failed arm, with no adaptive fallback.
Start from the same four pilot last states; same seed+100000,750 warmup,2000 draws.
Use all original reference/diagnostic/divergence/moment gates. Compare paired
ESS/totalcalls and total measured sampler+fit seconds only where both pass;
retain failures and do not credit infinite ratios. No success threshold converts
this supplemental screen into application evidence. This tests an existing
estimator with our staged schedule, not the full published sampler.

Each metric fit and sampling job is bounded180s/2GiB/64MiB; persist gzip evidence
and hash manifests. Record raw scores, metric, parent pilot hashes and control
archive receipts. Six models and seeds929100001..4 exactly as broad01. Subsequent
general advantage claims require fresh larger replication and stronger
model-specific controls where feasible. The expensive high-precision solver
cannot support a claim against an optimized implementation's wall time.
