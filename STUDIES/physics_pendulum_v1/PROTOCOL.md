# Damped pendulum inference pilot, frozen 2026-10-31

Question: can WALNUTS efficiently infer uncertain physical parameters and future
motion, beyond cheap approximations? This is a two-case synthetic benchmark,
not robotics deployment, evidence for large neural world models, or a new
physical discovery. Equations follow MIT Underactuated Robotics, Simple Pendulum:
https://underactuated.csail.mit.edu/pend.html

Dynamics: theta'=v, v'=-c*v-k*sin(theta), initial v=0. Infer identifiable
effective damping c=b/(m*l^2) and restoring coefficient k=g/l; do not claim
separate identification of mass, gravity, length or friction torque. Truth
c=.2, k=2.25; initial theta=.3 and2 radians in two prespecified cases.
Train at .25,.5,.75,1,1.25,1.5 seconds, independent Gaussian angle noise SD.05.
Future observations at2,3,4,5,6 seconds use separately generated noise. PCG64
seeds953000001/2 for training,953000101/2 for future observations. Ground-truth
trajectories generated with independent DOP853 tolerance1e-12. No resampling.

Prior log(c) ~ N(log(.2),.8), truncated to[-5,1]; log(k) ~ N(log(2),.5),
truncated to[-2,2], independent. These are synthetic working priors. Samplers
use unconstrained logits of these bounds with exact Jacobian. Native RK4 with
maximum step.01 integrates the dynamics and analytic first sensitivities.
The same C++ evaluator, gradients, starting points, coordinate transforms and
call counters serve both engines. BLAS1; chains sequential within each worker.
No artificial delays, duplicated likelihood arithmetic or new AWS instance.

Numerical admission: compare RK4 .01 against .005 and independent DOP853 at
truth, prior center and12 seeded interior points. Max angle error<=2e-6rad;
scaled log-density-gradient finite-difference error<=2e-4 at8 seeded points.
Check transformed coordinates, Jacobian and native ABI by short runs of both
samplers; failure blocks main campaign. Linear sin(theta)->theta evaluator must
agree with matrix-exponential solution. Preserve all failures, no blind retries.

Reference and strongest cheap control: tensor Gauss-Legendre integration in
bounded log-parameter space at orders96,160,256, for each case and both nonlinear
and linear dynamics. Integrate normalized prior*likelihood (no logit Jacobian).
Last two orders require log normalizer difference<=1e-4; parameter/forecast
means within .002 reference SD, SD relative error<=.005; future-angle mean
absolute difference<=1e-4 and P(noisy theta(4)>0) difference<=1e-4.
This is numerical convergence, not a rigorous global error bound. A failed
reference blocks accuracy/speed claims; do not extend grid after results.

Common training MAP uses5 deterministic starts. Positive finite-difference
Hessian with mode gradient<=1e-4 admits Laplace and whitening; do not repair
invalid curvature silently. Laplace65536 draws, seed953300000+case/model index,
retains all failures. Count MAP cost. Linear-model quadrature is a separate
model baseline. Two-dimensional quadrature is a viable inference competitor,
not free reference work to omit from practical comparisons.

Calibration: nonlinear cases, both engines, raw/whitened coordinates, acceptance
.90/.99; four chains300warmup/400retained, depth11, WAL max_error1. Shared
training-derived starts. Diagnostic gate: log/physical parameters and five
future angles, rank Rhat<=1.01, bulk/tail ESS>=400, zero retained divergences
and depth hits. Select among passing configurations by kernel time; if none
pass, select smallest max mean MCSE/SD, then lexical order. Freeze selection
before four fresh validation seeds per case/engine,500warmup/1000retained.
Calibration seeds953100000+100*case+config, validation953200000+100*case+rep.
Paired engines share validation seed; different algorithms do not imply paired
random trajectories. Retain all failures and every configuration.

Validation accuracy against qualified quadrature: log and physical parameter
means within .10 reference SD; five future-angle means within .02rad;
P(noisy theta(4)>0) within .02. Mean MCSE must be <=half each tolerance.
Report forecast-angle RMSE against truth and marginal future-observation log
scores only after selection is frozen; never use scores to select settings.
Laplace and linear quadrature must face the same forecast tolerances. Four
seeds and two noise realizations are pilot evidence, not population calibration.

Advancement requires all4 WAL validation fits accurate, no fewer than NUTS,
paired full-cost median speedup>=1.5 with all qualifying pairs faster, and
a verified forecast/uncertainty need unmet by cheap controls. Report kernel,
shared MAP, prediction/diagnostics and total costs separately; include reference
quadrature as a competing workflow. No speed claim if <4 qualifying pairs.

Resource budget: reuse existing pinned Python runtime. Compile/admit300s/2GiB/
16MiB. Each inference/grid job300s/1GiB/8MiB; at most16 concurrent one-core jobs.
Whole campaign2700s/24GiB/256MiB, free-disk floor1GiB, initial free>=1.3GiB.
Heartbeat every15s; exact source/runtime hashes; no automatic failed-job retries.
Preserve completed spatial evidence off-host before dispatch. Final analysis
and raw verification are required before accepting a success claim.
