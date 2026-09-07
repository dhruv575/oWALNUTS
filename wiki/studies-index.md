# Studies index

One row per directory under `STUDIES/`. "Preregistered" means a
`PREREGISTRATION.md` or `protocol.json` was committed before the first
evidence cell. Every study has a ledger entry in the
[ledger](research-ledger-2026-08-31.md); the WP code is the entry key.

| directory | WP | preregistered | outcome |
|---|---|---|---|
| `adaptation_parity_v1` | pre-WP22 | yes | Only max depth 10 becomes a default; no single Stan warmup difference helps, and Stan metric regularisation is harmful under delta = 1. |
| `bridgestan_lifetime_v1` | WP35A | yes | Resident DLL plus joined workers did not meet the zero-fault rule: 8 of 180 fixed-arm children faulted. |
| `bridgestan_owned_worker_v1` | WP35A | yes | The owned one-worker backend met its acceptance criteria: 0 faults in 540 children against 17 for the comparator. |
| `canonical_v3_scale_noncentered_v1` | WP17 | yes | Full scale non-centering is falsified on every fixture and sampler; canonical-v2 arm V2-A stays the positive result. |
| `chain_rescue_v1` | WP33 | yes | `restart_from_best` meets the flip rule (25 of 27 cells); pooling does not. |
| `chain_rescue_v2` | WP36 | yes | 288 cells, mechanical decision `no_rescue`; rescue leaves the defaults. |
| `delta2_sidechecks_v1` | WP37A | yes | Fixed max error 2 fails funnel gates F3 and F4; not qualified for default selection. |
| `eight_schools_v9_rebench_v1` | WP8 | yes | The strict Eight Schools claim survives v9; the published minima were medians. |
| `exact_state_space_ground_truth_v1` | WP4 | yes | Predictions 16/16: the posterior-precision path block mixes at depth 2 to 4; prior-based metrics cap. |
| `flagship_crypto_sv_v1` | WP19 | yes | Zero divergences in 40 cells, fastest walls; the global ridge at T of about 3,000 is the open edge. |
| `flagship_crypto_sv_v2` | WP21 | yes | Zero divergences in 82 cells; 3/3 everywhere only in the labelled 2x-compute pooled tier. |
| `freeze_mode_v1` | WP24 | no (diagnostic, default confirmed by WP25) | Warmup-only `AcceptUnlessDivergent` becomes the sampler default. |
| `funnel_bias_fix_v1` | WP6 | yes | v9 removes the tail-mass bias (z -0.08 / -0.14), retained exhaustions 17 to 0. |
| `funnel_defaults_v1` | WP28 | yes | Eight refinement levels become `Tuning::default()`. |
| `invalid_evaluation_parity_v1` | WP10 | yes | v10 removes the no-op transition defect with reference semantics. |
| `joint_default_v1` | WP31 | yes | Rule not met (C2 on two fail-everywhere models); four of five criteria hold; the flip was made post hoc and validated by WP32. |
| `kernel_efficiency_v1` | WP30 | no | `cache_initial_evaluation` (bit-identical) and `MomentumSum` recommended for a preregistered rerun. |
| `kernel_gap_v1` | WP30 | no | `MomentumSum` is the fix for the largest kernel-side gap (0.77x to 0.90x). |
| `neal_funnel_dual_averaging_diagnostic_v3` | pre-WP2 | yes | Preflighted, never authorised or sampled; no results. |
| `neal_funnel_health_pilot_v1` | pre-WP2 | yes | No grid setting passed the health requirements; no selection. |
| `neal_funnel_intervention_pilot_v2` | pre-WP2 | yes | Longer warmup plus initial step search is falsified; no selection. |
| `nonfinite_position_policy_v1` | WP38 | yes | `NOT_QUALIFIED`; the health gate failed on the target for both arms. |
| `numpyro_comparisons_v10_v1` | WP14 | yes | sspd-05 timing claim supported at a corrected 4x; per-work efficiency is parity; NumPyro under-covers the funnel neck. |
| `outer_selection_bps_vs_multinomial_v1` | WP3-1 | yes | Biased progressive selection confirmed at 1.745x over exact multinomial; default stands. |
| `paper_adaptation_robust_v1` | post-WP22 | yes | `zero-wide` clears the bar (7/7 models, 1.036x DA) and becomes paper-adaptation v4. |
| `paper_funnel_adaptive_v1` | WP7 | yes | Rule satisfied narrowly by A2 on bulk only; not recommended as a documented default. |
| `paper_funnel_adaptive_v2` | WP9 | yes | `ContinueThroughLocalErrorInstall` qualifies and becomes the paper-mode default; the cumulative statistic is falsified. |
| `paper_funnel_reproduction_v1` | WP2 | yes | The paper's funnel claim did not reproduce at the paper's tuning; the failure is a bias, later fixed by v9. |
| `paper_stock_watson_reproduction_v1` | WP2b | yes | The Figure 16 contrast did not reproduce on a simulated series. |
| `posteriordb_bench_v1` | WP22 | yes | 26 of 51 gates; Appendix C warmup must not become the default. |
| `posteriordb_bench_v2` | WP23 | yes | Integration failures gone (32 of 51); the breadth gap to CmdStan is not. |
| `posteriordb_bench_v3` | WP25 | yes | The WP24 default does what it was built for: 35 of 51, no frozen chains. |
| `posteriordb_bench_v4` | WP29 | yes | Eight levels are free; Stan regularisation alone loses five gates. |
| `posteriordb_bench_v5` | WP32 | yes | Predictions 5/5: 42 of 51 against CmdStan 36 and nutpie 28 at 0.82x CmdStan per gradient. |
| `posteriordb_bench_v6` | WP35 | yes | 45 of 51 on the temporary rescue default; the release rule fails on one |z| cell and one process fault. |
| `rank_two_projected_gaussian_v1` | pre-WP2 | yes | Diagnostic; see ledger. |
| `rank_two_projected_gaussian_v2` | pre-WP2 | yes | Pooled diagnostic; see ledger. |
| `real_target_path_metric_v1` | WP4b | yes | Arm P 2.8x per call with the globals free, 50 to 200x with them frozen; the residual is global to path coupling. |
| `refinement_role_v1` | WP34 | yes | No arm meets the rule; `da-d2` near miss at 1.070x; the leaf-error distribution is one smooth population. |
| `reverse_coarsening_order_v1` | WP37B | yes | Paused at 72 of 84 cells after a target fault; `KEEP_FINEST_TO_COARSEST`. |
| `reverse_coarser_policy_v1` | WP39 | yes | `ZeroWeightBeyond` exact but 0.981x; step confound identified. |
| `reverse_coarser_policy_v2` | WP39B | yes | 0.878x; truncation hypothesis not supported with or without the step confound. |
| `sblrc_process_stability_v1` | WP35 follow-up | yes | The silent post-sampling fault reproduced in 1 of 46 children. |
| `sspd11_confirmation_v1` | WP12 | yes | Arm I confirmed on sspd-11; arm P 2/3, not confirmed under the conjunctive rule. |
| `sspd11_refreshed_block_v1` | WP16 | yes | Arm P confirmed 3/3 at 4,000 draws; per-window refresh not confirmed. |
| `sspd_target_fatal_diag_v1` | WP37B follow-up | no | The fatal target error reproduces at initial step 0.5 and is fixed at 0.1. |
| `step_collapse_v1` | WP27 | yes | Stan regularisation fixes `sblrc` (9.7x) but drops `earnings` gates; stays opt-in. |
| `uturn_default_v1` | WP26 | yes | `MomentumSum` alone is not the default: three of four criteria fail. |
| `warmup_gap_diag_v1` | WP40 | no | None of four warmup levers meets the bar; the gap is warmup gradients from single-leaf step crashes. |
