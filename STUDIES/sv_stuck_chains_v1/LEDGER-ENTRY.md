### WP89-SV-STUCK-CHAINS-V1: the frozen SV chain is a stiff high-sigma start (log_sigma > 1.3) whose first transitions are rejected, whose step collapses under the identity metric and whose first metric update installs the regularisation floor on every coordinate; nutpie escapes through its gradient-scaled initial metric; the WP67 restart rule at ratio 0.01 took 8/480 trapped chains to 0/480 with every rule held and is proposed (not flipped) for confirmation

- **When and where.** 2026-10-26 on `wt/sv-stuck-chains`, preregistered at
  `0d88b8f1` (harness and the research `with_check_window` at `23785f41`,
  base `522a6c84`). Lane 1 (pinned, co-tenanted), 18:46-20:27 UTC; the WP84
  SV target and data (250 returns, 253 coordinates) at 4 x 1,000/1,000;
  Part A 120 seeds x {nutpie, CmdStan, defaults}, Part B 9 arms x 60 seeds,
  Part C 3 candidates on the A seeds; funnel 30 seeds, three house models
  x 3 seeds; 1,416/1,416 cells, no reruns, no errors; one post-run
  analysis-only fix (the funnel cells' key names) and the draw-stripping
  step, no cell or rule changed.
- **Mechanism (Q1).** Trapped chains / 480: nutpie 0, defaults 8 (8/120
  cells), CmdStan 17. All 8 (and CmdStan's 17) started at log_sigma 1.3-2.0
  (no trap lower; 8 % of defaults' chains start there); max |gradient|
  2.5e7 against 1.5e3 at the mode; the first transitions are rejected, the
  step is below 1e-4 by transition 5-6, and the update at transition 99
  installs the Stan floor (mass 6,000) on 100 % of coordinates (8/8),
  leaving the chain 1,000-4,300 nats below the mode at 807k warmup
  gradients against 171k. The warnings named all 8 (0 missed, 0 false).
  Three near-traps with the same signature escaped at transitions 150-325.
- **nutpie (Q2).** Its initial metric mass_i = clamp(|g_i(start)|) alone,
  with the defaults' starts, gives 1/240 (`nutpie_init`); `normal` 1,
  `median16` 0, `uniform` 2, `small_step` 2, `grad_metric` 4,
  `early_windows` 5, `unit_reg` 5 (and final step 0.004 vs 0.12 on every
  healthy chain), `stan_search` 8 of 240. nutpie's step is 0.34 from
  transition 0; CmdStan's uniform starts trap more than the defaults.
- **Candidates (Q3), each 0/480.** R1-R5 held for `restart` (ratio 0.1 at
  t=99), `guard-0.01-0` (0.01 at 99) and `guard-0.01-1` (0.01 at 149):
  110/110, 110/110, 111/111 unfired cells bit-identical, 31/31 fired cells
  with untouched chains bit-identical, funnel P5 0.0502-0.0503 +- 0.0013
  (exact 0.0478), house passes 6/5/5 vs 5. `restart` fired on a healthy
  funnel chain (8903004, ratio 0.076; P4's funnel clause failed) and on a
  failing `earnings` cell that then passed; the 0.01 guards fired on the 8
  traps and 1-2 near-traps only. Predictions: P1, P2, P3a, P3d, P5 held;
  P3b, P3c and one clause of P4 did not.
- **Decision.** No flip. `guard-0.01-0` is proposed for a confirmation
  study (v7 posteriors x fresh seeds vs `defaults`, bit-identity on every
  unfired cell); `guard-0.01-1` is the equal alternative. Library:
  `TrappedChainRestartConfig::with_check_window` (research, default 0,
  bit-identical, tested); no default changed.
