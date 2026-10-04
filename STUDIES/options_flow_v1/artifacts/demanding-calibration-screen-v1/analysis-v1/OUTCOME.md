# Demanding calibration resource screen outcome

All 40 intended fits were normalized as usable: 32/32 public and 8/8 reference, with no missing, unstarted, provenance-skipped, storage-skipped, or budget-skipped cells. This is evidence of computational feasibility on these prior-generated demanding datasets, not a calibration or speed qualification. The separate raw/provenance audit remains authoritative for integrity.

Public selected-draw counts: 3 at 1,000; 21 at 2,000; 7 at 4,000; and 1 at 8,000. Reference counts: 1 at 1,000 and 7 at 2,000. The complete first-pass policy and all diagnostic and precision gates were retained.

## Coverage

Across the 32 public datasets, parameter coverage counts range from 26 to 31 of 32 (81.25% to 96.875%); the four observed predictive counts are 30, 29, 29, and 31 of 32. Across the 8 reference datasets, parameter counts range from 7 to 8 of 8; predictive counts are 6, 7, 8, and 8 of 8. These are separate functionals on shared datasets, not independent trials to pool into one oversized denominator. All 18 selector counts and the original simultaneous intervals are in result.json.

Neither arm meets the prespecified coverage rule. The 100-claim family intervals are necessarily wide at these sample sizes; even 32/32 usability has the declared multiplicity-adjusted lower bound of 0.7886 (reference 8/8: 0.3867). Small-sample deviations must not be called demonstrated bias, and passing every health check does not prove calibrated intervals. This resource study was not powered to resolve the intended calibration equivalence claim.

## Costs and paired descriptive comparison

Fitting and controller execution cost 3,645.807 seconds. Normalization, hashing, and coverage reporting add 2,157.532 seconds, for 5,803.339 seconds total (96.72 minutes). Reporting is 37.18% of that total and must be budgeted explicitly in any scaled campaign. No cap overrun or skipped work is reported. Controller costs for the 32 public fits total 3,012.033 seconds; the 8 reference fits cost 633.708 seconds. Comparing their unmatched averages would confound dataset selection.

On the eight prospectively shared datasets only, public costs total 688.706 seconds and reference costs total 633.708 seconds. The descriptive reference/public ratio of total costs is 0.9201; the median within-pair ratio is 0.9314. These cost measures exclude separately charged aggregate normalization and reporting, which cannot honestly be assigned per arm from available timers. They are exploratory summaries, not a speed verdict. The direction differs from the single-posterior repeatability experiment, reinforcing target-dependent performance.

## Next implications

1. Use the observed stage costs and long-tail tier usage to budget a prospective calibration campaign; 32 datasets are not a substitute for the previously calculated coverage sample sizes. Retain all planned failure denominators without replacing difficult targets.
2. Before a large run, reduce repeated provenance and report IO through verified caching or the shared lossless format equally for both arms, preserving all source and data integrity checks and diagnostic checks. Reporting cost is material here; this analysis does not isolate its internal bottleneck or claim it is all JSON serialization.
3. Keep broader reliability and coverage separate from fixed-target endpoint accuracy. Any future optimized likelihood, binary artifact route, or diagnostic acceleration changes the procedure and needs its own validated prospective recipe.
4. Continue matched comparisons on fresh datasets rather than extrapolating the earlier fixed-posterior runtime ratio. No algorithm parameter, target, gate, seed, or prior was changed by this analysis.

Replay: run analysis-v1/analyze.py only into a fresh output location; result.json is exclusive. Input hashes bind all compact normalized, coverage, manifest, and timing files. Raw arrays were not read or modified.
