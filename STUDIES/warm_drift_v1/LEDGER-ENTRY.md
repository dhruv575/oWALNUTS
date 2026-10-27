### WP96-WARM-DRIFT-V1: no frozen or re-adapted K=200 policy qualifies over 2,000 fixed-window updates; post-shock quote precision degrades without rising frozen-kernel cost

- Ordered time: 2026-10-27 00:06–02:02 UTC, `wt/warm-drift`, frozen at
  `9210c9471b2eacc1e1528455720239863bae76f0` (base `main` `f4a01ba6`, WP87/WP88,
  before the WP90 trap-guard default). Recovered and independently reanalyzed
  on 2026-10-27 after the original agents hit their API limit. Two pinned lanes,
  cores 8–11 / 12–15 of the shared c7a.4xlarge; 18/18 cells completed with all
  expected ticks and files, 32,000 warm updates, no reruns.
- Protocol/config: `STUDIES/warm_drift_v1/{PREREGISTRATION.md,protocol.json}`;
  WP84/WP88 Student-t SV target on a sliding 250-return window. Two synthetic
  streams share innovations (seed 96096); one switches mean and volatility
  innovation scale at return 1,250, entering at tick 1,001. Four chains, K=200;
  sampler seeds 960101/960102. Policies frozen, re-adapt every 100 or 500 ticks,
  or trigger on trailing cost >1.5x baseline / unchanged fraction >5%; each
  re-adaptation uses 200 warmup transitions. Gated 4x2,000/20,000 reference every
  25 ticks, seed bases 969450/969500. Pass: P50 relative error <=2%, P95 <=5%,
  no stuck chain on >=95% pooled and >=90% per seed in each half and stream;
  latency and drift are reported, not gated.
- Outcome: **no policy passes any stream-half aggregate**. Shift halves 1/2:
  frozen 83.75/66.25%, every-100 87.50/71.25%, every-500 88.75/60.00%, triggered
  86.25/62.50%. Control halves 1/2: 86.25/91.25%, 88.75/82.50%, 88.75/86.25%,
  87.50/90.00%, respectively. No supported long-run frozen/re-adapted quote
  configuration and no library/default change.
- Practical cost: shifted-stream median/P99 latency 129/157 ms frozen,
  306/585 ms every-100, 263/534 ms every-500, 303/533 ms triggered; shared-host
  timing and original grouping convention. Re-adaptation increases typical
  cost; maximum every-100 update 1.15 s. The trigger never fires after the
  shock; seed 960102 fires once at tick 913 in both streams due to unchanged
  fraction 0.0501875, with cost ratio only 0.790807; seed 960101 never fires.
- Failure diagnosis (post hoc, same evidence): frozen shifted-half-2 median
  own P50/P95 relative MCSE 1.69/3.59%, signed mean errors +0.26/+0.25%; 27/80
  failed ticks (21 P50, nine P95, three overlap). Accuracy already fails
  before the shock and on the control; failure persists after full window
  replacement. Frozen cost stays near/below baseline rather than rising.
  Finite quote-functional precision is implicated, not established as the sole
  cause; more draws or analytic integration are unqualified hypotheses.
- Diagnostics: zero stuck scored warm ticks, zero retained divergences across
  all warm updates, 16/16 clean and accurate initial fits, no re-adaptation
  fallback or error. Drift bound holds in 17/32 windows, not the predicted
  >=26. Reference interval occupancy is 89.64–90.29%; synthetic truth coverage
  is 77.5–90% over small dependent halves, so no blanket calibration claim.
- Reference: all 162 ticks pass; eleven drop a flagged chain, one control tick
  needs the prescribed second attempt. Supplemental saved-coordinate audit
  (mu/log_sigma/h_last; not a changed frozen gate): max R-hat 1.000580, min bulk
  ESS 14,561, min tail ESS 25,971, zero kept-chain divergences. Max relative
  reference MCSE 0.228% P50 / 0.522% P95. No independent algorithm or full-path
  reference validation is claimed.
- Artifacts: original compact draws/logs/results preserved;
  `artifacts/recovery` contains source/archive hashes, inventory, supplemental
  audit and failure decomposition. Archive SHA256
  `c1557f20369bb90b1a7b4a96f15b506a5048a29a3b900d033d5063b01cd0cf9c`;
  1,658 cell files, 185,183,822 bytes, raw f32 files uncommitted but hashed.
  Frozen source hashes match. NumPy 2.5.4 / ArviZ 0.23.4 reanalysis reproduces
  the table and all decisions; four reported warm R-hat differences <=7.08e-5
  across platforms do not cross 1.01. Original artifacts are unchanged.
- Conclusion/next decision: preserve the negative result; investigate
  finite-refresh and quote-functional precision before freezing any successor
  qualification. Accuracy is observed every 25 ticks, including every periodic
  adaptation tick, on a fixed-window synthetic posterior. No every-tick,
  full-history, real-market, executable-quote or profitability claim follows.
