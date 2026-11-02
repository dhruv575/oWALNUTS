# Algorithmic speedup investigation

Four bounded research pilots: exact grid GP algebra, blocked Gaussian-field
sampling, exact-corrected cheap physics proposals, and frozen nonlinear
transport. These are isolated study implementations, not production defaults.

Read PROTOCOL.md and the labeled followup/repair notes before interpreting
results. `analysis01/RESULTS.md` summarizes every completed configuration,
including failed statistical gates. Launch failures are preserved separately.
No spatial heldout data is used. Physics uses the existing qualified quadrature
reference only for evaluation, never for transport training.

## Reproduction

The existing Linux EC2 lane is
`/home/ubuntu/lanes/algorithmic-speedups-20261101`. Spatial jobs use
`/home/ubuntu/venv/bin/python`; physics jobs use the previously installed
`/home/ubuntu/lanes/unified-readiness-20261027/installation02/work/env/bin/python`.
The latter environment has the older nutpie constructor used by backend.py;
the former requires shared_var_keys as supplied in grid_backend.py.
BLAS is limited to one thread per process. Native spatial chains reserve four
CPU slots per job; physics uses one. See dispatchers for resource limits.

Build isolated native libraries with:

```sh
g++ -O3 -std=c++17 -fPIC -shared physics.cpp -o pendulum.so
g++ -O3 -std=c++17 -fPIC -shared \
  -I/home/ubuntu/.bridgestan/bridgestan-2.9.0/stan/lib/stan_math/lib/eigen_3.4.0 \
  grid_native.cpp -o grid_native.so
```

Run grid_preflight.py, grid_stan_check_v2.py and grid_native_preflight.py before
the corresponding sampling workers. The original compiled Stan comparator
depends on the existing spatial-counts-preflight-20261030 lane and
`LD_LIBRARY_PATH=/home/ubuntu/lanes/gp-portable-runtime-20261030/models`.
The frozen physics preparation must precede workers. Campaign scripts create
fresh directories and intentionally refuse to overwrite prior runs.

To rebuild summaries from downloaded evidence:

```sh
python analyze_pilots.py evidence01 analysis01
```

## Interpretation

The symmetric covariance root changes whitening coordinates while preserving
the mathematical physical GP posterior, including the original diagonal
jitter. The rho derivative uses the square-root Sylvester equation rather
than differentiating potentially unstable eigenvectors. Near-singular kernels
still require numerical scrutiny; both initial and repaired conversion checks
are retained. Independent dense-root and compiled-Stan checks are distinct.

The blocked sampler uses valid elliptical-slice field updates and an adapted-
during-warmup-only Metropolis hyperparameter step. A bracket cap fails the job.
Fast completion does not establish useful sampling: poor mixing rejects it.

The physics map is globally invertible with a cubic conditional mean and
constant positive scale. Its Jacobian and derivative are included in the
native target. Delayed acceptance always applies the full nonlinear target
correction. Training uses separate proposals and is charged to each mapped
run. Draw-count changes in the precision followup are explicitly labeled;
they estimate cost at the chosen accuracy gate, not a universal speed ratio.

Raw draws remain in the evidence archive and AWS lane, with source hashes,
supervision, seeds and failed logs. Compilation is a separate one-time cost;
worker timings include imports and diagnostics but not compilation. Physics
worker totals additionally charge shared mode preparation and map training.
