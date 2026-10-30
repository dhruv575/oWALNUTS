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
