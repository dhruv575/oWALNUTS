# Retrospective pooled option-flow acquisition

Draft only; no bulk requests have run. The eight-request capability probe is separate and preserved at `target/market-history-capability-v1`.

```
target/python-workflow-env/Scripts/python.exe target/market-history-acquisition-v1/collector.py --protocol target/market-history-acquisition-v1/protocol-draft.json --out target/market-history-acquisition-v1/september-development-v1
```

The fixed interval is September 1 through September 30, 2026 UTC. This is retrospective development data, not unseen qualification. All returned BTC option prints are retained, including any combo/block metadata; amount is raw option quantity, not delta-adjusted exposure. The target is BTC-PERPETUAL traded bar-close log return, not midpoint or a tradable fill. Bars are stamped at their opening times; close and OHLC information become eligible only at opening plus 30 minutes, with publication latency still an explicit assumption. Completed flow windows must precede the forecasting cutoff. Future bars cannot enter predictors or training before maturity.

Trade requests use the history host. Each UTC day is recursively divided into disjoint inclusive millisecond intervals until every leaf reports `has_more=false`. Global ID deduplication rejects conflicting payloads. An unresolved saturated one-millisecond interval fails. Completion requires contiguous leaf coverage of the entire fixed month and exactly 48 valid bars per day. This is API-reported coverage, not an independent proof of exchange archival correctness. Empty production-host responses are never substituted for historical coverage.

Prospective limits: 5,000 requests, 512 MiB total response budget, 1 MiB per response, 3,600 seconds request-admission budget, at least 12 GiB free disk before each request, and at least 0.5 seconds between request starts. No automatic retry or overwrite. Resource exhaustion preserves an incomplete terminal outcome and all received raw responses. A blocking read can overrun admission by its 12-second socket timeout; terminal serialization and local export are separately included in actual elapsed cost. A response can exceed the cumulative limit by at most one bounded response before failure. These are not hard process-kill or disk-reservation guarantees.

Planning estimate: the earlier single discovery day contained 9,788 option trades. If representative, a month would contain roughly 300,000 trades and approximately 80–120 MB of unique trade payloads. Recursive parent pages repeat records: a few hundred to roughly 1,500 requests and several hundred MB are plausible. This is an estimate from one day, not a promise. The 512 MiB cap may stop a busier month; retain that result and review rather than silently increase it. SQLite plus raw responses and final export may need around 1–2 GiB. No data are deleted by this collector.

Eight mocked tests passed in 0.13 seconds: subdivision, ID deduplication/conflict, saturation, missing bars, complete bar availability, cap failure, terminal persistence and no overwrite. No fitting or performance claim accompanies these tests.

Frozen protocol assumes zero publication lag after bar end for this retrospective replay; this is not an empirical availability guarantee.
