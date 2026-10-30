# Frozen importance-correction screen

Exploratory exposed target: public Stan ODE fixture from the prior pilot. No
clinical claim. Eight independent seeds per arm, 4096 and 16384 proposal draws.
Arms: training-only MAP Gaussian; defensive mixture of that Gaussian and a
Student t with five degrees of freedom and scale matrix four times the MAP
covariance, equal mixture weights. Do not select a covariance after results.

Use native value-only log density, including constants; verify density
differences against the gradient backend before running. Preserve nonfinite
evaluations as zero weights and count them. Do not smooth importance weights;
Pareto k is a diagnostic only. Record normalized weight ESS and maximum weight.
Audit value-only versus gradient-backend density differences at the 16 largest
weights and eight evenly spaced proposals. Maximum discrepancy must be <=.001
log-density units for qualification. Preserve samples before this audit.

Functions: all log parameters, their squares, lower/upper tail probabilities
at MAP +/-1.645 marginal Laplace SD (audit01). Reference is the previously
qualified public eight-chain reference, with new-function R-hat <=1.01 and
ESS >=2000. Mean tolerances are .1 reference SD for continuous functions and
.02 for probabilities, plus three reference MCSE. Estimated self-normalized
importance MCSE must be <= half tolerance, weight ESS >=400, Pareto k <.7.
Estimate MCSE from squared normalized weights times squared centered functions.
Treat it cautiously for unstable weights; retain across-seed failures.

This screen asks whether a cheap correction removes the apparent need for
full MCMC on this small posterior. At least 7/8 passes at a budget is required
to call the screen promising; a later fresh study is required for confirmation.
No superiority claim based on selected seeds or unqualified reference functions.
The comparison to old MCMC elapsed costs is exploratory, not a randomized new
timing contest. Gaussian importance sampling can have unstable tail weights;
the defensive mixture is the stronger baseline.

Seeds 905000000 + arm_index*100000 + budget_index*10000 + replicate.
32 jobs, up to 12 exclusive cores, 300s/512MiB RSS/8MiB outputs per job,
1GiB disk admission floor. Freeze sources and all external model/data/reference
dependencies, preserve q and weights, and record terminal process drain.
