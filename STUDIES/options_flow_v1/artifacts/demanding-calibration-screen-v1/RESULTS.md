# Demanding fresh-dataset resource screen

All 40 planned fits completed and normalized as usable: 32 oWALNUTS and 8 reference fits. The independent terminal audit passed 1,482 checks and inventoried 18.526 GB of artifacts. It verified reported diagnostic gates, provenance, starts, continuation metadata, coverage calculations, and cost accounting; it did not recompute diagnostics from raw draws. Public raw hashes were first fully inventoried by that audit.

Execution cost was 3,645.807 seconds; reporting added 2,157.532 seconds, for 5,803.339 seconds total. No fits were skipped and no integrity or resource-resolution flags remained. Reporting consumed 37.18% of the total.

On the eight matched datasets, controller costs totaled 688.706 seconds for oWALNUTS and 633.708 seconds for the reference. The descriptive reference/public ratio was 0.9201. Aggregate reporting cost cannot be assigned per arm from the available timers. This is not a speed qualification; the direction differs from the earlier single-posterior comparison.

Nominal 90% public intervals covered simulated truth in 26?31 of 32 datasets depending on the quantity. Neither arm passed the declared coverage rule, and this resource screen was not powered to establish calibration. No market-usefulness claim follows.

Detailed results: [analysis](analysis-v1/OUTCOME.md), [independent audit](independent-terminal-audit-v1/audit.json), and [report timing](run-v2/report-timing.json). Frozen procedures, all intended outcomes, and original costs are retained. Any optimized reporting is a separate subsequent analysis.
