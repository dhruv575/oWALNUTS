# Physics pilot implementation frozen before running

Two evaluation seeds 954200001/2; four chains per job. Native NUTS/WALNUTS
use 500 warmup + 1000 retained, acceptance 0.9, depth 11, one CPU.
Compare raw, affine and frozen triangular coordinates under each engine.
Independent Student-t(5) MH and quadratic delayed acceptance use 1000 warmup
+ 6000 retained per chain. All proposals receive exact nonlinear correction.
The transport uses a weighted cubic conditional mean and constant positive
conditional scale fitted to 4096 independent Student-t training draws, seed
954200000. It is globally invertible, with analytic Jacobian and derivatives.
Charge the complete training cost separately to each transported job.
The existing qualified large-angle quadrature is used only for evaluation.
Its established tolerances are 0.1 reference SD for four parameter features,
0.02 for five future-angle means and probability, MCSE <= half tolerance,
and probability MCSE <= 0.01, plus the protocol convergence gates.
Measure both sampling cost and complete worker cost; imports, training and
prediction are material on this small target. This is a pilot, not a scaled
world-model claim. Two replications cannot establish broad superiority.
