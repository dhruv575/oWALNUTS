# Fresh model screen and numerical repair

2026-10-30. Original frozen screen completed all 80 jobs. Four earnings candidate
configurations failed before sampling because NumPy inversion introduced tiny
antisymmetric roundoff rejected by DenseMass. Controls and other candidate cells
were preserved, not overwritten. Explicit separate repair symmetrizes the inverse
and requires SPD, relative pre-repair asymmetry <=1e-10 and inverse residual
<=1e-7. It reruns all 16 candidates; original controls/pilots are reused with
provenance, not independent replication. Inputs unchanged; all job groups drained.

All 16 repaired candidate cells pass frozen reference and accuracy gates. All
reference artifacts qualify. Earnings passes the small continuation gate: median
paired minimum-bulk-ESS/total-target-call ratios 13.97 versus diagonal and auto,
3.00 versus full dense. Pilot and curvature probes are included. The four dense
ratios are 3.32, 3.77, 2.67 and **0.379**: the unfavorable seed must not disappear
behind the median. Candidate rank Rhat <=1.00354, bulk ESS >=1652, tail ESS >=2001,
maximum mean discrepancy <=.024 reference SD on earnings. This warrants a
controlled follow-up, not a robustness or general usefulness claim.

Other targets do not pass the continuation gate. Kidiq's qualified median ratios
are 6.91/1.07/.966 versus diagonal/dense/auto. GARCH ratios are 1.00/.630/1.00.
GP ratios are .990 versus diagonal/auto; one dense control fails accuracy, so no
qualified dense comparison is reported. All candidate GP/GARCH cells select no
block, showing that this staged diagonal fallback can still regress relative to
stronger dense adaptation. No claim of globally safe adaptive selection follows.

The staged schedule is confounded with curvature information: compare identical
pilots/restarts with empirical covariance and diagonal masses next. The earnings
Stan source also has a direct posterior solution: Gaussian linear regression,
flat beta and sigma priors, no additional likelihood or regularization. A
conjugate/direct-draw baseline must precede any practical-application claim.
No production changes, novelty claim, deployment or trading. Goal remains active.

Original evidence: 408 members, 33,648,590 bytes, SHA256
a745dac01daf953d60b6f52f19c22516f289ffd0a8e55b6b6e066bfc5df35b13.
Repair evidence: 92 members, 7,431,762 bytes, SHA256
d976b1e58be8f642b86a0f0e4d13720751a9c2f3fac06539442cdebe81b0245a.
Repair archive references the verified parent for source executable/models and
original raw controls/pilots. The duplicate parent tar on root disk was reclaimed
only after exact-version S3 verification and local SHA match; original tmpfs tar
and durable per-job evidence remain. See archive receipts and RECLAIM audit.
