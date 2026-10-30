# Ensemble proposal validation, frozen before execution

No application experiment until these checks pass. No novelty/default claim.
Seed 940000001. Student density parity against scipy.stats.multivariate_t and
accepted-flux equality: dimensions 1,3,12, four heterogeneous fixed scales,
30 ensembles/dimension, each walker checked. Absolute log errors <=1e-10.

Stationarity: 12000 independent ensembles, four walkers each, initially exact
iid target draws. Apply one complete sequential MH sweep. Targets: 3-D standard
normal; 1-D mixture 80% N(-8,2^2)+20% N(8,0.2^2). The broad low-density mode
has most probability. Fixed scales differ by walker. Check first/second moments,
P(x_0>0), and centered cross-walker product for walkers 0/1. Estimate standard
errors over independent ensembles, not walkers; require all |z|<=4.5. Record
before and after estimates to distinguish random input fluctuations from drift.
A pass establishes a limited implementation check, not mixing or convergence.

Validate bad dimensions, singular factors, nonpositive degrees of freedom,
nonfinite current states/densities and proposal rejection. Ensure caller state
and factors are unchanged. Bound validation to 180 seconds and 2 GiB RSS.
