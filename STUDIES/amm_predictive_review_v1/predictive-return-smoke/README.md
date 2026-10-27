# Full predictive-return processor: fixture validation only

Prepared for a **single fixed WP97 reference origin**, `ref-real-lo` tick 2.
No WP97 draws have been processed by this package. No sampler or remote compute
was run. A measured one-origin smoke must precede any multi-origin plan.

The processor preserves the joint posterior of mu, log_sigma, beta and h_last,
integrates future Gaussian volatility innovation with 64/128-node Gauss-Hermite
rules, and integrates observation noise through the Student-t CDF. It inverts
the resulting predictive-return mixture for P5/P50/P95. It does not substitute
volatility quantiles for return quantiles, or impute beta into older three-field
archives.

`fixture-results.json` records validation on three fixed small mixtures, each
at three quantiles, against independent adaptive integration. Maximum CDF
disagreement was **2.30e-12**; maximum reported adaptive-quadrature error was
9.11e-13. Two known symmetric conditional distributions also reproduce their
location exactly at the median. Validation took 0.070 seconds locally; this
does not predict the cost of an 80,000-component posterior mixture.

## Bounded processing

`process.py` uses chunked evaluations, cached quadrature nodes, a combined
128 MiB inverse-scale cache limit, dynamic bracketing, numeric root checks, and
a five-minute local deadline checked inside each CDF chunk. This cache limit
does not bound the entire Python process RSS. Unsupported floating-point scale
overflow produces a failed diagnostic rather than an altered distribution.

The fixed-origin input must retain its successful original record and kept-chain
selection. The processor hashes the original record log, protocol and full raw
file; all draws are used. It records 64/128-node disagreement rather than silently
increasing nodes or thinning components. Node agreement is a convergence
diagnostic, not a rigorous integration-error bound, posterior MCSE or accuracy
qualification. Existing output files are never overwritten.

Fixture-only reproduction, writing a new output directory:

```console
python STUDIES/amm_predictive_review_v1/predictive-return-smoke/process.py --validate-only --out NEW_FIXTURE_OUTPUT
```

When the fixed WP97 origin is recovered and verified, the eventual smoke command
is:

```console
python STUDIES/amm_predictive_review_v1/predictive-return-smoke/process.py --study WP97_SOURCE_DIRECTORY --cells WP97_ARTIFACTS_CELLS_DIRECTORY --out NEW_SMOKE_OUTPUT
```

`PLAN.md` records the fixed input, output quantities, failure behavior and
resource ceiling. Results include source/plan hashes, versions, input identities,
CDF/Student-t evaluation counts, cache bytes and local postprocessing times.
This is a research diagnostic, not a production predictive API, market
calibration test, quoting policy or profitability result.
