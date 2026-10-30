# Fresh known-target mechanism screen

Freeze before launch. This is an improvement gate versus plain WALNUTS, not a
competitive comparison with NUTS and not an application demonstration.
Target: first coordinate 0.8*N(-8,2^2)+0.2*N(8,0.2^2), remaining coordinates
independent standard normals. Dimensions 1 and 8. Four walkers. Starts either
all at the broad-mode mean (cold) or three broad and one narrow (covered).
Other coordinates start at zero. No exact target draws are supplied.

16 independent ensembles per dimension/start/arm, seeds 941000001..941000016.
Arms plain WALNUTS, and the same plus one sequential Student-5 MH sweep after
each ten transitions. Fixed identity momentum mass, base step 0.1, depth 10,
max error 1, no adaptation. The same step is conservative for the narrow mode;
this screen tests the ensemble mechanism, not tuning superiority. Proposal
factors are identity, fixed and identical across walkers. 100 chunks, discard
first 20. Local RNG seed base+1000*chunk; proposal seed base+1000000. Pair local
seeds across arms and configurations; each reported configuration has 16
independent ensemble replicates. Do not treat configurations as independent.

Analyze post-sweep ensemble means across the 80 retained chunks: P(q0>0),
q0, q0^2, and for d8 the mean of the other seven coordinates and their squared
values. Ground truth is analytic. Compute Monte Carlo uncertainty across the
16 independent ensemble estimates, never across coupled walkers. Charge all
local, MH and diagnostic target calls; report wall time descriptively only.

Gate for further competitive work: in BOTH initializations and dimensions,
augmented mode-probability RMSE <=0.05, its grand mean within 3 across-ensemble
SE of truth, at least twofold lower RMSE than plain, no other functional RMSE
more than 1.1 times plain, zero callback failures/nonfinite states. Report all
failures and numerical events. Ratios alone cannot certify convergence. A pass
would still require independently tuned strong NUTS and application evidence.

128 jobs, deterministic shuffle seed 941000000; up to eight workers. Per job
600s, sampled 2 GiB RSS and 32 MiB output bound (including result directory).
Admission root >=1 GiB, tmpfs >=2 GiB, available RAM >=18 GiB. Preserve source
hashes, raw draws, failures and exit/process-drain records. No reruns or tuning
after observing results; implementation errors get separate versioned evidence.
