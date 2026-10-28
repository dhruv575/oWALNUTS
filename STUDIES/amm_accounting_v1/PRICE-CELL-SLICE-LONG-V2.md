# Cell-envelope revision, fixed independent panel

The first long-window panel failed in 15/16 chains at the conditional rejection
cap. Its sources and evidence remain immutable. This revision changes only the
rejection envelope: each neighboring Student-t factor is bounded by its maximum
over the actual cell, obtained by clamping its modal price to the cell interval.
The product of individual maxima bounds their product pointwise. Dividing by
this constant leaves the normalized conditional target unchanged. The maxima
need not occur at the same point for the product bound to be valid.

Deterministic tests cover all neighbor positions, narrow cells far from both
modes, pointwise domination and unchanged conditional density ratios. A positive
log acceptance ratio above 1e-10 aborts as an envelope violation; smaller positive
roundoff is clipped to zero. Attempt caps and abort semantics are unchanged.

Repeat the same four fixtures and sixteen-chain design with fresh seeds
398127000 through 398127015, subject to inventory audit. All other warmup,
retained draws, initialization, resource limits and comparison rules in
PRICE-CELL-SLICE-LONG-PLAN.md remain fixed. This is a new run, not continuation
or replacement of the failed chains. Do not pool either run to conceal failure.
