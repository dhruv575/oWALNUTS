# Later metric-selection mechanism screen

Hypothesis: windows 1+2 can misrepresent settled geometry; selecting after
window 3 may improve reliability and efficiency on ill-conditioned regressions.
This is a fresh-seed mechanism screen, not a default-change confirmation.
Earlier WP85 failure remains a failure; no threshold is reinterpreted.

Compare diagonal, auto selection at window 2, and auto selection at window 3.
Keep gain threshold 5 and minimum linearity .5 unchanged. Use four chains,
1000 warmup, 1000 retained draws, three new seeds 926100001--926100003.
Targets: earnings-logearn_interaction, kidiq-kidscore_momhsiq,
garch-garch11, and gp_pois_regr-gp_pois_regr (nonlinear guard control).
36 total jobs, randomized fixed order (seed 926199999). No reruns of failures.
Bound each job to 600 seconds, 2GiB RSS and 64MiB output; at most three jobs
with four distinct cores each. Keep disk admission floor at 1GiB, use memory
workspace for builds and pending output, copy completed evidence locally.

Report all branches, R-hat, bulk/tail ESS, divergences, reference errors where
qualified, and total target calls. Compare ESS per total target call, including
warmup. No benefit claimed from branch consistency alone. A promising screen
requires no diagnostic-pass loss versus either incumbent, >=1.2 geometric mean
efficiency over the three regression/time-series targets, no target below .9,
and all GP guard runs remaining diagonal. Timing is descriptive. A passing
screen requires a separate broader frozen confirmation with fresh seeds,
qualified accuracy and uncertainty analysis before adoption.

Use existing WP85 native model binaries and data, hashing every dependency.
Build current baseline source with research features, changing only the study
harness to read the selection-window parameter. No production kernel edits.
