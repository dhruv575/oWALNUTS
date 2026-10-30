# Triangular quadratic transport diagnostic: no advancement

The pilot-only fit and held-out evaluation completed for all six saved models. No model clears the frozen advancement gate. This is an exposed one-seed-set geometry diagnostic; held-out continuations are temporally adjacent to pilot draws, not independent fresh validation. Production is unchanged.

| Model | Prior native qualified | Candidate/affine score discrepancy | Cross-entropy change (nat/dimension) |
|---|---|---:|---:|
| arma-arma11 | False | 1.0445 | -0.00554 |
| arK-arK | True | 1.9875 | 0.01260 |
| sblrc-blr | True | 1.2792 | 0.00444 |
| eight_schools-eight_schools_centered | False | 0.9302 | 0.09465 |
| garch-garch11 | True | 0.8794 | -0.00161 |
| gp_pois_regr-gp_pois_regr | False | 0.3485 | -0.02621 |

The GARCH score discrepancy improves by12.1%, short of the required20%; other qualified models worsen. GP improves by65.2%, but its saved native posterior was unqualified (R-hat1.060, minimum bulkESS55.6, tailESS17.2 and128 divergences). It cannot provide promotion evidence. Centered eight schools also remains unqualified. ARMA lacks the matched-geometry qualification artifact; it is explicitly unqualified rather than assumed healthy, and its enormous gradient discrepancy remains visible.

The first diagnostic attempt stopped on the missing ARMA qualification file. The repaired attempt preserves that failure and treats missing qualification as false, keeping every target. Model parameters, map, fit, order, ridge and thresholds were unchanged. Inverse, gradient and constant-Jacobian preflight checks pass. A separate post-diagnostic audit recomputed72 target gradients (12 positions per model); every stored gradient matched exactly, including the ARMA examples. This validates the checked storage semantics, not all posterior draws or posterior correctness. No target evaluations were used to fit the map. All affine/nonlinear transformed positions and scores replay exactly from preserved inputs and map coefficients.

The triangular construction uses a globally invertible additive shear with constant positive determinant. It has no modeled conditional variance and is order-dependent; limited pilot size and quadratic feature count can overfit. A smaller Gaussian-score discrepancy is neither an ESS guarantee nor a tail certificate. This experiment does not establish runtime, application value, uniqueness or a useful algorithm improvement. Transport preconditioning is established prior work: https://doi.org/10.1137/17M1134640 and https://arxiv.org/abs/1602.05023 .

Research queue: do not promote this fixed fit or retune its threshold on these outcomes. Investigate the GP failure mechanism separately using its qualified target/reference and existing successful arms before considering any new method. In particular determine whether discrepancies are poor initial conditioning, nonlinear curvature, weak-identification tails, or finite-budget noise; existing dense/Fisher/native controls must stay in scope. A fresh qualification/repair study would require its own protocol and could not retroactively change this gate.

Evidence: quadratic_transport02, failed attempt01, transport_gradient_audit01 and scoped supervisor receipts; verified local archive quadratic_transport_archive01. No off-device claim.
