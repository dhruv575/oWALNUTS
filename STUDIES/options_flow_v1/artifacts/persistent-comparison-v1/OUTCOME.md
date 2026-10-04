# Repeated-fit outcome

All four processes and all twelve intended fits completed and met the full
production health and endpoint-precision criteria. The independent terminal
audit passed 577 checks. No fit was replaced or excluded.

| Matched pair | oWALNUTS process cost | NumPyro process cost | Reference/public ratio |
| --- | ---: | ---: | ---: |
| 0, public first | 82.462 s | 121.246 s | 1.470 |
| 1, reference first | 82.498 s | 120.244 s | 1.458 |

These are full A/B/A process costs, including first-fit work, fresh adaptation
for every posterior, compilation and serialization. Per-fit costs and retained
tiers are preserved in `run/timing-report.json` and the fit reports. Later-fit
costs vary with stopping tier and seed; differences between first and returning
A fits cannot be attributed entirely to cache reuse.

The first pair illustrates the distinction between draw efficiency and elapsed
cost: public fits stopped at 4k/8k/4k retained draws, while reference fits stopped
at 2k/4k/2k. All passed the same diagnostic and .02-width endpoint-MCSE criteria.
The observed advantage is practical time to the declared stopping rule, not a
claim that oWALNUTS produces more effective samples per draw.

Summed process cost is 406.4516101 seconds. The separately measured outer run
cost is 407.0426305 seconds, adding 0.5910204 seconds for controller imports,
independent output validation and final bookkeeping outside per-process clocks.
The outer record excludes its own final JSON write, as declared before launch.

## Supported conclusion and limits

oWALNUTS completed this fixed repeated-fit development workload about 1.46-1.47
times as fast as the reference in both balanced pairs (roughly 32% less process
time). This is stronger evidence for practical repeated-use cost than the earlier
single cold-fit measurements. It remains two pairs on two fixed sparse market
posteriors, not a population speedup estimate or a general qualification result.

The audit verified canonical starts, normalized target parity, fresh adaptation,
fixed within-fit adaptation, first-pass stopping, full diagnostic families,
failure denominators, contained execution and report-bound costs. Passing the
MCSE stopping criterion does not independently establish endpoint accuracy.
Posterior-reference uncertainty, broader reliability and useful market interval
scoring remain separate unfinished requirements.

## Reproducibility

Frozen plan SHA-256:
`924569d7d03cd9eadd9e86268da4b2d6577e2d78ce9b39536cde3b50b44271e6`.
The committed prelaunch plan, seed audits, fixture construction and prefreeze
audit are retained. `run/independent-terminal-*` contains the terminal audit,
executable auditor, exact study-source archive and provenance.

All 27 raw files remain local, totaling 1,397,203,078 bytes. The independent audit
and `raw-artifact-manifest.json` record their hashes; a study-specific local Git
exclusion keeps these arrays out of Git. All compact results, status files,
hardware records, logs, source snapshots and costs are committed. Restore the
manifested raw files to replay raw-data checks in another checkout.
