# September historical acquisition

One authorized run completed with exit 0: 201,712 unique BTC option trades and 1,440 BTC-PERPETUAL half-hour bars. It used 628 public requests, 121,226,708 response bytes and 376.61 seconds. API-reported complete leaf coverage, duplicate-payload consistency, every stored trade within completed coverage, full bar grid and source/protocol terminal checks passed. No retries, fitting or selection on future return outcomes occurred.

The full raw responses, SQLite store and exported data remain outside Git at the paths in external-data-inventory.json, with byte hashes. This compact archive includes executed source, frozen protocol, tests and completeness evidence. Eight final-source mocked tests passed. Completion relies on the API archive and its has_more declaration; it is not an independent audit of all exchange events.

Treating candle ticks as opening timestamps follows the bar convention; it was not expressly established by the API time-axis description. Zero publication lag at bar end is an explicit retrospective replay assumption, not observed receipt availability. This target is traded bar-close return, not midpoint, delta exposure or causal flow effect.

All September evidence is retrospective development. The prospective analysis split is September 1?14 initialization/development, 15?21 validation and 22?30 frozen exploratory evaluation. Freeze features, priors and model recipe before final-segment fitting. Original sparse-contract failures and the separate live receipt-clock route are unchanged.
