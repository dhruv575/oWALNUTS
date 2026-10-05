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

`aggregate.py --plan <scheduler-plan.json> --scores <score-files...> --output
<new-summary.json>` requires exactly one score record for every planned origin.
It rejects partial or duplicate denominators, retains each unavailable status,
and compares models only on common scored origins with identical outcomes.
Per-arm available-outcome summaries are separate from that paired comparison.
An empty scored set produces null metrics, not perfect coverage. Five tests
passed. It binds supplied score files, without independently revalidating their
producer; dependent-outcome confidence intervals are deliberately not estimated.

`provisional_score.py` accepts a later immutable receipt-prefix directory using
the same CLI arguments as `score.py`. The prefix must reach the forecast horizon,
be unclipped, and preserve the original receipt/lifecycle prefix and selection.
Three tests passed for identity, late-gap withdrawal, maturity and missing quotes.
The result has a distinct provisional schema and requires final reconciliation;
the final aggregation CLI rejects that schema. Provisional scoring never replaces
an issued interval or a previous score. A later final score is a separate record.
