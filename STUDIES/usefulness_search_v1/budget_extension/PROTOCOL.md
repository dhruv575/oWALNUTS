# Defensive-importance budget follow-up

The initial screen is exposed: the defensive proposal at 16384 draws passed
5/8 seeds, with three precision failures and one of those also failing mean
accuracy. This extension tests whether more samples close the gap at lower
cost than full MCMC. It is not a change to the original screen or its verdict.

Freeze the same equal Gaussian/Student-t5 mixture and all original functionals,
reference, accuracy tolerances, Pareto-k/weight-ESS gates and numerical checks.
Eight fresh seeds each at 65536 and 262144 draws. No covariance adaptation in
this extension. Seed base915000000, same arm/budget/rep offsets as original.
Success screening rule remains >=7/8 qualified repetitions at a fixed budget.
Report all attempts and actual value-only density, setup and worker cost.
Do not claim a same-run randomized MCMC speed comparison.

Run sixteen jobs on at most twelve exclusive cores, 300s/1GiB RSS/24MiB output
per job, 1GiB disk admission floor. Preserve raw proposals, densities and
weights. This is a bounded extension, not permission to increase indefinitely.
If it succeeds, deprioritize the small ODE example as an exclusive application
for WALNUTS. If it fails, inspect remaining failures before another experiment.
