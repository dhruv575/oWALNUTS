# Fresh paired workflow result

The preregistered practical-speed criterion was **not met**. Both workflows passed accuracy and reliability checks on this fixed T1000/G4 posterior.

| Result | Public mixed block32 continuation | Associative mixed NumPyro |
|---|---:|---:|
| Usable / intended fits | 36 / 36 | 36 / 36 |
| One-sided 97.5% completion lower bound | 0.902606 | 0.902606 |
| Mean full cost per usable fit | 75.2689 s | 89.4304 s |
| Accuracy checks passed | 24 / 24 | 24 / 24 |

The reference/public cost ratio was 1.18815, with the separately specified approximate 95% paired-bootstrap interval [1.06874, 1.32042]. This corresponds to an observed 15.84% reduction in time. The required interval lower bound was greater than 1.25 (more than 20% less time). The failed criterion remains unchanged.

All 72 intended fits ran once. The controller exited zero and charged 5,929.1731 seconds including shared overhead, within its admission budget. There were no unresolved integrity or cost flags. The frozen analysis also exited zero. All 24 signed-mean endpoint checks and 24 RMS checks passed against the audited approximate reference bank; complete values and margins are in `postfit-analysis-v1/summary.json` and `OUTCOME.md`.

Independent review passed 2,200 terminal checks and 984 analysis checks, including recomputation of the full health/precision gates, first-passing tiers, endpoint extraction, costs, statistical decisions, and hashing 34.25 GB of bound inputs. See `independent-terminal-review`. Raw samples remain local and are bound by `postfit-analysis-v1/artifact-manifest.json`; compact results and executed source archives are retained here.

Reference-bank research cost is separate: approximately 15,650.645 seconds fitting plus 2,556.239 seconds analysis (5.06 hours), excluding earlier preparation. It is not included in the candidate runtime ratio, and no amortized production saving is asserted. The postfit comparison took another 158.656 seconds including preparation.

This result establishes computational repeatability on one posterior. Accuracy and runtime bootstrap intervals are approximate; the reference bank can share missed modes or implementation errors. Reliability, accuracy and runtime use separate error families, not an overall joint 95% claim. No market calibration, repeated-data coverage, default-sampler superiority or broad goal completion follows.

Posthoc diagnosis in `posthoc-cost-decomposition-v1.json` identifies mean public adaptation cost of 26.84 seconds, retained sampling of 25.30 seconds, checkpoint evaluation/serialization of 14.35 seconds, and other costs of 8.78 seconds. These observations motivate development only; any changed workflow needs fresh validation with unchanged scientific gates. Fresh-dataset calibration and chronological market validation remain outstanding.
