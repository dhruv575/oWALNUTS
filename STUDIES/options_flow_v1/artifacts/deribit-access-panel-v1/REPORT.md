# Historical access attempt: incomplete

The frozen September 25–October 2, 2026 panel acquisition stopped after its
first discovery request. Production returned HTTP 200, an empty trades array
and has_more=false for September 25 UTC. No contracts were selected, no holdout
trades retrieved and no model fitted. One request consumed 135 response bytes.

The raw response, exact parameters, retrieval clocks and source/protocol hashes
are preserved. Empty output is an access limitation for this attempt; it does
not establish absence of trading or a documented retention limit. The recent
two-trade probe from a separate artifact does not establish historical access.

The official currency/time endpoint documents the requested time filters but
does not list an include_old parameter. Further bounded access diagnosis is
needed before changing the panel protocol. A replacement must use a new artifact
and preserve this unsuccessful attempt.

Source: https://docs.deribit.com/api-reference/market-data/public-get_last_trades_by_currency_and_time
