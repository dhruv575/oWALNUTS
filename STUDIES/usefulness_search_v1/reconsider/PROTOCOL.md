# Conditional metric reconsideration

Research-only candidate: Hessian selection at window 2; if dense, preserve that
handoff exactly; if diagonal, reconsider at window 3 using the independent fit
over windows 2+3. Both observers collect existing positions/gradients without
new target evaluations or random draws. No retained draw affects selection.
Default configuration remains unchanged. Gain threshold 5, linearity .5.

Before evidence: existing metric selection and fingerprint tests; new tests
for early-dense and final-diagonal exact draws/work, serial/parallel agreement,
and invalid configuration. Also replay an exposed kidiq case solely to verify
the late-dense path matches unconditional window 3; exclude it from evidence.

Fresh screen: earnings-logearn_interaction, kidiq-kidscore_momhsiq, garch-garch11,
gp_pois_regr-gp_pois_regr; three arms diag, auto2, reconsider; seeds
927100001--927100003; shuffle seed 927199999. Four chains, 1000 warmup and 1000
retained draws. 36 bounded jobs: 600 seconds, 2GiB RSS, 64MiB sampled output cap,
three simultaneous jobs on disjoint groups of four cores. Disk floor 1GiB;
memory-backed build/output, preserve complete source and evidence off-instance.

Gates: no per-model diagnostic-pass loss versus either incumbent; R-hat<=1.01,
bulk/tail ESS>=400, zero retained divergences, finite draws, correct process and
decision provenance. Compare per-seed minimum bulk ESS / total target calls
(including warmup); per-model median paired ratios, then geometric mean over
the three non-GP targets. Require >=1.2 versus both incumbents, no model <.9,
all GP candidates diagonal. Early dense candidate paths must exactly match
auto2 draws and work; final diagonal paths must match diag draws and work.
Report reference discrepancy with combined MCSE, reference diagnostics, all
failures and branch choices. Timing descriptive. No wins from choosing draws
post hoc. A pass only motivates broader fresh confirmation and does not meet
the overall goal or authorize a default change.
