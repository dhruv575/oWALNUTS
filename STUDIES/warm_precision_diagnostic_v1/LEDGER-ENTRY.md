### WARM-PRECISION-DIAGNOSTIC-V1: fixed K=400 plus analytic scale quantiles merits further testing on reused WP96 data; one fresh seed, not qualification

- Ordered time: plan/supervisor frozen at `42214fce` before sampling on
  2026-10-27 16:54:21–17:23:55 UTC. Six cells, K=200/400/800 on shift/control,
  2,000 updates each, frozen WP96 binary/library at `9210c947`, sampler seed
  99271021 (base and derived seeds searched before freeze). Cores 0–3 / 4–7,
  co-tenanted with WP97 references on 8–15. All cells exited zero, all 12,000
  updates and 480 scored rows present, no reruns, no resource cap reached.
- Design: original 250-return synthetic windows and audited WP96 references
  reused; one paired fresh sampler seed, not nested budgets after every tick.
  Original predictive-noise quantiles and analytic scale-mixture CDF inversion
  at P50/P95, original versus original / original versus analytic / analytic
  versus analytic reference, unchanged descriptive 2%/5% bands and stuck-chain
  handling. Missing data remains in planned denominators. No adaptive stopping.
- Outcome, counts per 40 scored ticks (half1/half2): shift K200 noise34/31,
  analytic37/36; K400 noise40/34, analytic40/39; K800 noise40/39, analytic40/40.
  Control K200 noise35/34, analytic38/38; K400 noise40/39, analytic40/40; K800
  both40/40. Across all cells original/original446/480, original/analytic446/480,
  analytic/analytic468/480. These are descriptive one-seed counts, not a
  qualification rule or default decision.
- Precision: shifted-half-2 analytic P50/P95 own-MCSE medians 1.17/2.29%,
  0.85/1.62%, 0.61/1.19% at K200/400/800; signed mean errors
  +0.09/+0.31%, −0.13/−0.32%, +0.06/+0.05%. K400's only analytic miss is tick
  1,725, P50 −2.78%, P95 −2.43%. These uncertainty estimates are not validated
  for adaptive stopping. Maximum analytic reference own-MCSE 0.177/0.355%.
- Cost: median sampler wall about128/255/503ms at K200/400/800, P99 about
  143/273/531ms. Analytic arithmetic medians roughly0.56/0.93/1.64ms, measured
  separately on saved ticks after sampler process groups drained. Sums of
  sampler and arithmetic measurements are not fused online latency. Combined
  estimator-MCSE work reported separately. Arithmetic completed17:24:45UTC in
  16.29s process wall, before WP97 official pooling, still on a shared host.
- Diagnostics/integrity: zero stuck scored ticks or retained divergences,
  all initial fits kept four chains. All123 paired pre-shock raw files are
  byte-identical; expected ticks/shapes complete. All reference bytes pinned
  to prior audit, input hashes verified before/after, maximum root residual
  2.51e-12. Six integrity/numerical fixtures pass; original WP96 score replay
  agrees below1e-12. Executed source and process records retained.
- Artifacts: `STUDIES/warm_precision_diagnostic_v1`; archive SHA256
  `154cd1703845d0ec605b8197e6a6f8caeb604f2b4a3cd4cd640d1b5deb87ad4f`,
  10,322,273 bytes; raw compact draws uncommitted but checksum-pinned locally
  and remotely. Original WP96 artifacts were not changed.
- Next decision: fixed K400 plus analytic scale quantiles is a candidate for
  fresh multi-seed qualification and a resident implementation check. This
  single-seed diagnostic on reused data/reference cannot establish broad
  posterior accuracy, every-tick behavior, return-risk calibration, executable
  quoting or profitability. No library/default/deployment change.
