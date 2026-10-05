# Receipt-clock market features

`features.py` consumes the collector's JSONL envelopes (`receipt_utc_ns`, `receipt_monotonic_ns`, `raw`). It performs no acquisition, fitting or interpolation. All data selection uses local monotonic receipt time, not exchange event timestamps.

Default: 15-minute option-flow window, 30-minute midpoint-return horizon, five-second maximum quote receipt age. `origins_ns` is an explicit fixed grid. Flow sums **raw BTC-option trade amount**, buy positive/sell negative, across the currency option channel; this is not delta-weighted exposure. Duplicates by trade ID are removed; conflicting duplicates fail. Flagged block/combo trades remain included and separately counted. A malformed trade makes its window's flow unknown.

Known flow requires an explicit collector-declared acknowledged connection coverage interval spanning the whole window and no gap intersecting it. Missing coverage, pre-ack windows and gaps produce null signed/total feature values; observed partial counts and amounts remain separate. A known empty window is zero. This is a received-stream contract, not proof of exchange feed completeness or absence of packet loss. V2 session/gap translation will use its explicit acknowledgement/terminal clocks; no invented coverage from silence.

The price target is the independent **BTC-PERPETUAL bid/ask midpoint**, not an option last trade or BTC index. The latest received quote at or before origin/horizon is used only when open, positive, uncrossed and within the receipt-age limit. An invalid latest quote is not replaced by an older favorable quote. Gaps after that quote invalidate it. Label availability is the horizon boundary after collection reaches that boundary; quotes received later never backfill it. Features and delayed labels are separate objects, so a forecast can be issued without inspecting the future label.

Receipt freshness does not imply the exchange price changed: repeated ticker messages can report unchanged bid/ask. The probe has 31 perpetual ticker notifications but only 15 distinct bid/ask pairs. Rows are serially dependent, not independent samples. Exchange event timestamps are retained as metadata; local receipt clocks are not certified or synchronized with the exchange.

Five focused tests passed: future quote perturbations leave earlier features unchanged; crossed/stale latest quotes cannot fall back; gaps distinguish unknown flow from known zero; receipt-time trade aggregation deduplicates correctly; collector gap/terminal translation preserves a label after a quiet period without inventing a new quote.

Use `--collector-summary summary.json` for V2. The receipt file SHA must match the terminal summary. The builder takes coverage, gaps and terminal time exclusively from that summary; CLI configuration cannot inject them. The summary itself is hash-recorded, not independently authenticated. If `origins_ns` is omitted, the grid starts one feature window after the first receipt and uses `origin_stride_ns` (default 30 minutes) through the observed terminal time. An empty `{}` config therefore yields no forecast grid on a 120-second smoke. A separately labelled two-second smoke can set horizon/stride to 2e9 and window to 1e10 nanoseconds. This tests plumbing only.

## Probe outputs

`smoke-config.json` deliberately uses a **one-second** feature window/horizon and two-second staleness to test plumbing on the approximately 30-second probe. Its 29 origins yield 28 observable midpoint labels, and **zero known-flow features**, because this original probe has no formal connection-coverage/gap evidence. These are not 30-minute forecasts or an accuracy dataset. `default-result.json` retains the ordinary 30-minute horizon as unavailable; the probe cannot supply it. Original probe bytes and executable/config hashes are recorded in each result. No new acquisition or sampler run occurred.

## Actual collector V2 integration

The separately retained `collector-v2-smoke/` contains results from the completed 120-second V2 collection. Both commands exited zero. Ordinary defaults give **0 origins/0 labels**. The explicit two-second feature window/horizon/stride gives **59 origins, 59 known received-flow windows, 51 known-zero windows, 17 deduplicated received trades across windows, and 58 observable midpoint labels**. No malformed trades were encountered. These counts demonstrate correct causal transport, not predictive accuracy or a sufficient financial dataset. The summary reported one acknowledged connection and no gaps; known flow still does not mean independently proven exchange completeness.

Run from the repository root (replace `python` with the configured environment interpreter):

```powershell
python target/market-receipt-features-v1/features.py --receipts target/market-receipt-route-v2/smoke-v1/receipts.jsonl --collector-summary target/market-receipt-route-v2/smoke-v1/summary.json --config target/market-receipt-features-v1/collector-v2-smoke/default-config.json --out NEW-default-result.json
python target/market-receipt-features-v1/features.py --receipts target/market-receipt-route-v2/smoke-v1/receipts.jsonl --collector-summary target/market-receipt-route-v2/smoke-v1/summary.json --config target/market-receipt-features-v1/collector-v2-smoke/two-second-config.json --out NEW-two-second-result.json
python -m pytest target/market-receipt-features-v1/test_features.py -q
```

Use new output names; outputs are exclusive. `verification.json` binds source, configs, actual collector summary and receipt bytes. The deliberate modified-receipt invocation returned nonzero with `Collector receipt binding differs` and produced no result. Exact executed sources are preserved in `collector-v2-smoke/executed-source/`. Earlier v1 probe examples remain separately labelled and are not overwritten.
