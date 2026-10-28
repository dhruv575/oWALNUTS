# Exploratory posterior marginal coverage supplement

This reuses all existing sealed draws and generating truths. No new inference,
data generation, randomization, exclusions or outcome-selected ticks were used.
It supplements the original predictive analysis without changing its protocol.

All 32 histories x 32 ticks x 4 parameters are available: 4096/4096 slots.
For each slot, `posterior_coverage.py` computes empirical equal-tail 50%, 90%
and 95% intervals from all four chains and 400 retained draws per chain.
The terminal latent truth is h[249+tick], checked against the stored record's
current index. Every consumed metadata/array file is checked against the
original packet seal; array hashes are also checked against their records.

| Parameter | Tick 1 covered, 50% / 90% / 95% | Tick 32 covered, 50% / 90% / 95% | 95% count range across all 32 ticks |
|---|---|---|---|
| mu | 15 / 29 / 31 | 15 / 30 / 32 | 30–32 |
| log_sigma | 14 / 27 / 31 | 16 / 28 / 31 | 29–31 |
| beta | 12 / 26 / 27 | 12 / 25 / 28 | 27–28 |
| h_last | 16 / 30 / 31 | 17 / 29 / 31 | 28–32 |

Every count has denominator 32. The endpoint table is a compact view; the JSON
retains every tick, interval, generating truth, fraction below truth and tie
count. Ranges are descriptive extrema, not simultaneous confidence bands.

Beta warrants attention in a larger independent calibration design. This small
sample does not establish a defect: the same histories recur at every tick, so
the repeated lower counts are not independent replications. Empirical MCMC
quantile error is not adjusted here. No iid rank null, p-value, acceptance gate,
or whole-posterior correctness claim is applied. Marginal prior-average
coverage can also miss an algorithm that ignores the data; predictive and
data-dependent checks remain necessary.

Reproduce from the repository root:

```powershell
python -m unittest discover -s STUDIES/prior_predictive_validation_v1 -p test_posterior_coverage.py
python STUDIES/prior_predictive_validation_v1/posterior_coverage.py STUDIES/prior_predictive_validation_v1/execution-20261027/evidence/prior-predictive-validation-20261027 NEW-OUTPUT.json
```

The output path must be new. The checked result is
`execution-20261027/POSTERIOR-COVERAGE-SUPPLEMENT.json`. NumPy 2.5.2 was used;
the quantile interpolation method is explicitly `linear`. Two analytic-grid
tests check interval membership, outside truths, ties and invalid shape.
The earlier development invocation had a syntax error, produced no result and
was corrected before any analysis output was generated.
