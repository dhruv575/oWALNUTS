# One-shot actual forecast issuance

```
target/python-workflow-env/Scripts/python.exe STUDIES/market_uncertainty_v1/online_issuance/issue.py --capture <active-capture-directory> --output <new-exclusive-directory> --origin first
```

`first` means the first captured receipt's monotonic time plus15minutes. Later origins are explicit integer monotonic nanoseconds on that anchor plus multiples of30minutes. The runner does not wait or launch a service. Invoke2–10seconds after the chosen origin. Earlier calls are not_due; late or already matured targets are rejected, never backdated. This default cannot replay old origins as live issuance.

An immutable snapshot is taken after the origin so coverage can span it. Snapshot capture is bounded512MiB; clipped snapshots are withheld. All feature receipts are filtered at the origin, and observation_end is forced to that origin. The current forecast has no future label. Only older matured labels can train the exact baseline. Late gap notices inside the brief snapshot delay may conservatively withdraw data quality; later prices never enter features or labels at issuance. Final source validation and feature serialization precede the issue timestamp/lag decision; final small JSON publication follows immediately. This is a local process clock record, not an externally certified timestamp or atomic exchange delivery guarantee.

All records preserve actual UTC/monotonic issue clocks, scheduled origin, cutoff lag, snapshot and source hashes. When both baselines lack20 mature observations, status is `issued_no_forecast`, not an issued interval. Longer computation causing lag>10seconds withholds forecasts. Snapshot/source failures retain a not_issued record. No future scoring occurs here; delayed scoring must be a separate identity-bound operation. Final collector-gap reconciliation can invalidate provisional snapshot coverage.

This prototype is the exact Gaussian/NIG baseline interface, not the demanding stochastic model, a trading strategy, or a market-calibration result. All eight one-shot issuer tests pass, including clipped snapshots and source drift. Inspect the frozen launch manifest and actual scheduler output for live execution status; this page does not establish that a forecast was issued.

## Bounded scheduler

Run `scheduler.py --capture <active> --output <new-schedule-directory> --capture-end-ns <frozen-monotonic-end>`. It plans at most96origins and admits only origins whose30-minute horizon ends by the stated capture end. For a full48hours anchored at firstreceipt this is95origins, not96. Late startup preserves earlier origins as `missed_origin`; it never backdates forecasts. Each future origin is attempted after3seconds. A capture terminal summary stops further attempts, preserving `capture_terminated` records. Unknown future labels are never scored here.

The scheduler has an admission deadline at or before capture end and a12GiB free-disk floor before each snapshot. This is not hard preemption or reserved capacity: a snapshot may finish after admission, and the issuer then withholds forecasts outside its10-second origin deadline. Passing/failing disk readings are recorded in the append-only event ledger. A storage/source/worker failure latches remaining origins as unattempted outcomes. Source drift caught inside issuance also latches the scheduler. Existing outputs are never overwritten or restarted. In-flight issuance failures retain their existing evidence; otherwise failures create the same `issuance.json` shape with explicit origin/horizon.

For a long run, freeze a standalone copy of this directory and sibling `live_snapshot`, `receipt_features`, and `forecast_baseline` directories so relative imports work and subsequent repository development cannot alter the launched experiment. Record runtime versions and exact source hashes in the schedule plan. The running collector remains untouched. Current15issuer/scheduler tests pass0.64s; fake clocks cover missed origins, correctfutureissuance, budget/storage/terminalcapture withdrawal and source-drift latching.
