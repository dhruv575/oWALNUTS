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
