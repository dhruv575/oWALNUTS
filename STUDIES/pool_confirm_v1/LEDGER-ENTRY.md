### E59 / WP97-POOL-CONFIRM-V1: reweighted pooling qualifies K = 200 on both fixed streams; lower transition budgets do not qualify jointly

- Ordered time: 2026-10-27, sampling 16:36:31-17:34:39 UTC; original timed analysis
  17:36:06-17:36:42. Branch `wt/pool-confirm`; actual execution freeze `5aa256fb`,
  launch commit `a355bae5`, unchanged protocol/harness/library/analyzer relative
  to draft `ee32a28a`. Existing executable SHA256
  `7ef3556ce13e52866e0ce0f8012409a4444a1aae150acc4a95b8d675e9988828`.
  Cores 8-11/12-15 of the existing c7a.4xlarge; 22/22 complete cells, exit zero,
  no reruns, 58 min 8 s wall. Recovered diagnostic smoke preserved separately.
- Protocol/config/seeds: `STUDIES/pool_confirm_v1/{PREREGISTRATION.md,protocol.json}`;
  WP84 price-only SV model, fixed rho=.95/nu=5, 250 initial returns and 100 appended
  returns; K={20,50,200}, H={10,20}, exponential primary/uniform secondary, H=1
  control. Warm seeds 971201-971203 sim / 971301-971303 real; reference bases
  979460/979500; propagation bases 972000/973000. Same previously inspected sim
  and real bar-close streams; new sampler seeds, not new-data generalization.
- Decision rule: P50/P95 of predictive Student-t scale within 2%/5% of a gated
  reference, no frozen stuck-chain census flag, declared library+pool time <400 ms,
  >=285/300 pooled, >=90/100 each seed, signed-P50 drift <=0.5 pp each seed.
  These scale quantiles are historical quote proxies, not executable spread or
  return-risk quantities. Original criteria and historical protocol terms retained.
- Outcome: primary K=200/H=10 PASS on sim 300/300 and real 294/300 (seeds 100/100/100
  and 99/97/98), median component latency 79.7/306.2 ms, max absolute drift 0.158/0.438 pp.
  K=200/H=20 also PASS at 300/300 and 296/300, 84.0/311.3 ms, max drift 0.120/0.274 pp.
  K=50/H=10 passes sim only, 292/300; real 261/300 fails. K=50/H=20 real 283/300 misses
  the pooled requirement by two, while sim 294/300 fails one drift window (+0.593 pp).
  K=20 fails. The smallest jointly qualifying K remains 200; no threshold relaxed.
- Controls/secondary: unpooled K=200 passes sim 286/300 but fails real 261/300.
  Pooling therefore repairs real-series scale accuracy at K=200, without qualifying
  a lower transition budget jointly. Uniform K=200 passes both H and both datasets
  but remains secondary. All warm ticks have zero recorded divergences, no stuck
  census flags, no slow ticks under the component metric; no tick-0 retry or chain drop.
- References/diagnostics: all 202 origins passed on attempt 0 with all four chains;
  no flags, retries or double failures. Max original Rhat(h_next)=1.00019;
  median P50/P95 reference MCSE 0.085%/0.193% sim, 0.123%/0.278% real.
  Supplemental mu/log_sigma/beta/h_last audit meets rank-Rhat<=1.01 and bulk/tail
  ESS>=400 on all 202 origins (max rank-Rhat 1.000484, min bulk ESS 19,602, min tail
  ESS 33,011, zero retained divergences); full and retained chains coincide. This supports
  reference mixing but does not establish independent-sampler agreement or
  empirical predictive calibration. Weight ESS is concentration only; median
  chain-split MCSE below 1% did not guarantee passing.
- Execution context: all primary warm timing cells ended 16:39:27. A separate
  precision diagnostic co-tenanted cores 0-7 during references 16:54:21-17:23:55.720541;
  its arithmetic ended 17:24:45.905198. Official pooling ran after those jobs drained,
  before build prep was released. Supplemental processing is separate and never
  changes the frozen verdict. Timing omits newest-tick innovation precomputation,
  diagnostics/I/O/caller integration; it is a component metric, not full AMM latency.
- Artifacts: first original outputs `artifacts/official`; full integrity inventory
  `artifacts/execution/inventory-final.json`; global/endpoint diagnostics and shared
  fixed-origin reconciliation `artifacts/supplemental`; source/raw/report manifest
  `CHECKSUMS.sha256`. All raw draws retained remotely and locally outside Git.
  All 2,278 extracted archive files and all 42 shared-snapshot comparisons verified.
  Evidence archive SHA256 `19a89ac0ac401e0700d3140e33e71637658d0cc791a52806dc3eaa38013de595`.
- Conclusion/next decision: K=200/H=10 or 20 is supported for these two fixed,
  growing-history streams. Do not claim K=50 jointly qualifies, fresh-market
  calibration, an executable pricing policy or profitability. Combining with
  WP96's sliding window requires a valid observation-removal/boundary treatment;
  unchanged added-data weights are insufficient. Next test properly marginalized
  predictive functionals on fresh streams with full update-cost and reliability
  checks, preserving this completed study's result.
