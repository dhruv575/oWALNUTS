# Resident predictive harness: development only

This isolated harness uses public Python WarmSession APIs, a GIL-free SV target,
and joint four-field functionals. No kernel change and no qualification study.
WP96 priors/rho/nu and the zero-filled stationary-boundary remap are explicit.
Its tiny N12 smoke uses a new development initialization and the public session
seed schedule, so it is not a reproduction of WP96 trajectories.

The target compiles once and reads each immutable window through user_data. The
TargetOwner keeps the window and callback alive; retarget is synchronous between
refreshes. Do not mutate buffers while native workers are running.

Per-tick wall time includes window construction, target ownership, remap, retarget,
K transitions, compact transport, scale inversion and checked GH64/128 return
inversion. Imports/JIT/initial fit are separate; JSON persistence is outside the
tick timer. A 30-second numerical deadline and native evaluation cap bound smoke
work but are not a hard whole-process watchdog. Failures stop the smoke; no quote
is authorized. No memory-performance claim is made without a native RSS monitor.

Implementation must be committed before measured smoke. Run tests with the Python
environment that provides owalnuts, NumPy, SciPy and numba:

    python -m unittest discover -s STUDIES/resident_predictive_harness_v1 -p test_harness.py
    python STUDIES/resident_predictive_harness_v1/harness.py --out NEW_OUTPUT_DIRECTORY

Smoke is four updates, including the first three observations after an artificial
scale change at update2. It is an implementation exercise, not a posterior or
forecast accuracy assessment. Record native .pyd hashes and runtime package/source
provenance; the installed extension is not assumed to match current source.
Independent reference target: STUDIES/online_sv_quote_v2/models/sv.stan, with
n/y/rho=.95/nu=5/mu_mean=2log(.005)/mu_sd=1/log_sigma_mean=log(.2)/
log_sigma_sd=.5/beta_sd=.002. Tests compare independent density/finite differences,
window preservation, native compact output parity and independent quadrature.

Development smoke01 is preserved: admission rejected the first refresh because
the kernel's theoretical worst-case target bound exceeded two million evaluations.
No predictive result was produced. The corrected development harness disables
worst-case admission while preserving the same actual two-million evaluation
limit; this is an admission setting change, not a higher compute budget. Smoke02
uses the identical seeds/data and is a debugging rerun, not fresh evidence.

Smoke02 also failed before sampling: the actual API always admits against an
explicit evaluation cap. Disabling admit_worst_case does not bypass that check.
Smoke03 changes the development tree-depth cap from8 to3, retaining the same
two-million evaluation cap and data/seeds. This is a changed development sampler,
not a practical accuracy candidate. Structured diagnostics and native process
memory are now recorded; callback keep_alive retains (compiled,array) without a
self-cycle. The first two failure records remain unchanged.

Smoke03 completed all four updates. Direct complete tick times were 130.13,
111.11, 142.96 and155.28ms; N12/K8/depth3 means these are not N250/K400
feasibility or accuracy evidence. GH64/128 checks passed and structured diagnostic
arrays, effective per-chain seeds, target calls and work counters are preserved.
Actual child Python peak working set was150,917,120 bytes; peak commitment
1,146,896,384 bytes. These are process measurements, not quadrature-cache size.

Installed native SHA256 was
6f06427db8c968164e0a38cd4f25d5892fa53a422b34f4f79c6831447a81fd85.
The development smoke used max_depth3 and the installed default refinement cap8.
An immediate post-smoke defaults snapshot is preserved separately without editing
the run output. Current code explicitly pins refinement cap8 and records the full
runtime Tuning/default map; that reporting-only update has not been smoke-rerun.
All five focused tests passed before smoke03. No Linux timing or independent
posterior reference fit was launched. K400 from the separate precision diagnostic
is a possible future candidate, not a qualification result or a return-accuracy
conclusion.
