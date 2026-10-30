# Operations log

2026-10-29: three final backend tests passed in 44.566 seconds. Original public
source snapshots intentionally retain upstream whitespace and exact byte hashes.

Initial launch `initial01` was stopped after detecting a relative output-path
bug: workers changed directory to `source`, so results landed under
`source/initial01` while resource scans watched root `initial01`. Supervisor PID
375523 was stopped from admitting work, its children terminated, then supervisor
terminated. Preserve both folders, exclude this administrative attempt from
scientific results. Fix resolves output root to absolute before creating jobs.
No tuning decisions or scientific outcomes were taken from the aborted attempt.
Replacement `initial02` uses the same frozen seeds and protocol.

Original initial02 completed 53/53 in 887.95 seconds: 21 complete, 32 failed
with nonfinite log predictions, unchanged source hashes and all groups drained.
These forecast-failed workers did not save parameter draws before failure;
the limitation is preserved, and the corrected worker saves parameters first.
The complete legacy archive verifies 314 members and its initial02 source
freeze. initial01's known post-abort supervisor change is recorded separately.

Log-state forecast repair passed four numerical/backend tests in 43.592 seconds,
including independent predictions and likelihood/gradient equality to the old
binary. Do not relax tests: an initial repaired-solver test missed tolerance
by 1.69e-6 and was corrected by tightening forecast-only tolerance to 1e-10.
The separate root `pharma-ode-logforecast-20261029` reruns all jobs. The workflow
hash-freezes selection before launching fresh validation. Remote originals stay.
