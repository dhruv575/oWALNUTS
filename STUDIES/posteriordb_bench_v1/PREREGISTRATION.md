# posteriordb benchmark v1 — preregistration

Frozen before execution on 2026-09-01 (see `protocol.json`; its SHA-256 is the
first line of `CHECKSUMS.sha256`). Nothing in this file or in `protocol.json`
is edited after the first evidence cell starts; deviations are appended under
"Deviations" with a timestamp.

## Question

On a fixed breadth set of posteriordb posteriors with reference draws, at
*default settings for every sampler*, how does oWALNUTS (BridgeStan target,
kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`) compare with
CmdStan NUTS and nutpie on ESS per second and ESS per gradient, and — the
decision this study exists for — **is the JMLR Appendix C warmup
(`PaperAdaptationConfig::default()`) at least as good as acceptance-driven
dual averaging on every model, and by how much overall?** The answer decides
whether Appendix C becomes the package default.

## Model set (fixed; 17 posteriors)

Selected from posteriordb `28f8d3d` (stan-dev/posteriordb, cloned 2026-09-01)
for breadth, with the constraint that a reference posterior (10 chains x 1,000
thinned draws) exists. `radon_*` and `dogs-*` were on the wish list but have
no reference draws in this posteriordb revision, so they are replaced by
other hierarchical/latent models (`gp_pois_regr`, `accel_gp`, two HMMs).

| # | posterior | why |
|---|---|---|
| 1 | `eight_schools-eight_schools_noncentered` | canonical hierarchical, non-centered; the existing strict-track target |
| 2 | `eight_schools-eight_schools_centered` | funnel geometry; NUTS is expected to diverge at default `adapt_delta` |
| 3 | `diamonds-diamonds` | 26-dim polynomial regression with strong posterior correlations; hard for a diagonal metric |
| 4 | `earnings-logearn_interaction` | plain regression with an interaction (5 params) |
| 5 | `mesquite-logmesquite_logvash` | log-log regression (7 params) |
| 6 | `kidiq-kidscore_momhsiq` | small regression (4 params) |
| 7 | `sblrc-blr` | Bayesian linear regression (6 params) |
| 8 | `nes2000-nes` | logistic regression (10 params) |
| 9 | `arK-arK` | AR(5) time series (7 params) |
| 10 | `arma-arma11` | ARMA(1,1) with stationarity constraints (4 params) |
| 11 | `garch-garch11` | GARCH(1,1) with a data-dependent constraint (4 params) |
| 12 | `gp_pois_regr-gp_pois_regr` | latent Gaussian process + Poisson likelihood (13 params) |
| 13 | `hmm_example-hmm_example` | HMM with simplex rows (6 params) |
| 14 | `bball_drive_event_0-hmm_drive_0` | HMM on basketball tracking data (8 params) |
| 15 | `one_comp_mm_elim_abs-one_comp_mm_elim_abs` | one-compartment PK model with an ODE solve (4 params) |
| 16 | `hudson_lynx_hare-lotka_volterra` | Lotka–Volterra ODE (8 params); expensive gradients |
| 17 | `mcycle_gp-accel_gp` | brms approximate GP, 66 params; highest dimension in the set |

## Arms (all at their defaults; nothing tuned per model)

* **owalnuts-da** — `StanTarget` (BridgeStan 2.9.0, Stan 2.39.0,
  `STAN_THREADS=true`), Python-package default tuning `h0 = 0.1`, depth 8,
  1 minimum micro-step, 4 refinement levels, `delta = 1.0`, divergence
  threshold 1000; `WarmupConfig::new(0.8)` with adapted diagonal mass from
  identity; four chains on four threads; starts uniform(-2, 2) in
  unconstrained coordinates from a seed-derived RNG (the CmdStan default
  initialisation rule).
* **owalnuts-paper** — identical, plus `PaperAdaptationConfig::default()`
  (`Delta = 2`, `p_a = 0.95`, `Gamma = 0.8`, minimum 10 orbits, per-transition
  step statistic, continue-through restart policy).
* **cmdstan** — CmdStan 2.39.0 via cmdstanpy 1.3.0 `CmdStanModel.sample`
  defaults: NUTS, `adapt_delta = 0.8`, `max_treedepth = 10`, `diag_e`,
  random uniform(-2, 2) inits, four chains run in parallel
  (`parallel_chains = 4`), 1,000/1,000.
* **nutpie** — nutpie 0.16.8 with its BridgeStan backend
  (`compile_stan_model`), `nutpie.sample` defaults (`target_accept = 0.8`,
  `maxdepth = 10`, four chains, all cores), 1,000/1,000.

Every arm: 4 chains, 1,000 warmup, 1,000 retained, seeds 77101, 77102, 77103
(verified absent from `wiki/` and `STUDIES/` before freezing). Run order is
fixed: models in table order; within a model, arms in the order above; within
an arm, seeds ascending. Cells run sequentially; the driver launches nothing
concurrently. Each model is compiled once per toolchain (BridgeStan, nutpie's
own BridgeStan build, CmdStan) before its cells; compile time is excluded from
every wall.

## Metrics (per cell)

Parameter set: the columns of the posteriordb reference draws for the
posterior (constrained parameters plus the transformed parameters posteriordb
stores). oWALNUTS draws are constrained with BridgeStan's `param_constrain`
(`include_tp = True`); CmdStan and nutpie draws are read by name.

* ArviZ 0.23.4 rank-normalised bulk ESS, tail ESS (0.05/0.95), rank R-hat on
  every parameter; `min bulk ESS`, `min tail ESS`, `max R-hat` over parameters.
* Sampling-phase divergences and max-depth stops (all chains).
* Gradient evaluations: oWALNUTS `target_calls_total` (fused value+gradient
  calls, warmup + retained, all chains, including the initialisation call);
  CmdStan `n_leapfrog__` summed over warmup and sampling; nutpie `n_steps`
  summed over warmup and sampling. Sampling-only counts are also recorded.
* Wall: seconds around the single sampler call (`sample_chains_with_target_budget`,
  `CmdStanModel.sample`, `nutpie.sample`) with warmup included. Sampling-only
  wall is *estimated* as `wall x sampling_gradients / total_gradients` for all
  arms (the oWALNUTS facade and nutpie do not expose a phase split); for
  CmdStan the per-chain elapsed times printed in the CSV are also recorded.
* `min bulk ESS/s`, `min tail ESS/s` with warmup included (primary) and with
  the estimated sampling-only wall (secondary); `min bulk ESS per gradient`
  with warmup included (primary) and sampling-only (secondary).
* Agreement with the reference: for each parameter, `z = (mean - mean_ref) /
  sqrt(mcse^2 + mcse_ref^2)` with ArviZ mean-MCSE on both sides, and
  `|mean - mean_ref| / sd_ref`; `max |z|` over parameters is the reported
  figure. A cell is flagged `agreement_flag` when `max |z| > 4`.

## Gates (identical to the prior studies)

A cell passes when max rank R-hat <= 1.01, min bulk ESS >= 400, min tail
ESS >= 400, zero sampling-phase divergences, finite draws, and the sampler
exited without error. Max-depth rate and refinement exhaustions are reported
but not gated (they are visible in ESS).

## Preregistered analysis of the Appendix C question

Per model: `r_grad = median over seeds of min-bulk-ESS/gradient (paper) /
median over seeds (da)` and the same for `r_wall` (min bulk ESS/s, warmup
included) and for tail ESS. "At least as good on model m" means
`r_grad >= 0.9` (10% tolerance for ESS-estimator noise at ~1,000–4,000 ESS)
**and** the paper arm passes the gates on every seed where the DA arm does.
Overall effect: geometric mean of `r_grad` and of `r_wall` over models where
both arms produced draws on all seeds.

Decision rule: Appendix C is recommended as the default if the geometric mean
`r_grad >= 1.0` and it is "at least as good" on every model. If it wins the
mean but loses one or more models, the recommendation is "not by default;
opt-in for hard targets", with the losing models named.

Predictions (written before running): P1 — both oWALNUTS arms pass all gates
on the noncentered eight schools, the regressions (#4–#8), arK, arma and both
HMMs; P2 — CmdStan and nutpie diverge on the centered eight schools at
`adapt_delta = 0.8` while at least one oWALNUTS arm has zero divergences;
P3 — the paper arm has lower total gradient counts than the DA arm on a
majority of models (it targets a fixed unrefined fraction rather than
acceptance 0.8); P4 — CmdStan/nutpie have higher min-bulk-ESS/gradient than
oWALNUTS on diamonds, where depth 8 vs 10 and a diagonal metric dominate.

## Reporting

`artifacts/summary.json` (every cell, every metric), `artifacts/results-table.md`
(per-model table: for each arm the seed-median min bulk/tail ESS/s, ESS per
gradient, gates passed x/3, divergences, max |z|; plus the Appendix C ratio
table), `README.md` (verdict), `LEDGER-ENTRY.md`. Raw draws stay in
`artifacts/draws/` (hashed in `CHECKSUMS.sha256`, not committed).

Failures (compile error, sampler exception, timeout of 45 minutes per cell)
are results and are recorded as such; no cell is rerun, nothing is tuned
after seeing results.

## Load caveat

The machine (Intel Core Ultra 7 255H, 16 threads, Windows 11) is shared with
other agents during execution. Walls are upper bounds on cost; ESS per
gradient is the machine-independent primary figure for the Appendix C
decision, and ESS/s is reported with that caveat.

## Deviations

(none at freeze)
