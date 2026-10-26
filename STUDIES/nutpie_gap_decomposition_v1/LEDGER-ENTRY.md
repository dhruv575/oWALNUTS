### WP80-NUTPIE-GAP-DECOMPOSITION-V1: nutpie's per-gradient lead is sampling gradients per draw (B), driven by a smaller effective oWALNUTS step on every model and by refinement spend on centered Eight Schools; not warmup, not ESS per draw

- **When and where.** 2026-10-26 on `wt/nutpie-gap`, preregistered at
  `b0373e34`. 24 telemetry cells (4 models x seeds 720701-3, both samplers),
  lane 1 (pinned, co-tenanted), no reruns. All 24 are bit-identical to their
  WP72 / WP76 cells.
- **Part 1** (288 + 288 cells on disk). Mean over 15 models: G 0.233,
  A -0.376, B 0.580, C 0.028. Top three by G: sblrc 1.02,
  eight_schools_centered 0.66, hmm_example 0.46. P1 failed: hmm_drive_0 is
  last on the mean of logs because nutpie's ESS collapses on 6 of 18 seeds;
  its median G is +0.73.
- **Part 3.**
  - H1 (step, B1) supported: 0.35 / 0.61 / 0.21, and 2.62 on diamonds.
  - H2 (B2), H3 (metric spread), H4 (B4) and H5 (A) not supported.
  - B4 is 1.38 on eight_schools_centered and about 0 elsewhere.
- **Ranking** by the preregistered mean rule: B4 0.46, B1 0.39, B2 0.22,
  C -0.04, A -0.88. P2 (B1 first) failed and P3 failed.
- **Next decision.** None here (no candidates). The step gap, including
  sblrc's 1/M at about 11x the variance on its smallest scales, is the
  efficiency lead to study.
