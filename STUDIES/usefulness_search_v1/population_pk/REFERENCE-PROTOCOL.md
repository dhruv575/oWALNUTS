# Analytic population posterior and predictive screen

Frozen before execution; exploratory application evidence, not clinical validation.
Target: the same 43-parameter linear hierarchical Theoph posterior, evaluated
with the audited stable closed-form gradient. Earlier target already used the
closed-form curve via Stan autodiff; this is an implementation change.

Two fresh seeds per arm: PyMC NUTS + exchanges (935100001/2), WALNUTS + exchanges
(935200001/2), and native nutpie NUTS initialized around the primary mode
(935300001/2). Four chains, 1000 burn-in and 4000 retained local transitions.
Exchange arms use the archived mixed-mode starts, fixed .05 step, identity
metric in primary Hessian coordinates, depth 12; exchange every 25 local draws
(global then independent uniform subject). Retain every local state, replacing
chunk's last state with the post-exchange state. All phases individually preserve
the target; record diagnostics by burn/retained phase and charge jump calls.
PyMC Emax=1000; WALNUTS max_error=1. Native NUTS uses ordinary 1000-step adaptation,
target_accept=.99, depth 12; starting around primary mode is explicitly a
conditional-mode baseline, not proof that other modes have negligible mass.

Bound each job to 900 seconds, 2 GiB RSS and 64 MiB output. Four concurrent jobs
on separate cores, one BLAS/engine thread per job; preserve all failures. Admission
requires 1 GiB root and 4 GiB tmpfs headroom. Randomize job ordering once.

Reference gate: both independent PyMC-exchange runs have zero retained divergences,
zero depth hits, no retained evaluation errors, all-parameter R-hat <=1.01,
bulk ESS >=400 and tail ESS >=200. Require the same checks for 24 withheld-time
log-concentration predictions, sigma, and primary rate-order indicator when
nonconstant. Compare independent-run means using their MCSEs; report all
standardized differences and require max <=4.5 for 68 continuous functionals.
A constant mode indicator is explicitly unresolved, not assigned infinite ESS.
Passing these gates supports a practical sampling reference but not a rigorous
bound on unvisited mode mass. Report this limitation throughout.

Only after reference qualification compare posterior summaries and predictions
for WALNUTS, native NUTS, MAP and the primary-Hessian Gaussian approximation.
The 24 held-out measurements were previously exposed during model preflight;
any score comparison is exploratory. Use per-subject predictive log scores and
paired subject-level uncertainty; no observation-independent confidence claims.
If an inexpensive approximation is adequate, deprioritize this application.
Python-vs-native timing is not a sampler-efficiency comparison. Neither target
speedup nor escaping a tiny starting mode alone satisfies the research goal.
