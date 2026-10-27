# Studies index

One row per directory under `STUDIES/`. "Preregistered" means a
`PREREGISTRATION.md` or `protocol.json` was committed before the first
evidence cell. Every study has a ledger entry in the
[ledger](research-ledger-2026-08-31.md); the WP code is the entry key.

| directory | WP | preregistered | outcome |
|---|---|---|---|
| `adaptation_parity_v1` | pre-WP22 | yes | Only max depth 10 becomes a default; no single Stan warmup difference helps, and Stan metric regularisation is harmful under delta = 1. |
| [`adaptive_delta_v1`](../STUDIES/adaptive_delta_v1/README.md) | WP49 | yes | Not supported. Inverse-tail rule 1.016x, controller 0.885x; the warmup tail misses `accel_gp`. Fixed-2 control 1.141x but 34 vs 11 funnel divergences. |
| `bridgestan_lifetime_v1` | WP35A | yes | Resident DLL plus joined workers did not meet the zero-fault rule: 8 of 180 fixed-arm children faulted. |
| `bridgestan_owned_worker_v1` | WP35A | yes | The owned one-worker backend met its acceptance criteria: 0 faults in 540 children against 17 for the comparator. |
| [`bridgestan_windows_root_cause_v1`](../STUDIES/bridgestan_windows_root_cause_v1/README.md) | WP50 | yes | Not supported for every hypothesis: 0/300 faults, baseline did not reproduce; leading confound the `libwinpthread-1.dll` copy loaded. |
| [`bridgestan_windows_root_cause_v2`](../STUDIES/bridgestan_windows_root_cause_v2/README.md) | WP50B | yes | Fault reproduced only with the full WinLibs mingw runtime (3/60), 0/180 elsewhere; no single factor implicated (Fisher p 0.123). |
| [`bridgestan_windows_root_cause_v3`](../STUDIES/bridgestan_windows_root_cause_v3/README.md) | WP50C | yes | Static mingw runtime: 0/360 vs dynamic 2/120; unserialised dispatch 3.2x (sblrc) / 4.0x (arK) contended wall with bit-identical draws. Shipped opt-in. |
| [`bridgestan_windows_root_cause_v4`](../STUDIES/bridgestan_windows_root_cause_v4/README.md) | WP50D | yes | Not supported. Static 1/1000 (a sampler nonfinite-position error, not a crash) vs dynamic 4/300 crashes; owned worker 0/300 and stays the default. |
| [`bridgestan_windows_root_cause_v5`](../STUDIES/bridgestan_windows_root_cause_v5/README.md) | WP50E | yes | `NOT_ESTABLISHED`. The WP50D fault replays 6/6 under both dispatches as an integrator overflow; the only cross-dispatch difference is the error-path gradient buffer (fixed). |
| `canonical_v3_scale_noncentered_v1` | WP17 | yes | Full scale non-centering is falsified on every fixture and sampler; canonical-v2 arm V2-A stays the positive result. |
| [`chain_disagreement_warning_v1`](../STUDIES/chain_disagreement_warning_v1/README.md) | WP44 | yes | Mixed. `ChainWarning` ships observe-only: zero step/density false positives in 60 cells, Rule B met (specificity 0.966, sensitivity 1/1); gate-failure sensitivity 0.30. |
| `chain_rescue_v1` | WP33 | yes | `restart_from_best` meets the flip rule (25 of 27 cells); pooling does not. |
| `chain_rescue_v2` | WP36 | yes | 288 cells, mechanical decision `no_rescue`; rescue leaves the defaults. |
| `delta2_sidechecks_v1` | WP37A | yes | Fixed max error 2 fails funnel gates F3 and F4; not qualified for default selection. |
| [`delta_half_default_v1`](../STUDIES/delta_half_default_v1/README.md) | WP42 | yes | Not supported. `delta = 0.5` is 1.385x on the funnel but 0.936x over posteriordb with 38 vs 41 gates; `delta = 0.75` is 0.995x but only 1.142x on the funnel. `delta = 1` stands. |
| [`dense_metric_confirmation_v1`](../STUDIES/dense_metric_confirmation_v1/README.md) | WP51 | yes | Not supported by the frozen rule: 3.21x the diagonal, `diamonds` 98.7x, but 40 vs 43 gates and `gp_pois_regr` 3/3 -> 0/3. The candidate became the dense facade default by a separate engineering decision. |
| [`dense_metric_posteriordb_v1`](../STUDIES/dense_metric_posteriordb_v1/README.md) | WP48 | yes | The shipped `Metric::dense()` was broken (0.082x, 17/51 gates); with the opt-in fixes it is 1.67x (seeded) / 2.59x (Stan) geomean, and `diamonds` 65.7x post hoc with all three. Admission fix merged; no `auto` rule. |
| `eight_schools_v9_rebench_v1` | WP8 | yes | The strict Eight Schools claim survives v9; the published minima were medians. |
| `exact_state_space_ground_truth_v1` | WP4 | yes | Predictions 16/16: the posterior-precision path block mixes at depth 2 to 4; prior-based metrics cap. |
| `flagship_crypto_sv_v1` | WP19 | yes | Zero divergences in 40 cells, fastest walls; the global ridge at T of about 3,000 is the open edge. |
| `flagship_crypto_sv_v2` | WP21 | yes | Zero divergences in 82 cells; 3/3 everywhere only in the labelled 2x-compute pooled tier. |
| `freeze_mode_v1` | WP24 | no (diagnostic, default confirmed by WP25) | Warmup-only `AcceptUnlessDivergent` becomes the sampler default. |
| `funnel_bias_fix_v1` | WP6 | yes | v9 removes the tail-mass bias (z -0.08 / -0.14), retained exhaustions 17 to 0. |
| `funnel_defaults_v1` | WP28 | yes | Eight refinement levels become `Tuning::default()`. |
| [`init_rule_confirmation_v1`](../STUDIES/init_rule_confirmation_v1/README.md) | WP52 | yes | Rule passed: 1.254x, 42 vs 42 gates, funnel |z| <= 1.11, no hide event. `Init::best_of(16)` became the default; the other 14 models are 0.862x. |
| [`init_rule_v1`](../STUDIES/init_rule_v1/README.md) | WP43 | yes | Supported under the frozen rule. `Init::best_of(16)` 72 vs 71 credited passes, 1.258x, no hidden mode; shipped opt-in. `median_of(16)` fails the funnel (z -3.19) and is closed. |
| `invalid_evaluation_parity_v1` | WP10 | yes | v10 removes the no-op transition defect with reference semantics. |
| `joint_default_v1` | WP31 | yes | Rule not met (C2 on two fail-everywhere models); four of five criteria hold; the flip was made post hoc and validated by WP32. |
| `kernel_efficiency_v1` | WP30 | no | `cache_initial_evaluation` (bit-identical) and `MomentumSum` recommended for a preregistered rerun. |
| `kernel_gap_v1` | WP30 | no | `MomentumSum` is the fix for the largest kernel-side gap (0.77x to 0.90x). |
| [`lotka_volterra_stall_v1`](../STUDIES/lotka_volterra_stall_v1/README.md) | WP57 | yes | Mixed. 0/12 stalls at the new defaults vs 4/4 with uniform starts; a secondary-mode trap remains on 2/12 (R-hat 1.59). Neither `best_of(64)` nor an initial-phase depth cap fixes it; the S1 step rule flags 10/10 trapped chains, 0/139 healthy. |
| [`metric_regularisation_scalefree_v1`](../STUDIES/metric_regularisation_scalefree_v1/README.md) | WP41 | yes | Not supported. Scale-free median regularisation is 1.007x (`ScaleFreeStanMedian` 0.949x); 2.06x on `sblrc` but 0.61x on `kidiq` and a funnel z of -3.02. Both stay opt-in; `Stan` stays the default. |
| `neal_funnel_dual_averaging_diagnostic_v3` | pre-WP2 | yes | Preflighted, never authorised or sampled; no results. |
| `neal_funnel_health_pilot_v1` | pre-WP2 | yes | No grid setting passed the health requirements; no selection. |
| `neal_funnel_intervention_pilot_v2` | pre-WP2 | yes | Longer warmup plus initial step search is falsified; no selection. |
| [`nonfinite_policy_requalification_v1`](../STUDIES/nonfinite_policy_requalification_v1/README.md) | WP54 | yes | Rule passed. Bit-identical on 73/73 completed-abort cells; 75 vs 73 runs completed; `RejectLeaf` became the `sampler::Tuning` default. |
| `nonfinite_position_policy_v1` | WP38 | yes | `NOT_QUALIFIED`; the health gate failed on the target for both arms. |
| `numpyro_comparisons_v10_v1` | WP14 | yes | sspd-05 timing claim supported at a corrected 4x; per-work efficiency is parity; NumPyro under-covers the funnel neck. |
| [`nutpie_per_gradient_gap_v1`](../STUDIES/nutpie_per_gradient_gap_v1/README.md) | WP58 | yes | Documentation only. nutpie's 1.70x ESS-per-gradient lead is warmup spend (44 %) and its mass matrix (transplant closes 44–60 %), not accounting (0.15 %) or refinement (5–7 %). Python `init=None` follow-up fix. |
| [`options_flow_v1`](../STUDIES/options_flow_v1/README.md) | application workflow, 2026-10-03 | no | Exploratory uncertainty/precision and Python-interface tests; no broad speed or market-calibration qualification. PyMC nonfinite transport fixed; fixed Fisher geometry failed its screen. |
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
| [`posteriordb_bench_v7`](../STUDIES/posteriordb_bench_v7/README.md) | WP56 | yes | Mixed. Post-WP51–54 defaults pass 43/51 house cells (CmdStan 34, nutpie 26) and 6/15 on five hard posteriors (CmdStan 7, nutpie 3), max passing |z| 3.82, funnel unbiased; release rule not met (0.708x CmdStan per gradient vs 0.75; wall 1.85x). Dense descriptive arm 18/18 at 13.4x. |
| [`posteriordb_breadth_v1`](../STUDIES/posteriordb_breadth_v1/README.md) | WP46 | yes | Shipped defaults on 19 unseen posteriors: 40/42 on the reference tier, 8/15 gates-only; two new failure classes (box-constraint corner traps, silent funnel). No default change. |
| [`python_callpath_v1`](../STUDIES/python_callpath_v1/README.md) | WP47 | yes | Merge rule met. Thread-state pinning (Python callables 1.14–1.90x at threads=4) and `from_jax` without `jnp.asarray` (2.05–2.59x), bit-identical in 102/102 cells; nutpie 1.6–2.4x more ESS per gradient. |
| `rank_two_projected_gaussian_v1` | pre-WP2 | yes | Diagnostic; see ledger. |
| `rank_two_projected_gaussian_v2` | pre-WP2 | yes | Pooled diagnostic; see ledger. |
| `real_target_path_metric_v1` | WP4b | yes | Arm P 2.8x per call with the globals free, 50 to 200x with them frozen; the residual is global to path coupling. |
| `refinement_role_v1` | WP34 | yes | No arm meets the rule; `da-d2` near miss at 1.070x; the leaf-error distribution is one smooth population. |
| [`rescue_removal_paired_v1`](../STUDIES/rescue_removal_paired_v1/README.md) | WP61 | yes | Attribution only. Reinstalled `restart_from_best` is 1.023x, not the cause; seed variation explains 0.848 -> 0.708, and a 3-seed per-gradient figure is too noisy for a 0.75 release gate. |
| `reverse_coarsening_order_v1` | WP37B | yes | Paused at 72 of 84 cells after a target fault; `KEEP_FINEST_TO_COARSEST`. |
| `reverse_coarser_policy_v1` | WP39 | yes | `ZeroWeightBeyond` exact but 0.981x; step confound identified. |
| `reverse_coarser_policy_v2` | WP39B | yes | 0.878x; truncation hypothesis not supported with or without the step confound. |
| `sblrc_process_stability_v1` | WP35 follow-up | yes | The silent post-sampling fault reproduced in 1 of 46 children. |
| [`silent_funnel_diagnostic_v1`](../STUDIES/silent_funnel_diagnostic_v1/README.md) | WP55 | yes | Not supported. Refined-leaf rate sensitivity 0.667, specificity 0.718; nothing ships. 11 of 12 wrong cells had zero divergences; all 12 failed R-hat/ESS. |
| `sspd11_confirmation_v1` | WP12 | yes | Arm I confirmed on sspd-11; arm P 2/3, not confirmed under the conjunctive rule. |
| `sspd11_refreshed_block_v1` | WP16 | yes | Arm P confirmed 3/3 at 4,000 draws; per-window refresh not confirmed. |
| `sspd_target_fatal_diag_v1` | WP37B follow-up | no | The fatal target error reproduces at initial step 0.5 and is fixed at 0.1. |
| [`start_rule_paired_v1`](../STUDIES/start_rule_paired_v1/README.md) | WP60 | yes | KEEP. Best-of-16 is 1.061x uniform paired on six models, not the cause of the v6 -> v7 drop; gates 15/30 vs 18/30, `hmm_drive_0` second-mode chain on 2/5 seeds, named by `chain_warnings`. |
| `step_collapse_v1` | WP27 | yes | Stan regularisation fixes `sblrc` (9.7x) but drops `earnings` gates; stays opt-in. |
| [`thread_scaling_v1`](../STUDIES/thread_scaling_v1/README.md) | WP45 | yes | Mixed. Draws bit-identical across every thread count; contended C=16 speedups 4.6x / 3.9x / 2.8x, capped by contention and the slowest chain. Budget-CAS fix F1 not merged (0.92 at C=T=1). |
| `uturn_default_v1` | WP26 | yes | `MomentumSum` alone is not the default: three of four criteria fail. |
| `warmup_gap_diag_v1` | WP40 | no | None of four warmup levers meets the bar; the gap is warmup gradients from single-leaf step crashes. |
| [`warm_drift_v1`](../STUDIES/warm_drift_v1/README.md) | WP96 | yes | No K=200 frozen/re-adapted policy qualifies over 2,000 fixed-window updates; re-adaptation increases cost without fixing precision. |
| [`amm_predictive_review_v1`](../STUDIES/amm_predictive_review_v1/README.md) | Diagnostic | no | Predictive-functional oracles and archived-draw audits; analytic scale CDF helps but does not rescue WP96. |
| [`predictive_mcse_diagnostic_v1`](../STUDIES/predictive_mcse_diagnostic_v1/README.md) | Diagnostic | no | Exact stationary Gaussian-chain experiment: short correlated-chain tail MCSE and Wald coverage can be substantially optimistic. |
