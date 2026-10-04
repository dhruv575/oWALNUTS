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


## Analysis budget supported by resource controls

The saved-data common-grid control completed 20 queries in 57.41 contained
seconds using two reference fits and both prefixes. The separate 64-fit-shaped
mixed bootstrap control completed 30,000 shared resamples and 40 parameter
callbacks in 255.74 contained seconds, with 1.54 GB peak committed memory.
That workload used deterministic copies of the two pilot fits; its statistical
output was discarded. It measures computational cost, not 64-fit diversity or
interval accuracy. Neither control establishes actual-bank grid adequacy.

Declare a separate 7,200-second analysis budget, including materialization,
admission, grid construction, bootstrap, serialization, and verification.
Keep CPU 0, 8 GiB, 64 grid queries and 32 refinement rounds, with a 15-second
cleanup reserve. Record actual overrun and leave the result unresolved if the
declared budget is exceeded. The full quadrature ladder and original endpoint
family remain unchanged. A completed resource control supports launching the
prospective experiment after integration checks; it does not guarantee that
all 64 fits will pass or that the bank will resolve its uncertainty gates.
