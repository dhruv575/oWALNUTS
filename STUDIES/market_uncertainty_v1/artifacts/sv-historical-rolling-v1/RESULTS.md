# Historical rolling SV comparison

All 360 intended fits passed; all 72 evaluation origins have labels and usable intervals for all six compared forecasting models. This is dependent retrospective September history with zero publication lag assumed, not live calibration or certified market utility.

| Model | Coverage | Mean width | Mean interval score | Lower / upper misses |
|---|---:|---:|---:|---:|
| SV neither | 90.28% | .00809684 | .01054978 | 2 / 5 |
| SV mean flow | 91.67% | .00807734 | .01058844 | 2 / 4 |
| SV scale flow | 88.89% | .00788205 | .01065461 | 2 / 6 |
| SV both flow | 87.50% | .00788145 | .01059432 | 3 / 6 |
| Exact price baseline | 94.44% | .01010530 | .01206660 | 2 / 2 |
| Exact flow baseline | 94.44% | .01009498 | .01201039 | 2 / 2 |

Lower interval score is better. SV intervals are narrower and have lower mean scores than these exact baselines. Flow adds no clear score benefit over the SV model without flow; selecting an ablation from these same outcomes would be exploratory. No SV log-density score or iid confidence interval is claimed.

The 72 matched both-flow fits cost 467.436504 s public versus 648.340462 s reference, including all intended fit costs; all pairs passed. Their total-cost ratio is descriptive, not a new qualified speed claim. Campaign outer elapsed was 2449.989469 s, including the other three public ablations and controller overhead. The full reporter result retains each cell and the individual/common grids.

All frozen source/input and released runtime hashes rechecked; all 360 hardware records show clean containment, four-CPU affinity and exit 0. Full reports, configurations, fixtures, source ZIPs and logs are in evidence.zip. NPY arrays stay external with hashes and byte counts; they were not numerically re-audited here. Earlier launch-only archive remains immutable. ZIP members were extracted in memory and verified against zip-members.json.
