# GP lower-tail failure: short trajectories associated with reverse-coarsening stops

All eight instrumented replays reproduce original draws,target calls,divergences and revision exactly. Summed per-transition calls reconcile with retained telemetry on every chain. This is a posthoc diagnosis of exposed fits, not fresh validation or proof of causation. The selected-workflow validation remains failed.

Seed946500006,chain index1 spent159 consecutive retained draws (indices309..467) below the pooled empirical5% length-scale threshold4.42237. It was moving: its longest unchanged-state stretch was4 transitions. The excursion reached rho2.96005. It should not be removed as burn-in or an outlier.

| Metric |159-draw excursion | Other1841 draws in same chain |
|---|---:|---:|
| Mean target calls | 27.101 | 36.702 |
| Mean built leaves | 10.591 | 35.615 |
| Mean macro trajectory length | 1.0681 | 3.5918 |
| Fraction unchanged | 0.20126 | 0.014123 |
| Fraction with accepted refinement | 0.66667 | 0.067898 |
| Reverse-coarser rejections | 146 | 189 |

146 of159 excursion transitions stopped because a coarser reverse trajectory passed (91.8%), versus189 of1841 outside (10.3%). Mean trajectory macro length was1.068 versus3.592; mean built leaves10.59 versus35.62. The frozen chain step was.1008508 and the final dense-mass condition number2259.4. These associations identify a plausible mixing bottleneck; they do not show that the mandatory reverse check is incorrect or may be deleted. Endpoint-based region classification can mix entering,inside and exiting transitions. Mass condition alone is not proof of a bad metric.

Research direction: inspect alternative forward error criteria while preserving the complete reversibility construction. Tran,Kleppe and Bou-Rabee (2026), https://arxiv.org/abs/2610.16506 , investigate this specific problem using alternative error measures. Their repository https://github.com/jihut/locally_adaptive_step_size_hmc is pinned at f2a90e06195f4a5f38cb017e16f7ff1136d5be58 for method/source review. This is prior art, not our invention. Before coding a candidate, compare the paper and implementation, account for extra target evaluations, and verify that the altered criterion fits the existing selection law. State-independent step-size randomization is another established control (https://mc-stan.org/docs/2_36/reference-manual/mcmc.html), not a license for state-dependent uncorrected adaptation.

Next bounded experiment should begin with a leaf-level correctness/cost comparison on known targets, then use fresh posterior validation against original WALNUTS and native controls. Existing reverse_coarser_policy_v1/v2 negative results must remain distinguished from a new error criterion; no old failed rule is being reintroduced. All practical-usefulness and paper-novelty claims remain unproven.

Saved evidence: gp_lengthscale_diagnostic01,gp_tail_replay01,gp_tail_build01; verified local archive gp_tail_replay_archive01. Third-party code was downloaded for review, not executed or installed. Production unchanged.
