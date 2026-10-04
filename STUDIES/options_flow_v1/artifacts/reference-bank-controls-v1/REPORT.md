# Finite-bank feasibility control: unresolved

All 48 prospective trials completed; none resolved. Each trial used four fits per backend, one chain per fit, paired lengths128/256 and1000 whole-fit bootstrap replicates. The control deliberately evaluates a small bank, not the production recipe. Total recorded trial work was6.66seconds on a shared developer machine, not an isolated benchmark.

| Control | Completed | Resolved | Both exact endpoints covered |
|---|---:|---:|---:|
| iid Normal, same backend targets |12/12|0/12|12/12|
| iid Normal, backendB shifted+.5 |12/12|0/12|0/12|
| AR1 rho=.9, same targets |12/12|0/12|11/12|
| AR1 rho=.9, backendB shifted+.5 |12/12|0/12|4/12|

Backend equivalence failed its .02-width budget for both endpoints in every trial. Dependent controls additionally had precision and length-stability failures. Zero false resolution is not useful discrimination when true-null resolution is also zero. Twelve outer trials cannot establish nominal coverage; the bootstrap tails have only about4expected resamples and four independent fits/backend, both serious limitations.

Mean/max actual endpoint error relative to exact Normal90%width was .01375/.02543 for iid null, .03685/.08226 for dependent null, .08857/.11019 for iid shifted, and .09398/.15379 for dependent shifted. Shifted results intentionally violate the shared-target assumption and should remain unresolved.

## Prospective cost scaling, not a launch recommendation

For null banks, the median maximum absolute backend-difference interval bound divided by estimated interval width was .0853(iid) and .2344(rho=.9). Under a rough inverse-square-root effective-information assumption, reaching .02would require about18× and137× more information respectively. Reaching .001under the same approximation would require about7,269× and54,922× relative to this tiny pilot. The .001budget is20times tighter than .02and therefore about400times more expensive at fixed statistical efficiency. These are arithmetic extrapolations from noisy pilot bounds, not runtime forecasts or promises of resolution.

Increasing retained length reduces within-fit Monte Carlo error but leaves only four independent fit units for estimating whole-fit uncertainty. Increasing independent fit count improves that uncertainty calculation and sensitivity to between-fit bias; it is not interchangeable with length. Moving to the proposed eight fits/backend only doubles the independent units and still requires bootstrap-coverage validation. More bootstrap resamples improve numerical tail resolution, but create no additional posterior information.

The production plan also has twelve endpoints rather than two, increasing multiplicity and bootstrap-tail requirements. Freeze a next cost pilot separately; do not launch a large posterior bank based on these extrapolations. A practical next methodological check should vary fit count and length separately on exact null/shifted controls, retain dependent stress cases, and demand some null resolution alongside low false resolution before interpreting a reference-bank accuracy verdict.

Ten focused tests passed, including a nondegenerate whole-fit bootstrap whose lower/upper endpoint errors have positive covariance and whose shared-reference contribution does not shrink when the same bank is compared with20candidate replicates. This tests error propagation, not operating-characteristic calibration.

`plan.json` and its digest bind the original bank/control source hashes and numerical versions. `sources.zip` preserves exact implementation and test bytes; `provenance.json` records commands and hashes. `cell-evidence.jsonl.gz` preserves all145 original JSON records losslessly, including complete joint bootstrap endpoint vectors. No posterior sampling bank ran. Results remain exploratory and unqualified.
