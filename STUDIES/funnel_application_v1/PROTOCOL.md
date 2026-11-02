# Unknown-scale hierarchical binomial pilot

Question: does WALNUTS reach reliable hierarchical uncertainty more efficiently
than tuned native NUTS after allowing reasonable model rewrites? This is a
synthetic mechanism/application-class pilot, not a real-world outcome claim.
Earlier pivot_screen_v1 hierarchical A/B used fixed prior scales, so did not
test learned-scale funnel geometry. Preserve its negative application results.

Two fixed 12-group datasets: weak counts n=[5]*12 and mixed counts
n=[5,5,10,10,20,20,100,100,1000,1000,10000,10000]. Generate latent logits from
N(-2,.05^2), then binomial outcomes, PCG64 seeds956000001/2. No regeneration.
Inference: mu~N(0,2^2), tau~halfNormal(0,1), theta_j~N(mu,tau^2),
y_j~Binomial(n_j,sigmoid(theta_j)). Parameterize tau by log tau with Jacobian.
This models pooling/heterogeneity uncertainty across conversion or failure-rate
groups; the generator's small scale is disclosed, not an estimated real effect.

Compare both native engines under centered, noncentered and hybrid coordinates
(center groups with n>=1000, noncenter the rest). The physical posterior and
physical starting states must match across parameterizations. Both engines get
acceptance .90/.99, diagonal mass, depth11; WAL max_error1 and default refinement
cap. No engine-specific tuning search enlargement. One calibration seed per
case:956100001/2, four chains,750 warmup,1000 retained. Select each engine's
case-specific configuration by pass first, then minimum bulk/tail ESS per kernel
second; all failures remain visible. Two fresh validation seeds per case,
956200011/12 and956200021/22:1000 warmup,4000 retained. Run validation serially
in alternating engine order; report calibration, imports and analysis costs
separately as well as kernel time and target calls. Two seeds are exploratory.

Independent reference: integrate each conditional logit with adaptive Gaussian
quadrature, then population mean and log scale with two-dimensional quadrature.
Split logtau domain [-16,3] exactly at log(.1) and log(.5). Levels are
(logtau Legendre nodes per segment, mean Hermite nodes, logit Hermite nodes)
=(32,32,24),(48,48,40),(72,64,64). Mean proposal center/scale comes from
pseudocount logit precision, conditional on tau; logit proposal comes from its
strictly concave conditional mode/Hessian. Correct all proposal densities.
Check final two levels: log normalizers <=1e-4, means <=.002 reference SD,
SDs <=.005 relative, pooling probabilities <=.001. Also compare expanded
domains logtau[-20,3.5] and mean proposal width multiplied1.25, using final
orders. Domain/quadrature failures block accuracy claims, not weaker gates.

Functionals: mu,tau,all12 logits,all12 probabilities, P(tau<.1),P(tau<.5).
Sampler gates: finite, Rhat<=1.01, continuous bulk/tail ESS>=400, no divergences
or depth hits; mean error<=max(.05 refSD,4MCSE), MCSE/refSD<=.05; each pooling
probability error<=.02 and MCSE<=.01. Diagnose in common physical coordinates.
Accuracy, convergence and cost are separate. Zero divergences alone is not proof.

Cheap controls: reference marginalization itself, and Gaussian Laplace in
noncentered coordinates (finite stationary mode, positive Hessian without
clipping; 8192 draws, seeds956300001/2). Compare its functional fidelity without
calling the approximation exact. No unique sampler claim if rewriting or
integration solves the problem competitively. No artificial likelihood delays.

Gradient/coordinate-Jacobian/ABI checks must pass before sampling. Freeze source
and data hashes. Existing EC2 only, at most4 calibration workers, serial
validation,900s/2GiB per job, total lane<=28MiB, root disk floor1GiB. Current
headroom is tight: reserve full28MiB before launch. Retain raw draws, failures,
references and all configurations. No cleanup, new resources or deployment.

Primary methodological context:
https://mc-stan.org/docs/2_39/stan-users-guide/efficiency-tuning.html
https://arxiv.org/abs/0708.3797
