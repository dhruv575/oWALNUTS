# Follow-up passive snapshot/curvature audit

The first audit contradicts a single nonlinear-coordinate veto in the regression
cases. Their coefficient-force R^2 values themselves are low. A narrower
mechanistic possibility is changing noise scale multiplying a stable coefficient
precision matrix. Test this directly before designing any policy.

Replay the same 12 exposed auto2 cells with an additional passive stderr record
at current-window observations 1,25,50,100, each chain: selected position and
its already-computed gradient. No new target evaluations during replay. Require
the same full JSON parity (excluding wall time) against the historical cells.
Separate source2/build2/run02; preserve the first audit. Same resource limits.

Offline, evaluate central finite-difference negative gradient Jacobians at every
saved state with h_j=1e-4*(1+abs(q_j)), and half that step. Report full matrices,
symmetry error, step sensitivity and agreement with the recorded gradient.
Charge offline calls separately; never include them in replay parity or speed.
For regression beta blocks and the GP whitened latent block (identified from
model parameter names, not from favorable diagnostics), report trace-scale range,
trace-normalized shape variation, diagonal-normalized condition numbers, and
positive definiteness across all snapshots. Other coordinates remain visible.

This is exposed-data mechanism evidence only. Stable block shape despite changing
scale would explain poor global linear force regression; it would not show that
a block metric helps or justify a default change. Inconsistent/ill-conditioned
numerical derivatives must be reported, not used to claim stability. No new
selection thresholds or efficacy gates are fitted to these states.
