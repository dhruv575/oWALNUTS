# Preserved implementation failures

The first global runner failed before preparation because the earlier provenance
script named inspect.py shadowed Python's standard inspect module. Rename it
provenance_inspection.py; run_v2 uses a separate run02 directory. No statistical
results or seeds were observed before that repair. Preserve run.log and run.py.

The first conditional preflight failed at its second point. Its gradient stalled
at2.15e-6; Newton step3.03e-8, decrement4.01e-14. Subtracting objective values near
924 lost the improvement to rounding, and29 halvings produced a zero update.
Full100-iteration history is CONDITIONAL-FAILURE-AUDIT.json. No grid or production
draws were produced, so this is not a failed importance realization.

Version2 changes the line-search arithmetic, not stopping tolerances or scientific
gates. For delta=z_new-z and d=L*delta, compute the objective improvement as
gradient'*delta-.5*delta'*delta-sum(rate*(expm1(d)-d)). For |d|<1e-5 use its
fourth-order Taylor expression to avoid cancellation inside expm1(d)-d. This is
the algebraic objective difference; it avoids subtracting two large totals.
The neglected term is O(d^5), insignificant at this cutoff. Keep max gradient
<1e-7,100 iterations and40 backtracks. All original preflight checks must pass.
Version2 has separate source files and conditional02 output. Planned production
seeds are unchanged because no production run existed. Preserve the failure.

Version2 solves converged, but numerical target parity failed: offset spread
1.42e-5 exceeded1e-6. Latent gradients and proposal density checks passed.
At long length scales the covariance is ill-conditioned; constructing its
Cholesky in NumPy differs slightly from the compiled Stan factor. Preserve
conditional-v2-audit.json with all40 discrepancies. Version3 extracts that
factor from the actual Stan transformed parameter f=L*z using11 unit-coordinate
evaluations, charges every such backend call, and uses it consistently. Keep
the original parity tolerance; do not silently relax it. All preflight tests
rerun in conditional03. No production draws preceded either numerical repair.
