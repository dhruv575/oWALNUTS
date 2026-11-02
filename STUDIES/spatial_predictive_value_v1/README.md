# Spatial predictive value study

See `../../research-ops/SPATIAL-PREDICTIVE-VALUE-20261101.md` for findings.
The frozen primary positive-value gate fails; do not report this as a verified
advantage over every cheap alternative.

`PROTOCOL.md` freezes training-reference qualification and heldout scoring.
`APPROXIMATION-FOLLOWUP.md` records a training-only numerical refinement before
opening outcomes. `AUDIT-PROTOCOL.md` preserves the original result while
checking score arithmetic and auxiliary predictive sampling variation.
`RESERVED-SPLIT-PROTOCOL.md` defines a separately labeled continuation.

Execution used `/home/ubuntu/venv/bin/python` on the existing EC2 instance.
Primary lane: `/home/ubuntu/lanes/spatial-predictive-value-20261101`.
Continuation lane: `/home/ubuntu/lanes/spatial-predictive-replication-20261101`.
The native grid backend and original posterior draws are dependencies of
`../algorithmic_speedups_v1/`, with remote paths recorded in common.py.

Order: run score arithmetic checks; freeze inputs/source; run training reference
and approximation; preserve any failure and apply only a separately frozen
training-only refinement; freeze scoring sources and heldout hash; score only
after the reference passes; run the labeled audit. `run_stage.py` applies wall,
RSS, output-size and free-disk limits. Never rerun into existing output paths.

`evidence01/scoring/SUMMARY.json` contains all scores, comparisons and numerical
failures. CELLS.json contains the complete per-cell results and heldout counts.
`evidence01/training/REFERENCE.json` contains new reference qualification;
`evidence01/audit/SUMMARY.json` contains independent arithmetic checks and
additional Poisson sampling replicates. `ARCHIVE-VERIFIED.json` records the
local evidence verification. Raw NPZs and compressed archives are intentionally
excluded from Git; they remain available locally and on AWS.

Data attribution: spatstat/spatstat.data, pinned commit
3316eca0ef691ee8717fb4421918dd95978b5560, data/bei.rda, package GPL>=2.
Original source files, documentation, provenance and the point-count discrepancy
are preserved in `../usefulness_search_v1/spatial_counts_v1/source/` and its
protocols. This historical public dataset is exposed, not blinded new data.
