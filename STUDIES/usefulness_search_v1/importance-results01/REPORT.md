# Exploratory cheap-correction screen

The tail audit found a maximum 10.4 percentage-point Laplace discrepancy on
training-defined parameter-tail events in the qualified public ODE benchmark.
This does not establish an application. Before pursuing full MCMC as necessary,
the screen tests inexpensive importance correction against the same reference.

| Proposal | Draws | Passes /8 | Median density/proposal time | Median worker total |
|---|---:|---:|---:|---:|
| MAP Gaussian | 4096 | 0 | 0.31s | 2.22s |
| MAP Gaussian | 16384 | 0 | 1.23s | 3.17s |
| Gaussian/t5 defensive mixture | 4096 | 0 | 0.31s | 2.19s |
| Gaussian/t5 defensive mixture | 16384 | 5 | 1.22s | 3.17s |

All 32 corrected jobs completed and their dependency hashes remained unchanged.
None reaches the predeclared 7/8 exploratory gate. The larger defensive proposal
has weight ESS at least 2475 and Pareto k at most .664, but some mean/precision
criteria still fail. Do not equate weight ESS alone with accurate functionals.
Both mixture budgets encountered one nonfinite density evaluation across their
eight runs, retained as a zero weight and counted. Numerical density differences
at high-weight and systematic audit points stayed below the .001 bound.

Plain Gaussian weights can be unstable; increasing its nominal sample count is
not evidence of reliability. The defensive result motivates a bounded follow-up
at higher budgets and a training-pilot-adapted proposal, before claiming MCMC
is necessary. Comparisons with previously measured MCMC time are exploratory,
not a new randomized timing contest. The user’s continuing goal remains active.

The original 32-job attempt failed result serialization after saving samples;
it is preserved separately and is not a scientific negative. Source versions,
raw samples/weights and supervision receipts remain in the remote study root.
The corrected worker's remote source retains its original UTF-8 BOM/extra final
newline; the checked-in readable copy differs only in those text encodings.
