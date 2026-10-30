# Passive metric audit, frozen before execution

Replay only the auto2 arm for four exposed models (earnings interaction, kidiq,
garch11 and GP Poisson) and seeds 927100001--927100003 from reconsider/run01.
Use the preserved source/harness and identical compiled target/data, initialization,
four threads/chains, 1000 warmup/1000 retained, tuning and environment.

Insert a single research-copy stderr record after fitted precision construction:
window/transition/dimension, per-coordinate force R^2, position covariance,
force-regression matrix and symmetric fitted precision. No changed return values,
branches, target calls or random draws. Build in an isolated tmpfs source copy.
Verify old source/binary against the preserved BUILD.json before copying.

Require exact equality of every per-chain JSON field, including samples, draw
hashes, diagnostics and work counters, plus total target calls and starting
states against the matching old cell. Exclude wall time and paths only. A parity
failure blocks interpretation; retain failures without replacing them. Timings
of instrumented replays are not performance evidence.

For each record, report all R^2 values, unconstrained coordinate names, fitted
precision eigenvalues and position-covariance condition number. For coordinates
with R^2>=.5, report the principal precision block's positive-definiteness and
condition number before/after diagonal normalization if dimension>=2. These
are exploratory mechanism diagnostics, not sufficient evidence for a policy.
Do not select thresholds from these replays or modify the production sampler.

Build cap300s; each run600s,2GiB sampled RSS,64MiB output; three workers with
four dedicated cores each. Admission root>=1GiB,tmpfs>=4GiB,RAM>=10GiB. Preserve
dependencies, all draws, audit records, process-drain receipts and source hashes.
