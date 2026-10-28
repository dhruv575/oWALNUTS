# Fixed multi-observation candidate geometry panel

Nine fits: cap in {.5,1,2} crossed with the following ordered data cases:
(a) T=12, all observations exactly zero;
(b) T=250, y_i=.003*sin(.17*i)+.001*cos(.61*i), with i=0 and i=125 set to zero;
(c) T=250, the same unmodified sinusoidal values, required pairwise distinct.
Zero-based indices. Preserve all cases including severe all-tie concentration.
These synthetic fixtures are not prior random draws or empirical observations.

For every fit compare four-chain NUTS (2,000 warmup,4,000 retained,target_accept
.9,maxdepth10,no low-rank/transform adaptation) with four independently seeded
blocked elliptical-slice chains (1,000 warmup,4,000 retained,scalar hyperparameter
blocks then z blocks of at most16). Start NUTS at prior central physical values
mu=2 log(.005),sigma=.2,beta=z=0; slice starts at zero Gaussian-prior coordinates.
Record this initialization difference. Compare common physical mu,log_sigma,
beta,z coordinates, not unlike internal prior transformations.

Fit j=3*cap_index+case_index uses sample seed398135000+16*j, model seed+1,
slice chain seeds+4 through+7. Reserve/audit the whole144-integer interval.
Each fit runs NUTS and then four slice child processes on its assigned four
cores, preserving failures and full traces. Up to four fits concurrently;
assign an available disjoint core group dynamically rather than modulo job
index, to avoid oversubscribing a still-active group.

Per-fit limits:900seconds,4GiB process-tree RSS,512MiB output. Outer limits:
2,760seconds,18GiB RSS,5GiB output. Admission requires6GiB free disk, so verified
redundant archive cleanup is a prerequisite. Preserve every fixed fit and every
failed/incomplete method, without replacement seeds or budget extensions.

Report all-coordinate Rhat<=1.01,bulk/tail ESS>=400, retained divergences and
depth saturation, descriptive mean differences/MCSEs and actual phase costs.
Diagnostically failed slice output is not a reference, even when means agree.
This panel tests candidate geometry; empirical observation validity, prior cap
justification, predictive calibration and economic value remain open gates.
