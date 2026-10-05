# October fixed-period validation launch

The September-selected no-flow stochastic-volatility model is being evaluated
at 32 fixed origins, every three hours from October 1 through October 4, 2026.
Each origin has paired oWALNUTS and reference fits and an exact price-only
baseline. The primary outcome is the 90% predictive interval score; smaller
is better. Coverage and width are descriptive.

The scientific protocol was frozen before historical October acquisition.
Acquisition completed with 19,382 option trades and 192 half-hour bars in
35.08 seconds. The no-flow model does not use the acquired option activity.
September and October raw records were separately verified and joined once,
preserving the boundary anchor and excluding immature training labels.

All 32 fixtures were ready. Twelve join, schedule, and reporter tests passed.
The independent audit found no causal-boundary or model-equivalence blocker.
The final configuration SHA-256 is
`dd0dbef37f8dbe57337261a4a289b1f4dac9784eea758fc4784fd982111796ad`.
The original execution handle is 70620. This archive describes the launch,
not terminal results. Mutable fit outputs are deliberately excluded.

The archive retains the protocol, configuration lineage, source archives,
and acquisition evidence. Large raw records, fixtures, and joined features
are represented by 160 external hashes; this is not a self-contained data
bundle. See `manifest.json` and `checksums.json`.

This is a fixed historical validation on four dependent days. Bar timestamps
are assumed to denote bar opens, with zero publication lag at their close.
Existing October live receipts mean the market period was not universally
unseen. Results cannot establish general calibration or live performance.
No October-dependent model, prior, feature, or stopping-rule tuning is allowed.
