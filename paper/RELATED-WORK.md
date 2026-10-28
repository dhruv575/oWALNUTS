# Related work and contribution boundary

This is a verified starting point, not a systematic literature review. Publication
metadata and abstract-level claims below were checked against primary publisher
or author records on 2026-10-28. Full methodological comparisons remain required.

## Adaptive Hamiltonian inference

Bou-Rabee, Carpenter, Kleppe and Liu (2026), *The Within-Orbit Adaptive Leapfrog
No-U-Turn Sampler*, JMLR 27(113):1–64, introduce within-orbit step-size adaptation
and evaluate it on multiscale targets including stochastic volatility. Therefore
neither WALNUTS itself nor its use on stochastic volatility is a contribution
of this project. [Publisher record](https://www.jmlr.org/beta/papers/v27/25-1452.html).

Our implementation and streaming use must be distinguished from the published
algorithm. Any speed or robustness claim requires faithful same-target controls,
comparable accuracy, and complete computational accounting. Existing warm-path
results alone do not establish that within-orbit adaptation caused a benefit.

## Gaussian latent-path inference

Murray, Adams and MacKay (2010), *Elliptical slice sampling*, AISTATS,
PMLR 9:541–548, introduce a sampling method for models with multivariate Gaussian
priors. Our use of elliptical-slice transitions, including Gaussian conditional
blocks, relies on this established method. The fixed block partition is an
implementation choice and does not establish a new sampler.
[Publisher record](https://proceedings.mlr.press/v9/murray10a.html).

Kastner and Frühwirth-Schnatter (2014), *Ancillarity-Sufficiency Interweaving
Strategy (ASIS) for Boosting MCMC Estimation of Stochastic Volatility Models*,
Computational Statistics & Data Analysis 76:408–423,
doi:10.1016/j.csda.2013.01.002, study centered/noncentered interweaving for
stochastic-volatility inference. Their work establishes interweaving as a
relevant comparator, not a new idea introduced here. The author manuscript was
posted in 2017; the publication year is 2014.
[Author record](https://arxiv.org/abs/1706.05280).

Our augmented Student-t target, fixed persistence, priors and implementation
must be checked against any external package before using it as a same-target
baseline. An interweaving-inspired implementation is not automatically a
replication of that paper's algorithm or reported performance.

## What remains to be established

| Candidate contribution | Current status | Required evidence |
|---|---|---|
| A new inference algorithm | Not established | Distinct method, correctness argument and comparison with prior art |
| Efficient rolling inference under fixed compute limits | Partial engineering evidence | Fair end-to-end controls, posterior checks, held-out evaluation and reproducible costs |
| Predictive value beyond simple controls | Mixed and scope-limited evidence | Untouched data, dependence-aware uncertainty and explicit failure accounting |
| Economically useful inference for AMMs | Not established | Feasible accounting/execution, same decision model across methods and costs |
| Profitability or unique suitability | Not established | Identified economic comparison and robust out-of-sample evidence |

The current evidence supports reporting a reproducible development study with
explicit failures. A submission-ready manuscript still needs a defensible
contribution beyond combining existing methods. The remaining literature review
must cover sequential/rolling Bayesian inference, stochastic-volatility
forecasting, simulation-based calibration and AMM decision economics. Negative
results are part of that assessment, not an obstacle to be omitted.
