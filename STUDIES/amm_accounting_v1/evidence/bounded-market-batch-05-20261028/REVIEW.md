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
