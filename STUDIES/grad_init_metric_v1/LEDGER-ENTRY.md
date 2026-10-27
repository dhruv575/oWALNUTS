### WP94-GRAD-INIT-METRIC-V1: the gradient-scaled initial metric (nutpie's initial mass matrix, as a research flag on top of the shipped defaults) does NOT qualify for a default-flip confirmation: it is a 1.15x headline ESS-per-gradient gain (warmup gradients 0.87x, SV warmup 0.56x) that loses 5 house gates (96 vs 101) by sending lotka_volterra / hmm_drive_0 / seeds chains into the wrong mode where the step-ratio guard no longer fires, and alone (no guard) it leaves 4/480 SV chains trapped (the guard catches all 4)

- **When and where.** 2026-10-27 on `wt/grad-init-metric`, preregistered at `e9578cc1` (library `d6985347`
  on base `main` `a042a728`; `b512856a` two pre-existing clippy fixes). Lanes 1-2 of the shared box (two
  cells at a time, cores 0-3 / 4-7, pinned, co-tenanted), 01:15-02:23 UTC; 906/906 cells, none rerun, no
  errors. Smoke on seed 9459901 disclosed before the freeze (Windows and the box; `custom_noop` bit-identical
  to `defaults` / `diag` on 4/4 kinds).
- **Protocol.** `STUDIES/grad_init_metric_v1/{PREREGISTRATION.md,protocol.json}`. Flag:
  `WarmupConfig::with_initial_metric(InitialMetric::nutpie())`, per chain once in `ChainRun::start_from`
  after the start is chosen and before the step search, `mass_i = clamp(|g_i(start)|, 1e-20, 1e20)` (nuts-rs
  0.17.3 `update_diag_grad`; `|g|`, not `g^2`; non-finite -> 1). Arms: `defaults` (guard included since
  WP90), `gradinit` (defaults + flag), `gradinit-noguard` (flag, guard opted out). Part 1: 22 v7 posteriors
  x seeds 9450101-9450106 x 3 arms at 4 x 1,000/1,000 (WP85 gates and tiers); Part 2: funnel 4 x
  2,000/20,000, seeds 9480301-9480330, the three arms on the fixed `x = 0` starts (ruled) plus
  `diag-best16` / `gradinit-best16` on the sampler's starts (reported); Part 3: WP84 SV model, seeds
  9490101-9490222 minus 9490211 / 9490212, WP89 census. Rules R1-R7 conjunctive; no bit-identity rule.
- **Outcome.** R1 **fails** 96 vs 101 of 132; R2 holds, geomean 1.1500, paired median 1.0793 [1.037,
  1.141], range [0.002, 19.6]; R3 **fails**: warmup-gradient geomean 0.874 but gates dropped on 6 models
  (mesquite, gp_pois_regr, hmm_drive_0 x2, one_comp x2, lotka_volterra, seeds; gained on grsm_irt, radon,
  one_comp x1); R4 holds (0 new divergences; 21/22 models equal); R5 holds (gradinit P5 0.04932 +- 0.00262,
  z +0.58; diag 0.04747 +- 0.00200; `gradinit-best16` 0.0450 +- 0.0014, z -2.01, reported); R6 **fails**:
  `gradinit-noguard` 4/480 trapped (starts at log_sigma 1.47-1.98, step 7e-6 to 9e-16 at 99, 816k-876k
  warmup gradients), `gradinit` 0/480 with 4 guard firings (the same chains), `defaults` 0/480 with 15
  firings; R7 holds. Predictions P4, P5, P7 held; P1, P2 (geomean above 1.08), P3 (gate drops), P6 (noguard
  4 > 2; defaults 0 trapped because the guard is now the default) did not.
- **Diagnostics.** SV: healthy step at the first window close 0.065 vs 4e-4, warmup 96k vs 171k gradients
  per chain, wall 1.65 vs 2.30 s per cell; 11 of 15 defaults firings disappear at the cause, 4 remain.
  Part 1: total gradients 120.7M vs 122.3M; warned chains 29 vs 19; gains radon 2.11, accel_gp 2.98,
  eight_schools_centered 1.63, grsm_irt 1.45, kidiq 1.34; losses GLMM 0.53, diamonds 0.89, kilpisjarvi 0.92
  (initial masses up to 1e8), hmm_drive_0 0.93, one_comp 0.93, lotka 0.96. lotka 9450105: fires and passes at
  the defaults (ratio 0.0018), does not fire and fails (R-hat 2.30, two chains in the wrong mode, 936k
  gradients) under the flag: the scaled metric lifts a stuck chain's step above the guard's 1 % cut without
  freeing it. `gradinit` = `gradinit-noguard` bit-identical on 132/132 Part 1 and 30/30 funnel cells.
- **Artifacts.** `artifacts/{cells,summary.json,results-table.md,environment.json,box-logs,smoke}`,
  draws and SV telemetry on the box with sha256 manifests committed, `CHECKSUMS.sha256`.
- **Conclusion.** Supported: the identity initial metric is the cost (and the cause of the SV trap mechanism)
  and a gradient-scaled start halves SV warmup and lifts the house headline 15 %. Not supported: that
  nutpie's rule as stated is safe as a default (a start gradient far from the typical set is not a scale:
  masses of 1e5-1e8, chains in the wrong mode) or that it removes the SV traps alone (4/480).
- **Next decision.** The flag stays research-only; no default changed. A bounded variant (cap on the
  per-coordinate ratio to the median mass, or `|g|` damped toward 1) paired with a guard whose signal
  survives a scaled metric (WP90's two-signal step-and-log-density variant) is the candidate for a new
  preregistration; the funnel `x = 0` zero-gradient floor and the `gradinit-best16` tail deficit (-2.0 s.e.)
  go into its rules.
