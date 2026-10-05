# Public receipt collector v2

Run from repository root:

```
target/python-workflow-env/Scripts/python.exe STUDIES/market_uncertainty_v1/receipt_collector/collector.py --output target/market-receipt-route-v2/new-capture --duration 3600 --byte-cap 52428800 --minimum-free-bytes 1073741824 --option-quotes 0 --max-reconnects 3
```

Output directory must not exist. The two required channels are all BTC option trades at100ms aggregation and BTC-PERPETUAL ticker atagg2 aggregation. Optional option quotes use only the initial active metadata/volume snapshot; that selection never changes during recording. The perpetual target is not an index and recorded bid/ask are not guaranteed executable fills.

`receipts.jsonl` preserves the exact received text, local UTC and monotonic receipt clocks and connection number. `discovery.json` preserves initial metadata and selection snapshot. `selection.json` fixes channels. `lifecycle.jsonl` records subscription and gap events. `summary.json` contains terminal status, counts, bytes, hashes, coverage intervals and conservative gaps. Coverage starts after exact channel acknowledgment. A gap starts at the last received message (or connection attempt if none) and ends only at re-acknowledgment. Open gaps have no ending timestamp. Downstream features must mark these periods unknown; no historical backfill occurs. Aggregated feed completeness remains unproved even during connection coverage.

Duration includes discovery. Discovery executes synchronously with3second connect/read timeouts and checks the remaining deadline before each call; final request can overrun by up to6seconds. Websocket entry/read are bounded by remaining duration; close can add3seconds. Payload files collectively obey the byte cap; small terminal summary is outside it. Disk floor is an admission/ongoing check, not a reservation or process memory cap. A drop may reconnect at most the stated count. Captures with gaps/cap/error return nonzero and retain evidence. No output is silently overwritten.

Synthetic tests exercise clean completion, network reset/reconnection, exhausted reconnection, protocol error, wrong acknowledgment, pre-ack data, byte cap, disk rejection and output collision. Run `python -m pytest STUDIES/market_uncertainty_v1/receipt_collector/test_collector.py -q`.

The120second smoke is access/schema evidence, not a forecast dataset or interval-validation result. A useful30minute forecast experiment requires substantially longer chronological collection, stable clock discipline and explicit missing-data treatment.
