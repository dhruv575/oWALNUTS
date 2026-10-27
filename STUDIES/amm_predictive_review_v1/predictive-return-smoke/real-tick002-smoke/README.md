# WP97 real tick 2: full predictive-return numerical smoke

**One preselected origin; diagnostic only.** This follows the existing
`../PLAN.md` and uses the unchanged fixture-validated processor. No additional
origins, sampler runs, raw-draw modifications or component thinning occurred.

WP97's `ref-real-lo` tick 2 had completed its original reference gate at attempt
0, retaining all four chains and 20,000 draws per chain. A separate immutable
snapshot was taken at 2026-10-27 16:56:19 UTC while the broader WP97 experiment
continued. All six snapshot-file hashes were verified before processing. Final
archive reconciliation remains required; this is a completed-origin snapshot,
not a statement that WP97 is complete.

## Numerical result

The full mixture has **80,000 posterior components**, preserving joint beta and
volatility uncertainty. Both rules integrate the future Gaussian innovation and
the Student-t observation CDF. The resulting one-step **log-return** quantiles
are:

| Quantity | 64 nodes | 128 nodes |
|---|---:|---:|
| P5 | -0.005342988779865861 | -0.005342988779865861 |
| P50 | 0.00015215292521720517 | 0.00015215292521720324 |
| P95 | 0.005644471724601938 | 0.005644471724601937 |

Maximum absolute 128-node CDF discrepancy at the 64-node roots is 2.34e-14,
below the declared 1e-6 diagnostic target; maximum root residual is also
2.34e-14. Relative to the 128-node 90% interval width, the largest endpoint
discrepancy is 1.76e-16. Both dynamic brackets expanded twice.

This close node agreement is a convergence diagnostic, not a rigorous integration
error bound. It does not assess posterior Monte Carlo uncertainty, forecast
calibration, observed-return coverage, quoting quality or profitability. Earlier
independent-quadrature checks cover small fixed fixtures, not all 80,000 posterior
components by adaptive integration.

## Measured local computation and memory limit

- Complete processor time after imports: **68.512 seconds**; external launch-to-end
  time: 69.286 seconds. The five-minute cap was not reached.
- 64-node quantile processing: 23.259 seconds, 43 full-mixture CDF evaluations.
- 128-node quantile processing: 42.452 seconds, 43 CDF evaluations; three additional
  128-node evaluations checked the 64-node roots.
- Total Student-t CDF evaluations: **691,200,000**.
- Cached inverse-scale matrices: 40,960,000 + 81,920,000 = **122,880,000 bytes**
  (117.19 MiB), within the declared combined 128 MiB cache allocation limit.

**Actual Python peak RSS was not established.** The external Windows monitor
observed only 4,276,224 bytes on the process returned by launching the virtualenv
executable, which does not capture the working Python process and is smaller
than the explicitly allocated cache. Its exit-code field was also unavailable.
The unedited monitor record is retained as `process-memory.json` so this failed
instrumentation is visible; it must not be cited as workload peak memory. The
processor reports `completed`, stdout confirms completion and stderr is empty.
A future run needs process-tree or in-process peak-memory instrumentation.

These are single-run local postprocessing costs, not sampling or optimized
production latency. A naive 48-origin extrapolation is roughly 55 minutes at this
one origin's cost, already exceeding the earlier proposed 30-minute diagnostic
ceiling; it is not a measured multi-origin result. No such expansion was run.

## Identity and reproduction

- Remote source commit: `a355bae52233b9e5ede69953bb23fb899a43859f`.
- Raw `tick-002-a0.f32` SHA256:
  `7484d1c2b3cadb7fd9ddb133ad5cfeda1a08e688d9664fd409b4bf10fc20e95f`.
- Protocol SHA256:
  `20c4a1e2afab05907ba7defca4e5b669b28cae7439120afe8c8a1decd570f0a3`.
- Exact selected record SHA256:
  `dd904632b5c53cda4d49f6b748ab2dd11c39971039af87360a77840e3cabce65`.
- Executed processor SHA256:
  `fffc989bb6b59f4f2f055b1199f9e391fc49a5a97ea3fc436b1a348bb88875fd`.

`smoke-results.json` contains source/plan hashes, complete input identities,
original gate record, package/platform versions, fixtures, brackets/residuals,
timings and post-run input-integrity verification. `snapshot-provenance.json`
and `snapshot-files.sha256` preserve the completed-origin snapshot lineage.
Raw draws remain in the recovery snapshot and are not duplicated here.

Run the parent directory's documented command with that snapshot as `--study`
and its `cells/` as `--cells`, writing to a new output directory. Existing result
files are preserved. The original WP97 verdict and analysis remain unchanged.
