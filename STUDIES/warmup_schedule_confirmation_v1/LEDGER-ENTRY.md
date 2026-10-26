### WP77-WARMUP-SCHEDULE-CONFIRMATION-V1: neither WP73 warmup candidate confirms on fresh seeds; the default warmup stays

- **Ordered time:** 2026-10-26 on `wt/warmup-confirm`, lane 2 (cores 4-7) of the shared box.
  - Preregistered at `a1d3a738` after a disclosed smoke run on the non-study `kidiq-kidscore_momiq`.
  - One run, 03:59–05:03 UTC, with no reruns and no amendments.
- **Protocol:** `STUDIES/warmup_schedule_confirmation_v1/{PREREGISTRATION.md,protocol.json}`.
  - 17 house models x seeds 770771–770776, 4 x 1,000 draws, replicated dispatch.
  - Arms: the default (warmup 1,000), `half` (500) and `init25` (windows 25/25/50), with CmdStan 2.39.0 as a descriptive arm.
  - Funnel: 30 seeds x 4 x 2,000.
  - Statistic: WP72 form (c), the median of paired per-seed ratios, geomean over models.
- **Outcome:**
  - **`half`** fails G (81 vs 87 passes) and H (headline 1.119 < 1.15). It holds M 1.180, L 1.098, D, Z 3.38 and F (0.0487 ± 0.0048).
  - **`init25`** fails H 1.016, M 0.988, L 0.980, Z 5.85 and F (0.0530 ± 0.0051). It holds G and D.
  - Per sampling gradient: `half` 0.875, `init25` 1.047.
  - Default vs CmdStan: 0.791 per total gradient, 0.829 per sampling gradient.
  - `hmm_drive_0` under `half`: ratio 0.356 and 3 of 6 passes.
- **Decision:** no default change. WP73's robust `half` result did not replicate.
