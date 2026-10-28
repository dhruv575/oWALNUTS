# Retrospective warm-prefix budget assessment

All four fixed shifted-window traces were analyzed at nested prefixes of
64,256,1024 draws per chain. No draws were discarded or resampled. These are
dependent development assessments, not independently seeded experiments.

At 64 draws every coordinate failed at least one of the Rhat/ESS thresholds
in all four fixtures. At 256 draws the failure counts were 9,2,90,75 out of
27,27,503,503 coordinates. At 1,024 draws all coordinates passed in all four
fixtures. Do not infer full-posterior qualification from the selected CDFs:
both long fixtures' CDFs passed diagnostic thresholds at 256 draws despite
the many failed parameter coordinates.

At 1,024 draws maximum absolute CDF differences versus the saved full cold
reference were .000745,.000162,.000914,.0000132; maximum combined-MCSE
discrepancies were .637,1.274,1.687,.566. These describe three thresholds and
one shifted update only. Poor diagnostics at smaller budgets limit MCSE
interpretation; mean agreement does not rescue those failed diagnostics.

The full output archive and analysis source hash were verified after download.
Analysis took 6.459 seconds under a 120-second timeout and 4 GiB address-space
cap. Prefix sampling latency was not measured and cannot be inferred by
dividing the original run's duration proportionally.

Use 1,024 only as a candidate budget for a separately seeded repeated-update
study, with cold references at every update and all failures preserved. This
does not establish market forecasts, decision value or profitability.
