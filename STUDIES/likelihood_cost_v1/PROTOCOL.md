# Expensive likelihood mechanism test, frozen 2026-10-29

Question: does WALNUTS's lower target-evaluation count become a measured speed
advantage when a common density/gradient becomes more expensive? This is a
controlled mechanism test, not proof of a practical application advantage.

Two real dense likelihood calculations: Gaussian regression with 24 coefficients,
64 or 2,048 independently generated observations, X_ij~N(0,1/n), a standard
normal coefficient prior, and unit observation noise. Generate one fixed
dataset per size, retaining deterministic seeds and data hashes. No artificial
sleeps, repeated dummy terms, or duplicated arithmetic. The full evaluator
computes both dense X*theta and X.T*residual on each call, using single-thread
BLAS. It is shared by both engines through tested native ABIs.

To hold posterior geometry fixed, analytically compute its Gaussian mean and
Cholesky factor L; theta=mean+L*z(q), where z is the inverse curvature5 pair
transform used in the previous dimension24 study. This affine normalization
uses known analytic structure and is charged to all arms. Both transformations
have constant Jacobian. The exact posterior in q is therefore the same curved
known-truth target at both likelihood sizes, up to floating-point differences.
Report this deliberate construction, not an arbitrary nonlinear application.

Five frozen arms: full WALNUTS accept .90/error1 (prior calibration selection),
full NUTS .99/gradient diagonal, full NUTS .99/low-rank, sufficient-statistic
collapsed NUTS .99/diagonal in q, and collapsed/reparameterized NUTS .99/diagonal
in z. No tuning on these new seeds. Optimized controls are essential: Gaussian
regression permits an analytic solution, so a win over its full evaluator
cannot establish practical uniqueness. Exact IID draws are tested as truth;
no claim that MCMC is needed for this regression.

Eight fresh sampler seeds per arm and size, four sequential chains, 750 warmup,
6,000 retained draws, maximum depth ten: 80 fits. Fixed budget avoids restart
ladder artifacts. Deterministically shuffle all jobs to interleave engine and
size. No favorable-case exclusion or retry. Retain raw double-precision draws
and all failures. Compare every arm, not only a slow NUTS configuration.

Use the previous all-pair exact functionals and thresholds unchanged: uniform
means .015 error, first three coordinate .05-tail probabilities .01, every-pair
joint .02 and centered product .005; MCSE <=half error tolerance. All raw and
functional R-hat<=1.01, bulk/tail ESS>=400; zero retained divergences/depth hits.
Map reparameterized draws to q before identical diagnostics. Eight seeds give
limited uncertainty; paired successful-only ratios must display pair counts
and failures. Bootstrap 10,000 medians; descriptive intervals, not broad proof.

Candidate mechanism support requires >=7/8 qualifying WALNUTS seeds at the
larger size, no fewer than either full NUTS arm, and >=1.5 median matched kernel
plus materialization speed ratio over BOTH full NUTS arms, with lower 95%
bootstrap bounds >1. Report cold total time, data/precompute, compilation,
sampling, diagnostics and target calls separately. Show the small-size result
and both optimized controls even when they erase the advantage.

Dataset seeds755100000+n; sampler765000000+case*1000000+config*10000+rep*100;
tests775000000 and offsets; schedule785000000; bootstrap795000000. Data are
different across sizes but analytically normalized posterior geometry is fixed.

Existing EC2 only, twelve exclusive one-core jobs, BLAS threads1, 300s/1GiB RSS/
32MiB output per fit. Admit only above 1GiB free disk and within one hour.
Drain every process group, preserve source hashes and failure receipts. A
previously verified redundant pivot transfer tar is removed after rechecking
its local and remote SHA256; original evidence remains. Stream final backup
to avoid a duplicate tar on EC2. No deployment, trading or global-default change.
