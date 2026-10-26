### WP73-WARMUP-SPEND-V1: the warmup spend gap to CmdStan and nutpie is small (+0.031 and +0.007 share points); all three research schedules pass the frozen rule, but only `half` (warmup 500: 0.80x total gradients, 1.03x ESS) passes robustly

- **Ordered time:** 2026-10-26 on `wt/warmup-spend`, on the shared AWS box, lane 2 (cores 4-7), with three other lanes active.
  - Library commit `ed573c67` adds the research-only, default-off `WarmupConfig::with_stable_metric_stop` and `tests/stable_metric_stop.rs`.
  - Preregistered at `fdafc5b8`, after a disclosed smoke run on the non-study `kidiq-kidscore_momiq`. No code changed after the smoke run.
  - One run, 02:50–03:37 UTC, strictly sequential, one child process per cell; no rerun and no amendment.
- **Protocol/config:** `STUDIES/warmup_spend_v1/{PREREGISTRATION.md,protocol.json}`.
  - 17 house models, seeds 730731–730733, 4 x 1,000/1,000, v7 gates and metrics.
  - oWALNUTS ran on the WP65 replicated dispatch, against CmdStan 2.39.0 and nutpie 0.16.8 (plus `store_mass_matrix`).
  - Candidates:
    - `init25`: windows 25 / 25 / 50;
    - `half`: 500 warmup;
    - `stablestop`: `StableMetricStop(3, q 0.9, ln 1.5, ln 1.5)`.
  - Rule:
    - R1: passes not lower;
    - R2: geomean ESS per total gradient vs default >= 1.10;
    - R3: funnel 10 seeds x 4 x 2,000/20,000, P5 within 1 s.e. of 0.0478;
    - R4: `kernel_fingerprint` passes.
- **Outcome (descriptive):**
  - Median warmup share: oWALNUTS 0.524, CmdStan 0.508, nutpie 0.523.
  - P1 held: oWALNUTS − CmdStan +0.031.
  - P2 failed: gp_pois_regr +0.064 is outside [0, 0.05]; eight_nc +0.003, lotka +0.039.
  - P3 failed: the initial-fast per-transition ratio is 1.24, not >= 1.5. It is still 2–7x on sblrc, arma11, arK, diamonds and hmm_drive_0.
  - P4 held: slow windows 1.01x.
  - Sampling costs 1.04x CmdStan's per transition.
  - nutpie's stored metric last changed at draw 849 of 1,000 on every chain.
- **Outcome (rule):** every candidate passes R1–R4 (default 40/51 passes; R4 kernel_fingerprint 3/3 and stable_metric_stop 4/4 on Linux).

  | candidate | R1 | R2 | R3 funnel P5 ± s.e. |
  |---|---:|---:|---:|
  | `init25` | 43 | 1.440 | 0.0463 ± 0.0017 |
  | `half` | 40 | 1.315 | 0.0499 ± 0.0032 |
  | `stablestop` | 40 | 1.124 | 0.0477 ± 0.0015 |

  The overall prediction ("none qualifies") was wrong.
- **Post hoc robustness:**
  - **`half`:** median 1.25, leave-one-out min 1.21, 1.20 on the 11 models both pass 3/3. Warmup gradients 0.58x, total 0.80x, min ESS 1.03x. sblrc lost a gate and one_comp gained one; one passing cell has max |z| 4.99 (one_comp).
  - **`init25`:** median 1.04; leave-one-out min 1.09 without hmm_drive_0 (118x, where the default had stuck chains on 2 of 3 seeds).
  - **`stablestop`:** median 1.08; 1.08 without eight_schools_centered (fails in every arm). 68 of 204 chains stopped at 500.
- **Artifacts:** `STUDIES/warmup_spend_v1/`:
  - `{README.md,LEDGER-ENTRY.md,PREREGISTRATION.md,protocol.json,run_spend.py,build_models.py,checksums.py,Cargo.toml,Cargo.lock,src/}`;
  - `artifacts/{cells/,funnel/,summary.json,results-table.md,tests.json,test-*.log,build-manifest.json,measured_on.json}`;
  - `CHECKSUMS.sha256`, including the uncommitted draws.
- **Conclusion:** warmup spend is not where oWALNUTS loses to nutpie on the house models; WP58's `hier` gap does not transfer. Every sampler's 1,000-transition warmup is longer than these models need, and halving it is the one robust gain.
- **Next decision (coordinator):**
  - No default change.
  - A preregistered confirmation of a 500-transition warmup (fresh seeds, a robust per-model statistic, the gates).
  - R2-style geomeans should exclude models the default fails.
  - The nutpie gap goes to the metric (WP71).
