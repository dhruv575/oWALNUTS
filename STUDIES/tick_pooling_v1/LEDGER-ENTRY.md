### WP93-TICK-POOLING-V1: pooling the last H ticks' warm draws as they are does not let K fall below 200; the posterior moves 3.4 % per tick against a 2 % tolerance, so every pooled configuration fails (10–32 %) and only K = 200 without pooling meets the quote rule (95.0 %, 78 ms); post hoc, a likelihood-reweighted pool would let K = 20 with H = 20 (7.9 ms) reach 95 %

- Ordered time: 2026-10-26 23:52–00:29 UTC, `wt/tick-pooling` (base `main` `6dae32bd`, no library change);
  preregistered at `446d0caa` before any evidence cell (draft `ae52d8a1`, pipeline-only amendment `56d49780`:
  the driver creates `artifacts/`). Lanes 1 and 2 (cores 0-3 / 4-7) of the shared box, pinned, co-tenanted;
  17/17 cells exit 0, none rerun, 37 min wall. Seeds 931201–931203 (tick-0 retry 931212 used once), reference base
  939460, re-propagation noise 851000, data 84084 (WP84's series).
- Design: WP84 SV model, N = 250, 100 ticks; warm arm = gated tick-0 fit + `WarmState::extend_to` +
  `Sampler::run_warm` at K in {5, 10, 20, 50, 200}; gated reference 4 x 2,000/20,000 at every tick (adjusted from
  "every 10th": 33 scored ticks cannot resolve a 95 %/90 % rule; 101 ticks cost 19 lane-minutes); quote from the
  pool of the last H in {1, 5, 10, 20} ticks' draws, uniform or exponential (half-life H/2) weights, three readings
  of a stale draw (as-is, re-propagated with fresh noise, re-propagated and likelihood-reweighted); WP88 rule
  |P50 sigma_next err| <= 2 % and |P95 err| <= 5 %, >= 95 % pooled, >= 90 % per seed, drift <= 0.5 pp; 120
  configurations on the same 300 ticks.
- Outcome: PASS only at K = 200, H = 1 (285/300 = 95.0 %, seeds 98 / 96 / 91 %, drift -0.15 / +0.30 / -0.37 pp,
  77.6 ms median, p95 101 ms); every H >= 5 configuration FAILS at every K: as-is 10–32 % (best 32.3 % at K = 200,
  H = 5, exponential), nearly independent of K; prop 3–34 % (P95 biased high +2.4 to +9.5 %); frozen pf 8–92 %
  (unbiased but its cross-pool normalisation swamps the lag-0 draws). Exponential beats uniform on 15/15 as-is
  pairs by 2–7 points. H = 1 reproduces WP88: 13.3 / 19.0 / 33.7 / 53.3 / 95.0 % at K = 5 / 10 / 20 / 50 / 200.
- Stale bias: the gated reference's own P50 moves 3.43 % per tick (median; 27 % of ticks within 2 %), 9.4 % over 5,
  10.1 % over 10, 15.7 % over 20 ticks, signed +0.35 % to +2.83 % (volatility fell over the window); K = 200 as-is pools
  |P50 err| median 3.8 / 6.2 / 7.3 % (uniform, H = 5 / 10 / 20), signed P50 +0.6 / +1.1 / +1.4 %, signed P95 +1.1 /
  +2.2 / +3.3 %.
- Latency (library call, 4 pinned cores): 2.2 / 4.1 / 7.9 / 19.4 / 77.6 ms median at K = 5 / 10 / 20 / 50 / 200; 100 %
  under 0.4 s; own MCSE of P50 at H = 1 7.5 / 4.0 / 2.9 / 1.8 / 0.9 %; pooling arithmetic 0.03–2.6 ms.
- Gated reference: 101/101 ok, 0 second seeds, 7 ticks dropped a trapped chain (WP89 signature, step 1e-5 to 1e-10,
  all flagged by the sampler), min 3 chains, max R-hat 1.0003, floor 0.08 % / 0.20 % median (0.38 % / 0.58 % worst),
  sampler wall 10.8 s median (258 s max). Tick-0 gate: seed 931202 trapped one chain at attempt 0 (17 s), retry clean;
  15/15 cells carried 4 chains; no stuck chain or divergence in any warm tick.
- Predictions: held P1, P4, P9; partial P2, P3, P6, P7, P8; missed P5 (pf did not pass at K = 50; the analysis's
  pool-wide weight normalisation was wrong for mixing lags, disclosed).
- Post hoc (`posthoc/pf_lagnorm.py`, not preregistered, does not change the verdict): with likelihood weights
  normalised within each lag group, K = 20 with H = 20 reaches 95.0 / 95.3 % (uniform / exp; seeds 96 / 96 / 93 %,
  drift within 0.42 pp, weight ESS ~1,000, 7.9 ms), K = 50 passes at H = 5–20 (95.7–97.3 %), K = 200 at H >= 5 is
  100 % with |P50 err| 0.2–0.3 %; K = 5 and 10 stay under 85 %. Weight ESS per lag group 97 % at lag 1, 45 % at
  lag 19 at every K.
- Decision: the README may say "K = 200 per tick with a pool of 1 tick meets the quote rule" (= WP88); no pooled
  configuration earns the sentence. Next: a preregistered confirmation of the per-lag-normalised particle-filter
  pool at K in {20, 50}, H in {10, 20}, with the same reference and rule, and on the real BTC series.
