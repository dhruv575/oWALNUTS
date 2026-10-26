### WP88-ONLINE-SV-QUOTE-V2: the library warm continuation meets the 2 %/5 % quote bar at K = 200 on simulated data at both N (78 ms / 1.06 s) but not on real BTC returns (83 %); "real-time quote refresh" not claimed

- Ordered time: 2026-10-26 18:59–20:35 UTC, `wt/online-sv-v2` (base `main` `5027bc1e`, WP87 warm
  API); preregistered at `b827ae7b` before any evidence cell (harness `51daf883`, fix `be8ae0f8`).
  Queues A/B/C on cores 4–7 / 8–11 / 12–15 of the shared box, pinned, co-tenanted; 58/58 cells exit 0,
  none rerun, 95 min wall. Seeds 880101–880103; reference 889450 / 890200 / 889500; data 84084
  (sim, WP84's series) and the archived real BTC-PERPETUAL 30-minute bar-close returns (682 bars,
  `real_data.py`).
- Design: WP84 SV model; warm arm = `Posterior::warm_state` + `WarmState::extend_to` +
  `Sampler::run_warm` (bit-identical to the WP84 harness on this model, 4/4 chains, checked before
  the freeze); K in {50, 100, 200}; gated reference 4 x 2,000/20,000 per tick with
  `max_result_bytes_unchecked(2 GiB)` (173 ticks: every tick at sim N = 250, every 2nd on real, every
  5th at sim N = 1,000); accuracy = |P50 sigma_next err| <= 2 % and |P95 err| <= 5 %, stuck chains
  failures, latency 0.4 s / 2 s, pass >= 95 % pooled and >= 90 % per seed, drift <= 0.5 pp per
  seed; baselines oWALNUTS refit (as sampled and gated), CmdStan 2.39.0, nutpie 0.16.8 at 20 ticks;
  Python `sample_warm` extra.
- Outcome: K = 200 PASS at sim-N250 (96.7 %, seeds 97/99/94, median 78 ms, drift within 0.35 pp) and
  sim-N1000 (96.7 %, 100/90/100, median 1.06 s, 100 % under 2 s), FAIL at real-N250 (83.3 %,
  90/78/82, median 309 ms, one drift -0.99 pp without a common sign; largest tolerance met 5 %/10 %).
  K = 100: 81.7 / 83.3 / 59.3 %; K = 50: 54.7 / 58.3 / 39.3 % (latency 19 ms / 0.27 s / 81 ms). No
  stuck chain or divergence in any warm tick; 0.896–0.907 of warm draws inside the reference 90 %
  interval on 27/27 cells; own MCSE of P50 0.9 % (K = 200, sim), 1.25 % (real).
- Gated reference: 173/173 ticks ok; 3 ticks dropped a flagged chain; 1 tick (real) needed the second
  seed; 0 failed both; floor 0.08–0.12 % (P50) / 0.19–0.28 % (P95) median. The N = 1,000 reference
  that WP84 could not run ran at 70 s per tick.
- Baselines (accuracy ceilings, none under the latency threshold): nutpie 100 % accurate, 0 stuck,
  0.92 s / 4.2 s / 1.2 s median; oWALNUTS refit 96.7 / 91.7 / 90 % as sampled (stuck 2 / 1 / 3 of the
  scored ticks, every one flagged by the sampler; gated 100 %), 2.3 / 15.9 / 4.9 s; CmdStan
  90 / 91.7 / 90 % (stuck 6 / 1 / 3), 4.7 / 39.5 / 10.7 s.
- Python `owalnuts.sample_warm` on a C-ABI target (sim N = 250, K = 200): median 71 ms vs 77 ms for
  the Rust cell (0.93x), 97.0 % pass on both.
- Predictions: held P5, P6 (mostly), P8; partial P1, P4; missed P2 (K = 200 passed at N = 1,000),
  P3 (real failed on two seeds), P7 (Python not slower).
- Decision: no "real-time" sentence (rule requires all datasets). README states 78 ms / 1.06 s /
  309 ms at K = 200 with 97 % / 97 % / 83 % within 2 %/5 %, calibrated, no drift. Next: the K that
  meets 2 %/5 % on real returns (above 200; the own-MCSE line predicts it), and a Rao-Blackwellised
  P95 to remove the 0.4 pp low bias of the risk quote.
