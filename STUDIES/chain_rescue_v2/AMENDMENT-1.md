# chain_rescue_v2 — pre-evidence amendment 1

Date: 2026-09-04  
Status: **frozen before harness implementation or any evidence run**

This amendment corrects one source-selection tie rule in
`PREREGISTRATION.md` and `protocol.json`. Those frozen files remain unchanged;
for this point, this amendment supersedes their statement that an exact final
tie chooses the lower chain index.

## Discovery

Review after core candidate commit `6de4a41`, and before any study harness or
evidence execution, found that the source rule recorded in preregistration did
not exactly describe parent commit `17f1d97`. The parent implementation
iterates candidate chains in ascending index order and uses
`Iterator::max_by` with comparisons by:

1. larger post-boundary step;
2. larger median window log density.

When both comparisons are exactly equal, Rust's `Iterator::max_by` returns the
last equal maximum. The established immediate `restart_from_best` behavior
therefore chooses the **higher chain index**, not the lower index stated in the
frozen preregistration.

The initial candidate implementation added an explicit lower-index
tiebreaker. That changed an existing current/default edge case and is not
permitted by the requirement that the explicit `current` arm preserve parent
behavior.

## Amended rule

For `observe`, explicit immediate `current`, and `two_hit`, the deterministic
source is the non-outlier chain with:

1. the largest post-boundary step;
2. then the larger median window log density;
3. then, only when both values tie exactly, the **higher chain index**.

All three arms use this same rule. The source is still recomputed at every
eligible boundary, including the action boundary for `two_hit`.

No threshold, hit criterion, eligibility rule, source-position distribution,
state transfer, target, seed, gate, or decision rule changes. The implementation
must be corrected and covered by an exact-tie regression test before any
evidence run.

## Evidence status

No study harness has been built, none of seeds 92101–92112 has been run, and no
evidence has been observed. This is therefore a pre-evidence protocol
correction, not a result-driven change.
