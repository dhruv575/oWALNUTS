# chain_rescue_v2 — pre-evidence amendment 3

Date: 2026-09-04
Status: **frozen before any evidence run**

This narrow amendment clarifies origin-safety treatment when a process-valid
`current` or `two_hit` cell contains a restart action but the corresponding
`observe` origin assignment cannot be authenticated for that action's chain
index and initial-position hash. `PREREGISTRATION.md`, `protocol.json`,
`AMENDMENT-1.md`, and `AMENDMENT-2.md` remain unchanged. This amendment
supersedes only less-specific interpretations of unavailable origin mapping.

## Unavailable origin mapping

Each restart action is mapped independently by target, seed, chain index, and
initial-position hash. If the paired process-valid `observe` assignment is
unavailable, or if the action chain's initial-position hash does not match,
that action is classified as `origin_safety_unknown`.

`origin_safety_unknown` is not evidence that an origin was overwritten. It is
therefore distinct from `origin_overwritten`, does not force the cell's
overwrite-based credited diagnostic gate to fail, and does not itself create a
`current` no-rescue fallback red line.

For `two_hit`, any `origin_safety_unknown` action prevents the candidate from
satisfying its zero-origin safety gate. Consequently, origin uncertainty
cannot make `two_hit` the default by silence.

For the origin/telemetry cases clarified here and in Amendment 2, a `current`
red line requires either an actual mapped `origin_overwritten` action or a
run-stage sampler error with unavailable rescue telemetry. The other
independently registered current red-line classes remain unchanged.

## Pre-evidence status

This is a conservative interpretation fixed before evidence. It was not
prompted by an observed study result. No seed in the registered evidence range
92101–92112 has been launched.
