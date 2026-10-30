# Exact duplicate-evaluation mechanism screen

Observation only: always execute the target and record the result. No cached
values are returned. Keys are complete IEEE float64 coordinate bit patterns;
outputs include log density and all gradient bit patterns. Signed zero remains
distinct. Nonfinite inputs/outputs and target errors are reported separately.
Record at most32768 unique finite positions per chain, reset between chains.
Continue detecting hits on stored keys after capacity fills; report dropped
new-position calls and label observed duplicates a lower bound when truncated.
Reuse-lag bins count successful target calls, including nonfinite results but
excluding error returns. No approximate-coordinate reuse.

Cases: all five recoverable targets at native-step factors1 and4, using exact
preserved inputs from matched_geometry01 and step_ladder01. These are exposed
mechanism cases, including posterior failures. Run audit disabled and enabled
and compare retained draws, divergences, steps, masses and actual target calls
against each other and the preserved old runner. Ignore wall times for parity.
No changed posterior claim. Each case is bounded180s/2GiB/64MiB, one at a time.

Unit checks must distinguish signed zero, detect altered outputs at repeated
positions, enforce capacity, and account for nonfinite evaluations. A cache
implementation is worth a separate experiment only if all10 cases preserve
parity and have zero repeated-output mismatches, and at least two targets show
observed duplicate fraction>=.20 at factor1. Factor4 diagnoses refinement work,
but cannot alone justify an optimization of an inefficient configuration.
If coverage truncates, do not claim an upper bound on unobserved duplication.
No observed duplicate fraction is a measured runtime gain or novelty claim.
