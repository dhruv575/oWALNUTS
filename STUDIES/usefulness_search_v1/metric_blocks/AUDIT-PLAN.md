# Audit before proposing partial dense metrics

2026-10-30. No implementation or efficacy claim yet.

Current source src/walnutpie.rs computes a per-coordinate force-regression R^2
vector, then gates the entire dense metric on its minimum (around lines7539--55).
In exposed reconsider evidence, kidiq seed927100003 has gain13.93 but minimum
linearity .0647 at window2; at window3 minimum linearity is .9882 and gain174.0.
Conditional reconsideration nevertheless FAILED its frozen median-based screen.
Do not reclassify that result or repeat it with a more favorable aggregate.

Concrete question: was the early rejection driven by one nonlinear coordinate,
or was the correlated coefficient block itself poorly estimated? Existing
telemetry retains only the minimum, so it cannot answer this. Inspect the full
R^2 vector, coordinate names, fitted precision eigenvalues and covariance
conditioning before modifying any selection policy.

Next bounded action: add passive research-harness diagnostics at that decision,
replay exposed controls with unchanged random consumption/target calls, and
verify exact draw/work fingerprints against the archived runs. Include earnings,
kidiq, garch and GP count controls, all three exposed seeds. Source and evidence
must be frozen; all side effects must be logging only. No performance claim from
these exposed replays. Check source dimension/finite-value/empty-block behavior.

Only if a stable correlated subset is actually being rejected solely by another
coordinate is a block-metric hypothesis justified. A possible research policy
would freeze a positive-definite dense block for that subset and retain diagonal
mass elsewhere. The block must remain fixed during retained transitions; warmup
estimation/regularization and cross-block terms need explicit design and tests.
Compare against the existing automatic rule, full dense and diagonal controls,
not just the exposed failing seed. Any adoption requires fresh broader seeds,
qualified accuracy, total work including selection, and uncertainty analysis.
If the audit does not support the mechanism, stop this route before tuning it.

This is a proposal for evidence collection, not a claim that block selection
will improve WALNUTS or constitute a novel research contribution.
