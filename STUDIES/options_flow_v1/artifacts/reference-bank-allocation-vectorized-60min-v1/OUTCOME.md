# Reference-bank allocation outcome

The prospectively frozen 3,600-second campaign completed all 148 intended cells
(four timing sentinels and 144 main trials), with zero failed or unstarted cells,
in 707.3544 seconds. Independent integrity audit: 2,527 checks passed. Statistical
qualification remains false. These are analytic stationary Normal/AR(1) controls,
not posterior sampling or market calibration results.

At equal 32,768 full-length values per backend, the iid allocations with 16 fits
of length 2,048 and 32 fits of length 1,024 each resolved 6/8 null trials, covered
both known endpoints in 8/8, and passed exploratory progression. The 8-fit,
4,096-length allocation resolved 5/8, covered both endpoints in 7/8, and included
one resolved miss. For that replicate (5), the upper endpoint truth 1.64485363
was below its confidence bound 1.64544157. Retain this counterexample.

All 24 strongly correlated null trials remained unresolved. Each failed backend
equivalence at both endpoints: difference bounds of .0263-.0642 interval widths
exceeded the unchanged .02 requirement. Endpoint halfwidths (.0092-.0258) and
paired-length bounds (.0157-.0375) passed their .1 requirements. This identifies
insufficient information to resolve backend agreement, rather than demonstrating
endpoint bias or length drift. All deliberately shifted campaign groups remained
unresolved, as desired; this does not establish a well-powered detection rate.

Each group has only eight replicates. Exact unadjusted 95% binomial intervals are
[.3491,.9681] for 6/8 and [0,.3694] for 0/8. Passing these exploratory criteria
does not establish calibration or reliable resolution probabilities.

Next investigation: retain the .02 agreement requirement, prospectively compare
larger correlated banks, and add an independent endpoint-uncertainty control.
An exact iid order-statistic control would help diagnose the small-fit miss.
Evaluate unconditional coverage and coverage conditional on resolution separately.
More bootstrap repetitions alone cannot replace information in the original draws.

## Evidence and storage

`plan.json` and `plan.sha256` preserve the frozen design; `results/summary.json`
retains every intended cell and cost. `independent-audit.json` and
`independent-progression-summary.json` preserve the integrity and statistical
decisions. `study-source.zip`, the archived auditor, and `auditor-provenance.json`
preserve exact source evidence.

All 148 raw `results/*/bank.json` files remain locally available, totaling
357,772,873 bytes. `raw-bank-manifest.json` records their sizes and SHA-256 hashes;
the independent audit also binds their hashes. The raw banks are intentionally
excluded from Git through a campaign-specific local exclusion. Other results,
hardware records, failures/statuses, and logs are archived in Git. Replaying the
raw-data audit from another checkout requires the manifested raw banks.
