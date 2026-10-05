# Immutable, provisional live prefix

This utility reads an active collector directory and writes only to a **new directory outside it**. It captures fixed file-size boundaries, copies complete newline-terminated JSONL records only, and rehashes the copied source prefixes before sealing. Appends are allowed; truncation or mutation of captured bytes is rejected. The per-file read cap defaults to 50MB; receipt clipping is explicit, while clipping lifecycle evidence fails closed. It never writes or invents a terminal collector summary.

`prefix-summary.json` explicitly has status `prefix_snapshot_not_terminal`, a last-complete-receipt UTC/monotonic cutoff, receipt and lifecycle prefix hashes, exact snapshot-source hash/copy, and reconstructed acknowledged coverage/gaps. It is compatible with the feature builder's `--collector-summary` input. Connection changes create conservative gaps; recorded late gap notices retract known coverage from their recorded start. Live mode includes all lifecycle events captured at snapshot time, even a late notice after the final receipt. Thus the data cutoff and snapshot knowledge time are separate. Explicit `--cutoff-ns` filters both streams for historical as-of replay.

Provisional coverage is not exchange completeness. A later disconnect notice can identify an earlier gap. Before treating results as final, call `reconcile(prefix_summary, final_summary)`: it verifies the actual terminal stream starts with the exact captured bytes and reports final gaps intersecting provisional known coverage. Such gaps require feature rebuilding, not silent reuse of earlier known-zero flow. Reconciliation is bounded prefix-only verification, not a full terminal stream hash audit.

```powershell
python STUDIES/market_uncertainty_v1/live_snapshot/snapshot.py --capture target/market-receipt-route-v2/exploratory-48h-v1 --out NEW-PREFIX-DIRECTORY --max-bytes 5000000
python -m pytest STUDIES/market_uncertainty_v1/live_snapshot/test_snapshot.py -q
```

Five focused tests passed: partial final line, append during capture, explicit-cutoff future invariance, conservative late/open gap handling, exact source snapshot, final late-gap reconciliation, and byte-cap behavior. The first actual read-only snapshot `live-prefix-v1` copied 354 complete receipt records / 300,766 bytes, one acknowledged connection, no recorded gaps, and was not cap-clipped. It is only a few minutes of capture, not sufficient for the default 30-minute target or 20-label fitting requirement. The active capture was never modified.

Forecasting historical origins from a snapshot is an as-of replay, not evidence
that a forecast was issued at those historical times. Online issuance must retain
its actual UTC/monotonic issuance time, reject already-mature targets and report
cutoff-to-issuance latency. A byte-cap-clipped prefix may be old and must not
masquerade as current data. Preserve originally issued forecasts when later gap
evidence invalidates their inputs; mark them and save any rebuilt results
separately rather than rewriting the historical forecast record.
