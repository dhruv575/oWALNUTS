# Independent rescaled-coordinate control: failed qualification

All twelve fixed chains completed, but every cap failed fourteen of fifteen
physical-coordinate diagnostics: mu, beta and all twelve z coordinates. Only
log_sigma passed. The frozen reparameterized NUTS traces passed all coordinates.
Maximum absolute mean discrepancies were 3.153, 2.081 and 7.735 combined MCSEs
at caps .5/1/2. Cap 2 flagged log_sigma,z[0],z[10] above four. Poor mixing prevents
treating these discrepancies as calibrated tests or these chains as references.

The supervised campaign took 5.672 seconds, peak RSS 737,878,016 bytes and output
7,183,539 bytes. All groups drained and source hashes stayed unchanged. The
7,054,399-byte archive matched its remote SHA256; all source and comparison-input
bindings, all twelve array shapes and finiteness were verified locally. Full
small warmup/draw/work arrays are included in this Git evidence directory.
FULL-MANIFEST.json describes the frozen NUTS reference archive; the current
archive's inventory is ARCHIVE-MANIFEST.json, avoiding ambiguity between them.

No failed chain was replaced or given more iterations. The original zero-centered
Gaussian reference may still cause slow exploration of the highly shifted
posterior. A separately declared follow-up can test an analytically chosen
Gaussian reference center, with the exact normal-density ratio in the residual.
The target must stay unchanged. This is a hypothesis, not a guarantee of success.
The NUTS stress result remains independently unconfirmed.
