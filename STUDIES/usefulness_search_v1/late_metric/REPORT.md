# Later selection fails the improvement screen

The repaired 36-job batch completed in 44.30 seconds. All process groups drained
and frozen dependencies were unchanged. Every run recorded the intended
selection window. All 36 meet R-hat <=1.01, bulk/tail ESS >=400 and zero retained
divergences. Reference draws meet these statistical diagnostics; maximum
combined-MCSE-normalized mean discrepancy is 2.57. These reference checks are
not a new numerical-model validation or proof of decision value.

Candidate window 3 versus diagonal / existing window 2, median paired
minimum-bulk-ESS per total target-call ratios across three fresh seeds:

| Model | vs diagonal | vs window 2 | dense choices, window 2 / 3 |
|---|---:|---:|---:|
| earnings | 5.603 | 0.873 | 2/3 / 3/3 |
| kidiq | 5.481 | 0.972 | 2/3 / 3/3 |
| garch11 | 1.000 | 1.000 | 1/3 / 0/3 |
| GP Poisson guard | 1.000 | 1.000 | 0/3 / 0/3 |

The three-target geometric mean versus existing auto selection is 0.9468,
below the frozen 1.2 bar, and earnings misses the 0.9 floor. No diagnostic
loss occurs and the GP guard holds. Overall verdict: FAIL; no default or
production algorithm change. Gains against plain diagonal alone do not meet
the strong-incumbent requirement. Three exposed models/seeds do not establish
broad reliability, and timing is descriptive only.

The invalid first batch is fully preserved: global source replacement changed
the environment-key string, so both automatic arms used window 2. Analysis
assertions detected the mismatch before scientific summaries. AMENDMENT-1
records the correction, distinct fresh seeds and successful reserved-seed
preflight. All 72 original/repaired jobs, source and both binaries, model/data
dependencies and reference inputs are in the 302-member archive. Hashes were
verified locally; S3 receipts live in archive/. No evidence was reclaimed.

Next hypothesis, not an established result: keep early dense decisions and
reconsider only early diagonal decisions at window 3. This must be implemented
as a warmup policy, not selected post hoc from completed chains. It requires
a fresh frozen experiment against both incumbents, plus oracle/configuration
tests and broader confirmation if promising. Goal remains active.
