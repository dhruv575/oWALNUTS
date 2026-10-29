# Geometry and matched-accuracy screen

Exploratory mechanism study, frozen before calibration and validation. Prior
negative funnel studies remain negative; this experiment is not their rerun or
confirmation. No application, economic-value or general-purpose superiority claim.

## Targets and truth

Nine fixed targets: 12D standard Gaussian; 12D equicorrelated Gaussian (rho .95);
8D banana with curvature 2; 10D centered funnels with scale SD 1.5 and 3;
the severe funnel in exact noncentered coordinates (standard Gaussian);
12D conditional log-scale 1.5*tanh(2*v); 10D multivariate Student t, df 3;
6D equal mixture whose first coordinate has normal means +/-3 and variance 1.
All are proper and have exact generative samplers and Rosenblatt transforms.
Funnel gradients, transformations and density normalizers are independently
checked; full target definitions and dimensions are in targets.py.

Known truth is assessed through independent uniform coordinates U. Features are
each E[U_i]=.5, lower/upper .05-tail occupancy on the first three coordinates,
joint first-two below-median occupancy .25, and centered product expectation 0.
Absolute tolerances are .015 for means, .01 for tails, .02 for joint occupancy,
.005 for centered product. Each estimated MCSE must be <= half its tolerance.
Every raw-coordinate and feature R-hat must be <=1.01 and bulk/tail ESS >=400.
Require zero retained divergences and zero maximum-depth hits. Missing/nonfinite
diagnostics fail. A failure is retained, never replaced by a new seed.

This is a joint fixed accuracy criterion, not a proof of distributional equality.
IID controls measure its finite-sample pass behavior. Student-t diagnostics use
bounded probability features to avoid requiring nonexistent fourth moments;
raw-coordinate diagnostic stability can still be difficult for heavy tails.

## Calibration and validation

WALNUTS target acceptance .8/.9/.99; NUTS diagonal .8/.9/.99 plus NUTS low-rank
mass adaptation at .9. Both use four sequential chains, maximum depth 10, and
750 warmup. Same deterministic dispersed starts for both. Both call the same
Numba-compiled analytic target through Python; report target calls as well as
time. This controls target implementation but is not a native-backend speed test.

Calibration: two distinct seeds per target/configuration, 1,000 retained draws
per chain; 126 planned fits. Rank configurations by number passing the full gate.
If both pass, use median total cost; otherwise use median worst normalized gate
violation, then median cost. This rule chooses a configuration even if every
configuration fails; selection itself is not success. Preserve all calibration
results and checksum the selected-settings file before validation.

Held-out validation: eight new seeds per target/engine, three independently
executed retained-draw budgets 250/1,000/3,000 per chain, all with 750 warmup;
432 planned fits. All budgets run, regardless of earlier pass/fail. No settings
are changed after validation starts. First qualifying budget defines a replicate's
time-to-accuracy on this coarse ladder; sum all earlier attempts, including failed
ones, to include search cost. Report sampler-only time and actual cold total time
(framework import, target JIT setup, sampling, diagnostics, serialization) separately.
Failures at every budget are right-censored, not assigned a successful time or
excluded from reliability counts. Report pass rates at each fixed budget too,
so a lucky short-run pass is visible rather than silently promoted.

Candidate lead: at least 7/8 held-out ladders reach accuracy, with no material
reliability loss versus NUTS, and a descriptive median paired cost advantage of
at least 1.5x (report total time and target calls separately). Eight seeds and
tuning across targets cannot establish a general benchmark claim. Bootstrap
paired seed-level cost ratios only when both succeed; always show censoring.
Preserve inconvenient controls and the noncentered funnel, since a standard
reparameterization can remove a synthetic advantage.

Laplace control: multistart MAP and finite-difference Hessian on each target,
draw 12,000 approximate independent samples per seed and evaluate the same gate.
It is a single-mode Gaussian approximation, not a mixture-aware approximation.
IID control: exact independent samples at all three budgets and all eight seeds.
Both are truth/approximation checks, not competitors requiring Markov sampling.

## Repeated-target supplement

Fixed independently of static outcomes: correlated Gaussian and banana targets,
six translated targets, smooth shifts .1*t or an abrupt +2 shift from update 3,
four independent streams each (16 streams). Compare WALNUTS WarmSession reuse,
fresh WALNUTS, and fresh NUTS under their frozen target-specific settings.
Warm reuse starts with 750-warmup/3,000-draw initial fit, carries positions and
metric without an oracle position shift, and discards 250 refresh transitions
before retaining 3,000 per update. Cold fits use 750 warmup at every update.
Charge initialization to the whole stream; assess all six updates with the same
accuracy criterion. A warm-versus-cold result is an interface/workflow comparison,
not a fundamental advantage over an equally capable NUTS continuation kernel.
The direct-generative baseline is available for these synthetic targets.

## Resources and preservation

Existing 16-core EC2 instance only. Up to 12 one-core sampler jobs; 120-second,
1-GiB RSS and 20-MiB output cap per static fit. Stop admitting after one hour or
below 1 GiB free disk. Detached process ownership monitor must drain every group.
Use isolated XDG caches. Supplemental controls use remaining cores 12-15 or run
after sampler jobs. Warm stream cap 300 seconds and 64 MiB. Source/config hashes,
raw retained sampler draws, terminal receipts and failures are retained.

Seeds: 605000000 pilot, 615000000 calibration, 625000000 held-out, with target
stride 100000, configuration stride 10000, replicate stride 100 and budget
offset 0/1/2. Controls 635000000, streams 645000000, tests 655100000/655200000,
analysis bootstrap 665000000. Pilot is six disjoint 250-draw cells and excluded
from accuracy claims. Lower-budget failures do not relax the gate.

Tests check analytic gradients against finite differences, likelihood differences
against SciPy distributions, and independent uniform transforms on exact IID
draws. Neither a successful diagnostic nor a fast time alone constitutes success.
