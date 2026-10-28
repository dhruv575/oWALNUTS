# Batch 00 preservation review

All 12 fixed cells produced both NUTS and WALNUTS reports. Local verification
checked all 24 retained draw sets, finite arrays, expected dimensions, physical
joint-draw reconstruction, frozen plan/seed bindings, process drain records and
the model/inference/total score decomposition. Diagnostic estimates are preserved
worker reports; this verification did not independently recompute ArviZ estimates.

The full 971,800,969-byte archive remains in local target storage and in the
exact S3 version recorded in S3-VERIFIED.json. That version was fully streamed
back through SHA256 on EC2. CLEANUP.json records the hash-checked raw files and
redundant EC2 archive reclaimed after these checks. Reports and campaign control
records remain on EC2. No active dependencies were removed.

The initial Windows verification attempt stopped on a backslash/forward-slash
lookup mismatch. Canonical POSIX manifest keys fixed the verifier; the complete
archive then passed. No experiment data or frozen campaign source was changed.

This is partial development-set evidence from a 72-cell study, not an independent
holdout result or evidence of profitability. Predictive comparisons require the
full planned denominator and uncertainty review.
