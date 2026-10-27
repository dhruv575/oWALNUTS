# Bounded exposure audit, 2026-10-27

The proposed months are April, May and June 2026, selected as the latest three
complete calendar months before July 2026. No prices, returns, volatility, news
or forecast outcomes were inspected to choose them. July 26 through August 31
is now exposed through E62; September and October already had development use.

The metadata-only inventory scanned C:/dev/owalnuts and C:/dev/owalnuts-wt,
including ignored acquisition/request/protocol files and selected ZIP metadata.
It inspected 1,396 files and eight archive members, with 326 ZIP directories,
870 distinct metadata hashes, zero oversized skips and zero parse failures.
Execution took 9.218 seconds within a 120-second bound; limits are 5,000 files,
1,000 metadata archive members and 4 MiB per metadata file.

The 732 distinct numeric request intervals range from July 26 through October 5
(endpoint convention varies by source). None overlap the entire proposed
March 26 through June 30 acquisition, including all initial-fit context. The
complete path/hash/request interval inventory is EXPOSURE-METADATA.json.

April initializes from March 26 context; May from April 25 context; June from
May 26 context. Shared context inside the three planned months is intentional:
May/June initialization includes earlier panel observations. Fetching one
contiguous 97-day acquisition avoids independently revised duplicate downloads.
Each month still initializes its own model and baselines; the months are not
independent replications of a market process.

This is a bounded project-access finding, not globally unseen data or a
prospective live holdout. Raw market payloads, binary arrays, unexpanded tar
archives, browser histories and external accounts/machines were excluded.
Previously extracted E62 tar archives were covered as filesystem metadata.
Undated or unrecognized provenance cannot be certified. Any discovered contrary
provenance blocks the affected freshness claim; no silent period replacement,
trimming or outcome-selected fallback is allowed.
