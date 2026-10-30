# Fresh-data complete workflow cost study on AWS

Four exposed datasets, all seven workflows: raw/affine/bounded WAL dense/.9;
raw/bounded native diagonal/.999; affine native diagonal/.99; repaired wider-grid
conditional importance. Rotate serial order by dataset. Production seeds
950700001+dataset; four chains1100warmup8000retained for MCMC;16384 importance
proposals. Every transformed run regenerates its raw WAL pilot (seed950200001+
dataset,4x1100warmup2000retained), fits K4/ridge10 on first100/chains, constructs
target data. Replayed maps must match the independently qualified pilot map
within relative/absolute1e-10 (Python/NumPy versions differ); retain regenerated
pilot draws/maps and costs. A mismatch fails, never silently uses old maps.
Importance rebuilds its wider .0001 alpha-lower-bound grid and original exact
weight proposal from scratch. Retain all setup/factor/optimization counts.

Use the same24-functional accuracy gates as the preceding studies. Require all
28 fits qualified before comparing cost/precision. Full process time includes
imports, pilot/grid construction, fitting, production, diagnostics and writes;
precompiled libraries and one-time runtime verification excluded and disclosed.
Report time and worst standardized mean MCSE together, not importance-vs-chain
ESS ratios. Fixed budgets do not establish optimal cost at matched precision.
Four exposed datasets and one seed/dataset are descriptive; no population-wide,
application, profitability or novelty claim. Preserve failures and no retries.

Only one scientific job on AWS at a time; BLAS1;600s/3GiB/256MiB per job,
1GiB minimum free disk,28 jobs. Source/dependency hashes frozen. Existing local
sampler validation runs separately and is not timed against this machine.
