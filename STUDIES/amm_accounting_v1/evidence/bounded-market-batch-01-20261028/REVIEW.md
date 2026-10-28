# Batch 01 preservation review

All 12 planned cells report qualification for both NUTS and WALNUTS. The archive
verifier ran on the existing EC2 instance with the pinned scientific Python
environment, checking all 24 draw sets, finite arrays, dimensions, physical joint
reconstruction, source/seed bindings and score-decomposition identities. It did
not independently recompute the reported ArviZ diagnostic estimates.

S3-VERIFIED.json identifies the exact archive version whose full download stream
matched the original SHA256 and byte count. After verification, the raw NPZ files
were individually hash-checked against FULL-MANIFEST.json and removed along with
the redundant EC2 archive; CLEANUP.json records this operation. Reports and batch
control files remain on EC2. Unlike batch 00, the full archive was not downloaded
to the local workstation; the full raw evidence is preserved in versioned S3.

The compact review copy omits large SAMPLER.json logs as well as NPZ arrays. Their
hashes remain in FULL-MANIFEST.json and their contents remain in the full archive.
No sampler or campaign configuration was changed. These are development cases;
the complete 72-cell denominator and uncertainty analysis are still required.
