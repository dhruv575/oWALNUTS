# Delayed scoring of immutable forecasts

After the capture terminates, score one actual issuance record:

```powershell
target/python-workflow-env/Scripts/python.exe STUDIES/market_uncertainty_v1/delayed_scoring/score.py --issued-dir <issuance-directory> --capture <terminal-capture-directory> --output <new-score.json>
```

The scorer binds the original issuance, receipt snapshot, as-of features and
terminal capture by hashes, checks issuance clocks, and reconciles late gap
notices. It never refits or replaces an interval. A gap retracting provisional
coverage invalidates the forecast conservatively, including gaps in its training
history. Missing future quotes remain unavailable outcomes. Nonissuance and
insufficient-history records remain in the output denominator.

For each available 90% posterior predictive interval it reports coverage, width,
and the proper interval score (width plus a 20-times miss-distance penalty).
These per-origin scores do not establish calibration or an independent-binomial
confidence interval for dependent market observations. Aggregate only against
the complete scheduled-origin ledger, retaining missing and unissued statuses.
Local hashes and clock records do not certify external publication time.

Eight synthetic tests passed, including tampered receipts, late-gap withdrawal,
missing future quotes, inconsistent statuses, current-label leakage, exact score
boundaries, and preservation of original issuance records. No live market
forecast has yet been scored by this component.
