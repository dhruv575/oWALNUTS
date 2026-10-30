# RKNF leaf screens: no advancement

The published symmetric embedded flow-error criterion reduced reverse-coarser rejection, but its extra midpoint gradient cost outweighed that benefit in these independent mathematical leaf experiments. No production sampler change is justified by this evidence.

| Target | Matched refinement pressure: score/call ratio, 95% interval | Independently tuned: ratio, 95% interval |
|---|---|---|
| Gaussian | 0.7188 [0.7041, 0.7345] | 0.6666 [0.6666, 0.6667] |
| Banana c5, primary | 0.6004 [0.5919, 0.6096] | 0.7015 [0.6979, 0.7055] |
| Funnel | 0.7644 [0.7442, 0.7867] | 0.7284 [0.7205, 0.7366] |

Ratios compare RKNF with endpoint Hamiltonian error, including all attempted forward and reverse gradient calls and one initial evaluation. Each score is exact-stationary normalized squared displacement times MH acceptance, zero for invalid leaves. These are not full WALNUTS chain ESS, wall-time gains or application value. Bootstrap intervals condition on the selected calibration tolerances and use fresh independent validation phase points.

In the initial banana screen, reverse rejection fell from 21.83% to 11.36%, while mean calls increased from 3.97 to 6.93. With independently selected tolerances, rejection fell from 5.83% to 0.92%, but calls rose from 2.25 to 3.12 and mean movement declined slightly. All accepted-leaf reversal checks passed, including identical selected refinement level. Both frozen advancement gates failed.

The follow-up gave each criterion nine candidate tolerances and 4096 calibration points, then 16384 new validation points per target. Both criteria selected the largest candidate tolerance on banana and funnel. This boundary selection limits the claim: the finite search does not establish a globally optimal tolerance or rule out other macro lengths, norms or targets. In particular, it does not justify permissive tolerances in a full sampler; earlier full-chain permissive-error tests failed tail exploration.

Sources and all inputs, per-point outputs, calibration choices and bounded-worker receipts are preserved. The original study uses 8192 validation points per target. The implementation independently follows the pinned published RKNF formulas but rejects exhausted leaves and uses strict threshold comparisons. It is not a port or validation of the entire published sampler. No novelty claim is made for the criterion.

Next reviewed research direction: inspect whether a symmetric endpoint-only flow-error estimator can avoid the midpoint gradient without sacrificing reversibility or meaningful refinement. Before experimentation, establish its error order and distinguish it from existing energy-range and adaptive-delta studies. Any candidate must retain reverse-coarser checks and pass fresh cost-adjusted validation before full-chain work. If no defensible estimator emerges, return to GP trajectory-length sensitivity with the existing qualified baseline and explicit tail diagnostics.
