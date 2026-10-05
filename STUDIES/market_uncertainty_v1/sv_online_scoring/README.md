# Delayed SV scoring prototype

This separate scorer never fits, changes an issued interval or deploys an issuer. It consumes `research-live-sv-issuance-v1` and requires the caller's previously pinned issuance SHA256. Hashes establish local identity, not externally certified timestamps.

For a scheduled run, use the `issuance_sha256` saved in the scheduler's event
ledger at issuance time. Do not establish a new identity from a potentially
changed issuance file when its future outcome is scored.

```
python score.py --issued-dir IMMUTABLE_ISSUANCE --capture TERMINAL_CAPTURE --issuance-sha256 PIN --output NEW_SCORE.json
```

Add `--provisional` when the later data are an immutable prefix snapshot. Provisional scores require later terminal reconciliation and may be withdrawn by subsequent gap evidence. Outputs are created exclusively; final scoring produces a separate record.

The admitted interval must equal the bound public-worker result, which must pass the complete canonical and functional health/precision gates for the fixed both-flow SV scope. Source, fixture, physical starts, origin, sampler/predictive identities, publication deadline and absent current label are checked. Unknown, late, precision-failed and insufficient-history issuance remain explicit nonscored outcomes. A caller aggregating a schedule must retain every scheduled issuance, including missing files represented as errors.

Terminal or later-prefix hashes are checked before and after scoring. Late gaps intersecting any original acknowledged coverage conservatively invalidate a forecast, including when they could retract training inputs. Current features are rebuilt and compared before using the mature 30-minute midpoint-return label. The score reports width, coverage and the proper nominal-90% interval score; none implies calibration from one or a few observations.

Eight mocked tests cover terminal/provisional scoring, wrong identity, future-label leakage, gap retraction, nonsuccess denominator, numerical gates beyond boolean claims and mutation during scoring. An integration test calls the actual issuer, snapshot and feature builders with a mock sampler, then scores a later immutable prefix and terminal capture and retracts the score after a late gap. Production hardware/config hash pairs are validated when present. No live SV issuance or actual sampler run has been deployed by this prototype.
