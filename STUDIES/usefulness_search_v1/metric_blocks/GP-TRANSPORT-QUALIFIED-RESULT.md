# Qualified-input quadratic transport: advance to full-chain test

This exposed-data mechanism diagnostic repairs the old unqualified-pilot objection. It is not fresh sampling validation. The fitting rule is unchanged from the failed earlier transport study; four independent fit/evaluation seed pairs use qualified native GP runs.

| Fold | Quadratic/affine score discrepancy | Cross-entropy change, nat/dimension |
|---|---|---|
| 0 | 0.147551 | -0.104198 |
| 1 | 0.151996 | -0.116167 |
| 2 | 0.139217 | -0.148117 |
| 3 | 0.182558 | -0.110344 |

All four pass the frozen ratio<.8 and cross-entropy increase<=.1 gates. Twelve transformed-gradient and determinant checks pass; worst scaled gradient discrepancy2.58e-5. Diagnostic work:32000 target-gradient and312 density evaluations for the completed attempt, plus the preserved failed attempt and numerical diagnosis. The first finite-difference attempt failed from a small-perturbation discrepancy; a fixed larger perturbation passed without relaxing the threshold. See GP-TRANSPORT-QUALIFIED-REPAIR.md.

Next: implement a compiled transformed target usable by both WALNUTS and native NUTS, verify original-space density/Jacobian/gradient equivalence and coordinate roundtrips, then freeze fresh calibration/validation. Use affine and untransformed controls; include training/pilot work and map evaluation cost, maintain all original GP accuracy and tail gates, and report native transformed performance. All four maps must remain visible; do not select the most favorable fold. The known conditional-importance baseline already succeeds on24 means/SDs and must remain a practical comparator. No sampler or application advantage, generality, novelty, deployment or goal completion follows from this diagnostic.
