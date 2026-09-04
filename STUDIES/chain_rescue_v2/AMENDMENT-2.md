# chain_rescue_v2 — pre-evidence amendment 2

Date: 2026-09-04
Status: **frozen before any evidence run**

This amendment resolves three conservative analysis ambiguities found during
pre-evidence harness review. `PREREGISTRATION.md`, `protocol.json`, and
`AMENDMENT-1.md` remain unchanged. For the points below, this amendment
supersedes less-specific wording in those files.

## Nuisance action score

For one nuisance model/seed/arm, count the number of **unique chain indices**
that were restarted at least once. Multiple restart events on the same chain
count once. A complete seed block's nuisance score is the sum of those unique
chain counts over `kidiq`, `earnings`, and `diamonds`.

Every restart event and the separate event count remain reportable. This
clarification affects only the registered nuisance score and its total/ratio;
it does not change chain-rescue behavior.

## Unpaired process-valid safety and red lines

Triplet validity still controls paired efficacy scores, paired sign tests,
paired pass-count margins, no-fire identity comparisons, and efficiency
ratios. In contrast, safety and red-line observations do not disappear when a
sibling arm has a process fault.

The following checks apply to **every process-valid arm cell**, whether or not
its target/seed triplet is valid for paired analysis:

- decisive reference disagreement;
- stable-origin overwrite when the corresponding process-valid `observe`
  assignment is available and its initial-position hash maps to the arm cell;
- funnel gross red lines;
- the unknown run-error rule below.

Thus a process-valid candidate/current safety failure remains visible and
operative even if another arm invalidates paired analysis for that target and
seed.

## Sampler errors and unavailable rescue history

A child that exits successfully with an authenticated, schema-valid raw
sampler error remains process-valid and is a valid diagnostic failure.

- An **initialization-stage** error occurs before sampling and therefore has
  known zero rescue history. It does not by itself create a rescue-safety or
  rescue red-line failure. It can still invalidate pairing when four initial
  hashes are unavailable.
- A **run-stage** sampling error may lack partial rescue telemetry. Such a cell
  records `telemetry_unknown=true`; it must not be presented as having complete
  successful rescue telemetry or zero actions. Conservatively, it fails the
  `two_hit` rescue-safety gate. For `current`, it counts as an unknown
  rescue-safety red line in the frozen fallback decision. If future raw output
  durably supplies complete validated partial telemetry, that telemetry is
  reported, but a run-stage sampler error still remains a diagnostic failure.

This rule prevents missing partial telemetry from establishing safety by
silence. It does not convert the cleanly returned sampler error into a process
fault.

## Evidence status

No seed in the registered evidence range 92101–92112 has been launched. The
only executed study-related sampling remains deterministic non-evidence
conformance.
