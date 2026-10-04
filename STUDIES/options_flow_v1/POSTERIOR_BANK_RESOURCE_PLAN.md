# Independent posterior bank: resource planning decision

This is a prospective implementation decision, not a frozen executable plan or
a completed accuracy study. The intended bank has 32 fresh independent fits per
backend on the existing T1000/G4 posterior. All 64 outcomes remain in the
denominator. Pilot and recovery draws are excluded through their pinned stream
inventory, even if output IDs are renamed.

Retain four chains, 1,000 warmup, exactly 8,000 retained draws and the exact
4,000-draw prefix. Use the same public mixed-coordinate block-32 workflow and
associative mixed-coordinate NumPyro reference. Full health and precision checks
remain on all 1,012 coordinates, 14 physical functionals and four forecasts.
The 12-endpoint accuracy family does not narrow those checks.

Plan a six-hour fitting and compact-output phase, including per-fit extraction,
diagnostics, existing predictive quantiles and bookkeeping, with 1,800 seconds
per fit, CPU 0, 8 GiB process committed memory, and a 15-second cleanup reserve.
Public pilot attempts plus recovery cost approximately 216–224 seconds; full
reference workflows cost 268–282 seconds. Around 250 seconds per fit implies
roughly 4.4 hours for 64 fits before variability. Six hours is a prospective cap,
not a guarantee of completion. Preserve budget-exhausted and failed outcomes;
do not replace them to obtain 64 successes.

Common-grid predictive caching and joint bootstrap are a separate measured
phase. Its numerical contract checks the actual frozen bootstrap multiplicities
and pooled/backend/prefix point distributions without redrawing weights during
refinement. A query or time cap leaves unresolved results. Estimated quadrature
differences remain estimates, not certified envelopes. A complete executable
bank plan requires a successful resource/adequacy review of the saved-data grid
probe and a declared analysis budget; no eight-hour end-to-end claim is implied.

The bank must report achieved uncertainty, backend differences and paired-prefix
stability, with one shared reference perturbation across candidate comparisons.
Agreement and healthy diagnostics corroborate an approximate reference; they do
not establish exact truth, absence of common bias or calibrated market forecasts.
This resource plan does not weaken the original demanding uncertainty goal.
