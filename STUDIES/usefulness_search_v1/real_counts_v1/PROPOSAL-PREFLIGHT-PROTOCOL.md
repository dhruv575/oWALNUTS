# Conditional proposal correctness preflight

Training data only; no heldout scoring, accuracy or speed comparison. Preserve
wide-grid conditional importance settings from the synthetic study:41x41 grid,
rho bounds.5..20,alpha bounds.0001..10 in log coordinates;95% uniform-within-cell
grid mixture,5% exact hyperprior;90% conditional Gaussian,10% Student t5 scaled
1.5. Newton tolerance1e-7,max100iterations,line search40tries. No retries.

For79 dimensions replace extraction of a compiled factor with79 basis calls
per hyperparameter by one NumPy RBF Cholesky used ONLY to define the proposal.
All final importance weights must use the unmodified exact compiled target in
its raw noncentered coordinates. This proposal need not reproduce Stan's
factor numerically. Its density is normalized in those coordinates regardless.

At16 seeded hyperparameter points (seed951300001,rho uniform2..10,alpha.5..4),
check conditional objective gradient<=1e-7, covariance reconstruction1e-10,
Gaussian/Student mixture density agreement with SciPy<=1e-8, and finite samples.
Build all1681 grid cells once; require normalized finite probabilities and
mixture normalization. Generate64 proposal draws from the fitted grid and
check finite proposal densities. Bound one BLAS1 process180s/3GiB/32MiB.
Record all solve/factor/objective counts and failures. Production proposal
budgets and target-weight/accuracy qualification will be frozen separately.
