# Local fresh scale-correction validation

Frozen before execution. Inherit every algorithm, model, accuracy threshold,
six-arm schedule, continuation criterion and bootstrap procedure from
SCALED-VALIDATION.md, with the following explicit environment substitutions.

Use new seeds 929600001 through 929600016 in eight two-seed chunks. Reserve all
929500001 through 929500016 cloud seeds; the interrupted cloud study contributes
no observations. Bootstrap seed remains 929599999. Do not pool cloud and local
observations or timing. Local Ubuntu WSL Python 3.14 uses verified archived Linux
models and sampler, with pinned scientific dependencies and Intel TBB runtime.
The exposed compatibility preflight passed analytic density/gradient checks,
exact non-timing pilot/stage replay, and original reference accuracy gates.

One worker at a time, four sampler chains, BLAS/OMP/MKL threads one. Retain
180-second, 2-GiB RSS, 64-MiB full-job-output caps and 1-GiB free-space floor.
All raw output and separate compressed durable copies remain on local disk.
Before admitting each next chunk, audit the completed chunk and create a local
manifest archive, then read it back and verify every member. No S3 writes or
cloud compute are needed. This replaces the cloud exact-version archive step
while the AWS budget stop is in effect. Preserve failures; no threshold tuning.

Report all six models, old-hybrid contrasts, unsuccessful gates and operational
timings with their measured scope. Passing is evidence for further research,
not proof of application value, uniqueness, or a submission-ready contribution.
