# Equal-close observation audit

The frozen 4,608-bar acquisition contains nine exactly equal adjacent closes.
Two have zero current-bar volume; seven have strictly positive current-bar
volume. All two zero-volume bars are among these nine pairs. The audit first
revalidated all three monthly panels through the original sealed data contract.
It did not acquire new observations or alter returns.

Thus an empty-interval explanation cannot account for all observed zero returns.
Positive volume does not prove a particular rounding mechanism or historical
tick size. Zero volume alone does not establish the provider's fill policy.
Neither finding licenses dropping or jittering observations.

Next: distinguish missing-interval semantics from finite price resolution, and
specify a proper observation model before resuming posterior comparisons.
A joint latent-price cell model is a candidate: integrating a normalized return
process over observed price cells yields a likelihood bounded by one. Historical
cell boundaries and the observation mechanism still need justification; this
is not yet an admitted replacement model or a predictive-moment remedy.

The first audit invocation failed before producing a report because the
acquisition binding is a dictionary, not a path. The corrected invocation uses
its `directory` field. No scientific result was produced by that failed call.
