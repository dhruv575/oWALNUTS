# Batch 05 preservation review

All 12 planned cells report qualification for both samplers. The verifier ran
on EC2 using the pinned scientific Python environment and checked all 24 draw
sets, finite arrays, dimensions, physical joint reconstruction, source/seed
bindings and score identities. Diagnostic estimates remain worker reports,
not independently recomputed ArviZ estimates.

The full archive is preserved in the exact version recorded in S3-VERIFIED.json;
a full download stream matched its SHA256 and byte count. The compact local
copy omits NPZ arrays and large SAMPLER.json logs, whose hashes and full archived
contents remain available. This batch's raw EC2 files and archive have not yet
been reclaimed. COMPLETION.json records all 72 reports and 144 qualified fits.

Follow-up diagnostic audit: all 24 final-batch fits reproduced R-hat, bulk ESS
and tail ESS exactly through explicit ArviZ APIs; maximum scaled MCSE difference
was 3.54e-14. The separately implemented physical beta reconstruction differed
from archived beta by at most 1.52e-18. Exact rank reproduction uses archived beta
after this agreement check, since alternate floating-point arithmetic changed
one beta R-hat by approximately 1e-7 in an initial audit attempt. The first attempt
also exposed an ArviZ one-element-array conversion issue, corrected in the audit
code. Neither audit issue changed original data or qualification thresholds.
This is a final-batch recomputation using the same statistical library, not an
independent diagnostic estimator or an audit of all six batches.
