# Fixed blocked-core revision

V2 completed but failed core-coordinate diagnostics in all four fixtures. At
T250 width .001, log_sigma bulk ESS was 15.99 and Rhat 1.221; this is a mixing
failure, even though its mean was close to NUTS. Preserve V2 without extension.

V3 uses three separate scalar elliptical updates for standardized mu,
log_sigma and beta, followed by contiguous innovation blocks of at most 16.
Each block keeps other coordinates fixed and uses the whole conditional return
likelihood. Independent standard-normal priors make each block's conditional
prior exactly standard normal. Composition preserves the same target; it is
not assumed to mix well. Conditional price sweeps retain the V2 cell envelope.

Use the same four fixtures, sixteen chains, initialization, 1,000 warmup and
4,000 retained sweeps, per-update caps, diagnostics and resource limits as V2.
Fresh seeds 398128000 through 398128015 require inventory audit. No extensions
on failure. The added likelihood work is charged; no cost-matched efficiency
claim is intended. Unit checks verify that updates preserve non-block state
and reject malformed blocks, alongside existing target-identity checks.
