# Historical confirmation: final analysis, 2026-10-29

**Predictive confirmation was not established.** All 255 batches and 3,050
scheduled slots reached terminal accounting. There are 3,049 case reports:
3,048 NUTS and 3,049 WALNUTS fits qualify. The frozen primary analysis returns
`not_admitted`, not a successful confirmation or equivalence result.

September primary cell 62 has no report: ArviZ failed at startup while replacing
its shared daily-warning cache file. September primary cell 464 has a NUTS
physical-coordinate diagnostic failure. Both remain in the planned denominator;
neither was rerun or replaced. September has 1,438/1,440 qualified pairs and
October has 1,488/1,488. All 122 daily cap-sensitivity cells qualify for both engines.

## Predictive results

The table is **descriptive available-case evidence**, not the admitted primary
analysis. Units are mean log predictive density difference, nats per origin.
Positive means favor NUTS. Each lower bound is the one-sided 98.75% percentile
bound from 20,000 paired circular 96-origin block resamples.

| Month | Comparator | Mean gain | Lower bound | Median gain | Positive fraction |
|---|---|---:|---:|---:|---:|
| September | Rolling250 t5 | 0.065411 | 0.025965 | -0.002383 | 49.30% |
| September | EWMA t5 | 0.014417 | -0.003516 | -0.018976 | 43.67% |
| October | Rolling250 t5 | 0.073488 | 0.027903 | -0.017165 | 45.97% |
| October | EWMA t5 | 0.017080 | -0.004008 | -0.022783 | 44.35% |

Even setting aside the admission failure, the required positive EWMA lower
bounds are absent in both months. Mean improvements exceed the declared 0.01
research threshold, but do not satisfy the uncertainty requirement. This
descriptive conclusion is unchanged at blocks 48 and 336: rolling lower bounds
remain positive and EWMA lower bounds remain negative in both months. October
alone has a complete primary denominator and still fails the EWMA requirement.

The secondary NIG AR1 comparison gives mean gains of 0.172409 and 0.241294,
respectively; it cannot substitute for a primary comparator. Median gains against
rolling and EWMA are negative. Tail influence matters: removing each column's
largest 15 gains (an explicitly post hoc descriptive check) changes the EWMA
means to -0.000144 in September and 0.004125 in October. These trimmed quantities
are not replacement endpoints.

## Sampler agreement and costs

Qualified-pair WALNUTS-minus-NUTS means are 0.00000328 in September and 0.00015356
in October. Their 96-origin 95% intervals are [-0.00012423, 0.00013218] and
[-0.00000813, 0.00031627]. All three block-length intervals lie inside the
prespecified +/-0.01 tolerance. This supports close predictive agreement on the
observed qualified cases; the missing/failed primary cells still prevent the
study-wide formal predictive-functional equivalence claim. It does not establish
full posterior equality.

Per-origin differences, combined log-score MCSE (root sum of the two squared
MCSEs), and descriptive standardized discrepancies are retained in RESULTS.json.
This MCSE combination assumes independent sampler Monte Carlo errors; it is not
the uncertainty of the historical monthly predictive effect.

Across the 3,049 reported cases, median setup/sampling/physical-diagnostic seconds
are 14.575/4.866/2.030 for NUTS and 1.130/5.691/2.157 for WALNUTS. Compilation and
setup dominate the apparent total-cost difference. Sampling alone does not show
a WALNUTS median speed advantage. These are observed fixed-budget costs, not a
precision-matched algorithmic speedup; serialization, prediction and orchestration
are not included in those three components.

## Sensitivity and PIT

All daily cap .5 and cap 2 cases qualify. Their September mean gains over EWMA
are -0.051456 and -0.051432; October gains are 0.002129 and 0.001927. These are
30/31 daily-origin subsets, not independent replications or evidence that a cap
change improves the full primary calendar. No cap is selected from these results.

Primary NUTS PIT means are 0.501918 and 0.499628. Counts below .05 / above .95
are 54/55 of 1,438 and 61/67 of 1,488. WALNUTS counts are 54/54 of 1,439 and
61/67 of 1,488. These summaries do not constitute a serial-calibration test.

## Evidence, methods and reproduction

All 255 exact-version archive verification receipts were checked against their
packed metadata, PLAN hashes and raw-manifest hashes. All scheduled indices,
freeze bindings, batch process-drain receipts and source-unchanged flags passed.
31,257 selected evidence files were byte/hash checked during compact collection.
The analysis separately rechecks all reports and terminal control inputs before
loading scores. It uses the existing exact-version restore receipts, rather than
claiming a new download and rehash of every raw S3 trace in this analysis turn.
ARCHIVE-BINDINGS.json records all raw S3 object versions.

Local compact input archive: `target/confirmation-final-analysis-inputs-v2.tar.gz`
(151,985,550 bytes), SHA256
`f25c4888b37b659d8c06aa01afc5aa30192e1db731299775cc21cbf5b53bebc3`.
This archive was transferred locally and its SHA256 matched the remote digest.
Raw traces remain in the verified private S3 archives. The compact archive
contains reports, diagnostic CSVs, manifests and control receipts, not raw draws.

Run `final_analysis.py INPUT_DIRECTORY NEW_OUTPUT_DIRECTORY` after unpacking
the compact archive, with NumPy available and the repository source layout intact.
The script verifies calendar, bootstrap and protocol bytes against FREEZE.json.
Execution used the existing pinned EC2 Python environment. Scientific sampling
sources, seeds, budgets and diagnostic thresholds were not changed.

The frozen analysis gate and primary-analysis implementation were exercised by
12 passing unit-test invocations. Two additional tests check exact agreement of
the descriptive bootstrap with the frozen bootstrap on complete data and the
constant-mean/denominator behavior with calendar gaps. All passed.

September's available-case bootstrap is a post-acquisition descriptive extension:
sample original contiguous calendar positions, retain missing positions in each
block, and divide by the sampled qualified count. No values are imputed and gaps
are not closed before resampling. The same PCG64 seeds, paired columns, 20,000
replicates and linear percentile quantiles are used. October has no gaps, so this
reduces to the frozen complete-data calculation. This does not correct bias from
missing or diagnostically unqualified observations. Neither bootstrap offers
exact finite-sample coverage for these dependent market data.

The defensible finding is close observed sampler prediction agreement and a
model advantage over a rolling baseline, with insufficient evidence of an
advantage over EWMA. Profitability, AMM decision value, prospective performance,
and submission readiness remain unestablished. Further confirmation needs a new
prospectively frozen study; these exposed months cannot become a fresh holdout.
