# Compute-route result

**The structural route is worth pursuing.** A specialized full-path Gibbs update fits the same robust state-space return model cheaply, and the existing public oWALNUTS route already handles it substantially faster than either tested NumPyro representation in this one synthetic experiment. These are development observations, not a general speed or calibration qualification.

| Arm | Retained / chain | Contained elapsed | All515-coordinate health | Worst endpoint MCSE / interval width |
|---|---:|---:|---|---:|
| Gibbs, initial |4,000|9.20s|pass|2.949% — fails2% target|
| NumPyro centered |4,000|47.13s|pass|1.724%|
| NumPyro associative noncentered |4,000|56.71s|pass|0.820%|
| Public oWALNUTS, corrected target constants |4,000|25.73s|pass|1.720%|
| Gibbs, separately declared follow-up |16,000|21.50s|pass|1.061%|

These are fixed-length development pilots, not time-to-first-passing-tier experiments: the noncentered reference may reach the gate with fewer than4000draws, and an8000draw Gibbs follow-up was not tested. The ratios therefore are not optimized workflow speed ratios.

All used four chains and1000warmup, CPU0, a180-second per-arm timeout and8GiB memory bound. Elapsed is the common hardware-wrapper worker/cleanup measure, including process imports, compilation, sampling, full diagnostics and output. It excludes the enclosing launcher's startup. Complete first-batch launch timings are also retained in `experiment-v1/execution.json`; no costs or failures were overwritten. The first4k Gibbs result is not assigned an equal-precision speed ratio.

At passing health/precision, observed cost ratios versus centered NumPyro are1.83 for oWALNUTS and2.19 for16k Gibbs. Gibbs is only1.20 times faster than oWALNUTS end-to-end: its2.37-second warmup/sampling is excellent, but retaining and checking four times as many full paths costs substantial time. This directly cautions against selling conditional-update speed as end-to-end speed.

The16k Gibbs observation-scale interval is[.28453,.33462], state-scale interval[.08669,.12402], and beta interval[.22444,.28728]. Its observed next-return interval at known future x=0 is[-.93283,.48582]. Across all10reported endpoints, its largest difference from centered NumPyro is1.70 root-sum-squared endpoint MCSE; versus associative noncentered NumPyro it is1.95. oWALNUTS differences are2.29 and0.86 respectively. These are descriptive MC comparisons, not formal equivalence tests; the4k arms reuse predictive random noise and there is only one synthetic target.

The initial oWALNUTS attempt failed before sampling: PyMC's scalar distribution constants produced a position-independent1.014e-6 normalized-density offset, while gradients already matched within3.4e-13. Explicit float64 alpha/nu constants reduced the value discrepancy to1.91e-9, passing the unchanged1e-8 guard. The failed attempt cost7.26contained seconds and remains in `experiment-v1`; the separate diagnosis and corrected run are retained. This was target construction/normalization, not a sampler transition failure. The diagnostic script's initial syntax failure is also preserved.

## Concrete integration recommendation

Start with an exact structured-model capability, not a claim that Gibbs improved the oWALNUTS kernel:

1. Expose the tested FFBS block as a reusable conditional Gaussian state operation, with regular-grid missingness semantics and dense-Gaussian oracle tests. A fully conjugate model can select the specialized Gibbs backend.
2. Build the next richer model with **Gaussian latent return mean + non-Gaussian stochastic volatility**. Conditional on volatility and Student-t mixture scales, the return-mean path still admits exact FFBS. oWALNUTS should update the volatility/global block. Alternatively marginalize the Gaussian path inside a fixed target and run oWALNUTS on the remaining variables; this avoids introducing a mutable-target session contract but requires an efficient differentiable Kalman likelihood.
3. Do not mutate an existing target under continuation. A hybrid transition API needs explicit conditioning-state installation, cache recomputation and fixed valid proposal/adaptation semantics. Test the full joint invariant distribution first on this already cross-checked model, then on the richer model. A speedup with inconsistent conditioning is not useful.
4. In parallel, remove the current single-thread continuation restriction through a separately tested per-chain implementation. This is a general product improvement and does not depend on conjugate market models. Require bit-identical chain paths across thread counts, correct cancellation, and an end-to-end same-precision comparison.

A joint arrival model is also feasible in principle: Pólya–Gamma augmentation makes logistic observations conditionally Gaussian and has established dynamic-model applications ([Polson, Scott and Windle](https://arxiv.org/abs/1205.0310), [Windle et al.](https://arxiv.org/abs/1308.0774)). It could share a Gaussian liquidity state with robust return observations. That extension is not implemented here and needs a validated auxiliary-variable sampler and market data with explicit arrival/availability semantics.

Falsification for the next hybrid prototype: its normalized joint target or conditional draws fail independent oracles; full posterior endpoints disagree with reference beyond explained MC uncertainty; scale/volatility mixing remains poor; or total same-precision workflow cost fails to improve despite a fast path update. The existing stochastic-volatility target is nonlinear and cannot simply be fed into this FFBS implementation unchanged.

`comparison.json` contains every endpoint, diagnostic, cost and source-result binding; `summarize.py` regenerates it. `ROUTES.md` gives the architecture and wiki/core references. All sampling jobs are terminal. No production study or existing36-fit draft was launched or modified.

