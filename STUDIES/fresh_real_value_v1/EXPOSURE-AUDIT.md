# Bounded exposure audit, 2026-10-27

This audit inspected acquisition/request/protocol metadata only. It did not fetch
market outcomes, inspect return/price values, compute scores, or select periods by
volatility, news or realized performance. The proposal is a newly acquired
historical comparison, not a prospective live holdout.

The existing `../predictive_value_design_v1/EXPOSURE-AUDIT.md` establishes that all
September2026 acquired bars and the reconstructed682-return sequence are exposed
development data. Every one of the proposed331 later-tail labels was previously
scored by historical baseline arms. October1–4 has an existing acquisition and
32-origin validation; October live receipt observations also exist. Neither the
old tail nor another subsegment of those acquisitions is fresh evidence.

`exposure_inventory.py` scanned acquisition protocol/request metadata beneath
`C:/dev/owalnuts` and `C:/dev/owalnuts-wt`, including ignored project files and
metadata members of study ZIP archives. It inspected1238 filesystem metadata
files,8 selected archive members and326 ZIP central directories, deduplicating
831 metadata hashes. No files exceeded the4MiB metadata cap; no parse failures.
The resulting `EXPOSURE-METADATA.json` records exact source locations, hashes and
request intervals, including context requests rather than just headline periods.

There are658 distinct numeric request/protocol intervals. Their earliest start is
2026-09-01T00:00:00Z and latest endpoint is2026-10-04T23:59:59.999Z. No selected
acquisition metadata overlaps July26–August31, including the full initialization
context proposed below. The previous September collector's day requests begin
on September1; it does not silently acquire an August warmup window.

Choose August2026 because it is the latest complete calendar month before the
known September/October development exposure. This selection uses the calendar
and exposure records only. No economic-regime assessment entered the choice.
July26–31 is fixed pre-period initialization context, not additional scored data.

Limits: this is a bounded project-access audit, not proof that nobody anywhere
has seen August markets. It excludes raw response/price/return payloads, binary
arrays, browser histories, external machines/accounts and archive members whose
names do not identify acquisition metadata. Files without dated provenance cannot
be certified by this scan. Known later October live receipts are already treated
as exposed even though the numeric interval extractor does not inventory streams.
The allowed claim is **no prior acquisition/use found for this fixed period in
the audited project metadata**, not globally unseen data. Any contrary provenance
found before acquisition blocks the freshness claim and requires a separately
recorded period decision; do not quietly trim or substitute a month.

Existing source contract: the archived collector
`../market_uncertainty_v1/artifacts/historical-september-acquisition-v1/collector.py`
requests `history.deribit.com/api/v2/public/get_tradingview_chart_data` for
BTC-PERPETUAL, resolution30, UTC full days. It requires the exact48-bar grid and
assigns bar-close availability at open+30minutes. This is the prior project's
retrospective convention, not a demonstrated real-time publication guarantee.

Official documentation was consulted for schema only, with no data endpoint call:
[Deribit chart-data API](https://docs.deribit.com/api-reference/market-data/public-get_tradingview_chart_data).
It documents instrument/start/end/resolution requests and timestamped OHLC output.
The historical host's availability for the fixed dates remains an acquisition
check; no fallback venue, instrument, period or return definition is authorized.
