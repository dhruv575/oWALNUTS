# The T=1000 state-space line: sspd-10, sspd-11, canonical-v2/v3

## State of knowledge

The state-space line began from the finding that no sampler had ever actually sampled the T=1000 Polyscope fixtures: every earlier "falsified" comparison had two broken arms. An exact Gaussian ground truth showed the failure was the metric, not the sampler, and the real target confirmed that the non-pathological cell sspd-11 is sampled cleanly by a plain adapted diagonal at depth 8 and 2.2 to 2.8x faster per call by a posterior-precision path block. The pathological cell sspd-10 is not sampled by any tested Euclidean configuration, including NumPyro NUTS at depth 12, and is retired as a qualification fixture. Full scale non-centring of the innovations (canonical-v3) is falsified for both oWALNUTS and NumPyro, and the Appendix C warmup passes on the real target with a small gain. The line was later interrupted by the frozen target's fatal classification of reachable non-finite values, which is a target defect rather than a sampler one. Everything here is in the [ledger](../research-ledger-2026-08-31.md).

## Timeline of evidence

- **Programme 2026-08-31** `wiki/research-program-2026-08-31.md`: audit findings that motivated the line. Only JAX gradient parity existed for sspd-10; every T=1000 "falsified" row compared two arms at R-hat 1.5 to 2.2 and bulk ESS below 10. sspd-10 is a deliberately pathological covering-screen cell (strong, near-funnel-zero, contaminated); sspd-11 is the mixed-regular T=1000 cell. Under any diagonal or prior-based metric the path conditional precision has condition number about T squared, so a U-turn needs about T leapfrogs and depth 8 cannot reach it; the 83 percent depth caps were predictable. Decisions: freeze the arrowhead line at stage 7, no further sspd-10 sampling without a ground truth and an external reference, and test a mechanism on T=1000 only after it is predicted and observed on a checkable fixture.
- **WP4** `STUDIES/exact_state_space_ground_truth_v1`: Gaussian local-level path with globals fixed and an exact tridiagonal posterior, T in {100, 1000}, arms I (identity), D (posterior-variance diagonal), P (posterior-precision bidiagonal Cholesky), Q (prior precision only). Cap and no-cap predictions held 16/16. I and D never cap at T=1000 (min bulk ESS about 6,000); P mixes at depth 3 to 4 with min bulk ESS about 18,000 and ESS per call 4.8x I; Q caps 92 to 93 percent with step 0.0026 and R-hat 1.025. Accuracy against truth was at Monte Carlo level. The mechanism clause "the level direction is slow" was wrong: level is the stiff direction, fine-scale modes are slow.
- **WP4b** `STUDIES/real_target_path_metric_v1`: canonical-v2 ported verbatim with oracle parity 4/4 in Rust and JAX; first external reference (NumPyro 0.21 NUTS, depth 12). sspd-11: NumPyro at a=1 passes, at a=0.75 fails narrowly; oWALNUTS I passes at depth 8 with 0.79 percent caps; P passes at 2.8x I's ESS per call; B fails narrowly. sspd-10: every arm fails including the reference (R-hat 1.29 to 1.53, 913 to 1,510 divergences). sspd-05: I passes, the others fail or fail narrowly. With globals frozen the path block is 50 to 200x; with globals free a more accurate block (P2) is worse than P. Conclusion: "any diagonal metric caps at T=1000" is false as a general claim; the residual problem is global-to-path scale coupling.
- **WP12** `STUDIES/sspd11_confirmation_v1`: fresh seeds 91001 to 91003 on sspd-11. Arm I confirmed 3/3 and agrees with NumPyro on every seed; arm P 2/3 (one rank R-hat of 1.0102 on `beta`), efficiency P over I geometric mean 2.735, wall 7 to 9 s versus 24 to 28 s. Stock-Watson arm A robustness 2/3.
- **WP16** `STUDIES/sspd11_refreshed_block_v1`: arm P confirmed 3/3 at 4x500/4,000 (WP12's miss was run length); per-window refresh (arm R) not confirmed and its failure mechanism is variance underestimation in early windows.
- **WP14** `STUDIES/numpyro_comparisons_v10_v1`: the matched sspd-05 timing track on kernel v10 gives 4.03x bulk ESS per sampling second over NumPyro at a per-work-unit ratio of 1.00, so the older v7 figure of 5.4 to 7.3x is retired; the path block has no advantage at T=100. Real-market T=48 passes 3/3 at depth 10 in both parameterisations at 3.2 to 3.8x ESS per second, retracting the last NumPyro-favourable comparison.
- **WP17** `STUDIES/canonical_v3_scale_noncentered_v1`: canonical-v3 with `d_t = mu + sigma_x * eps_t`. sspd-10: every arm fails, NumPyro saturates depth 12 at 100 percent. sspd-11: V2-I passes; V2-A (canonical-v2 plus Appendix C) passes at 1.20x V2-I ESS per call; V3-D fails with `sigma_x` wandering to about 0.98; V3-A froze with every retained transition divergent and exhausted; NumPyro on v3 fails. sspd-05: V2-A passes at 1.02x. Mechanism: v3 likelihood curvature in eps scales as `sigma_x^2 T^2 c`, with top whitened eigenvalue 1e4 to 1e8 at the starts, so full scale non-centring relocates the funnel to moderate and large `sigma_x`.
- **WP37B** `STUDIES/reverse_coarsening_order_v1`: the first state-space cell (sspd-11 at T=1000, seed 96101, incumbent arm) exited at chain 1, transition 1 with "canonical log density or gradient is not representable as finite f64"; 11 state-space cells never launched and the study was archived incomplete.
- **SSPD-TARGET-FATAL-DIAG** `STUDIES/sspd_target_fatal_diag_v1`: at initial step 0.5 the frozen target fails 0/13 diagnostic seeds as frozen and 11/13 with fatal results reclassified recoverable; at step 0.1, 11/13 and 13/13. All 17 failures at transitions 0 to 2. The cause is the target's error classification plus a kernel abort on a non-finite proposed position.
- **WP38** `STUDIES/nonfinite_position_policy_v1`: `NonfinitePositionPolicy::RejectLeaf` completes all 24 runs on the repaired target where `Abort` fails 2/24, is bit-identical elsewhere, but the registered health gate (bulk ESS 400, R-hat 1.01 on nine coordinates in 1,000 draws) fails 0/24 with draws identical to `Abort` on 22 seeds. The gate measured the target's mixing, not the policy. Not qualified; `Abort` stays the default.

## What worked

| change | study | result | why |
|---|---|---|---|
| Exact Gaussian ground truth before touching the real target | WP4 | 16/16 cap predictions held; the Polyscope T=1000 phenomenology reproduced and eliminated | a checkable fixture separates the metric mechanism from the target |
| An external NUTS reference on every fixture | WP4b, WP17 | sspd-10 shown unsampled by NumPyro too; sspd-11 agreement within 3 MCSE | two broken arms are uninformative; one healthy reference makes a cell a result |
| Centred adapted diagonal on sspd-11 at depth 8 (a=1 coordinates) | WP4b, WP12 | passes 3/3 on fresh seeds, agrees with NumPyro | the a=1 canonical-v2 coordinates are the correct production coordinates |
| Posterior-precision tridiagonal path block (arm P) | WP4b, WP12, WP16 | 2.2 to 2.8x ESS per call, confirmed 3/3 at 4x500/4,000 | the conditional path metric removes the T-squared condition number |
| Appendix C warmup on canonical-v2 (V2-A) | WP17 | passes sspd-11 and sspd-05 at 1.20x and 1.02x V2-I | single seed each; a three-seed confirmation was named and not run |
| Real-market T=48 at depth 10 | WP14 | 3/3 in both parameterisations, 3.2 to 3.8x NumPyro ESS per second | zero depth caps at depth 10 against 3.6 percent in the pre-v9 pilot |

## What did not work

| change | study | result | why |
|---|---|---|---|
| Any Euclidean configuration on sspd-10 | WP4b, WP17 | every oWALNUTS arm and NumPyro at depth 12 fail | a deliberately pathological covering-screen cell with a `sigma_x` to 0 funnel; retired as a qualification fixture, kept as a stress cell |
| Prior-precision-only path metric | WP4 | 92 to 93 percent caps at T=1000 | the observation term sets the stiff direction |
| Full scale non-centring of the innovations (canonical-v3) | WP17 | fails at T=100 and T=1000 for oWALNUTS and NumPyro; V3-A froze | curvature in eps scales as `sigma_x^2 T^2`, relocating the funnel rather than removing it |
| A more accurate path block with globals free (P2) | WP4b | worse than P on every fixture | global-to-path coupling, not the block, is the residual |
| Per-window refresh of the path block | WP16 | 2/3, 0.25 to 0.52x the one-shot block | early-window variance underestimation of a slow global |
| The v7 claim of 5.4 to 7.3x over NumPyro on sspd-05 | WP14 | retired; 4.03x wall at per-work parity, no path-block gain at T=100 | the earlier figure did not survive a matched, one-code-path measurement |
| The frozen canonical target's fatal error classification at initial step 0.5 | WP37B, SSPD-TARGET-FATAL-DIAG | 0/13 completions as frozen | reachable non-finite values classified fatal instead of recoverable |
| `NonfinitePositionPolicy::RejectLeaf` as a qualified opt-in | WP38 | completes every run but fails the registered health gate 0/24 | the gate measured the target's mixing; draws were identical to `Abort` on 22 of 24 seeds |

## Current recommendation

Sample canonical-v2 in a=1 coordinates with the adapted diagonal at depth 8 or higher; this is the confirmed product-facing path. Use the posterior-precision path block through the opt-in structured-metric driver for a 2.2 to 2.8x gain when the globals are well estimated. Do not use canonical-v3. Treat sspd-10 as a stress cell with the NumPyro failure as its reference, not as a qualification target. Any renewed state-space protocol must use a repaired, pre-qualified copy of the target and fresh seeds.

## Open questions

- A three-seed confirmation of V2-A (Appendix C on canonical-v2) at 4x500/2,000 with the WP12 gates was named in WP17 and never run.
- Position-dependent geometry (a `sigma_x`-conditioned path-block refresh at slow-window boundaries) or partial scale centring selected from data are the remaining candidates for sspd-10; both need new preregistrations.
- Whether the kernel should treat a non-finite proposed position as a divergent leaf by default is undecided; WP38 showed the mechanism works and the qualification design was wrong, so a paired health gate with fresh seeds is the next design.
- The global-to-path coupling mechanism (arrowhead line) has arm-D pilot evidence only (WP21) and no preregistered confirmation.
