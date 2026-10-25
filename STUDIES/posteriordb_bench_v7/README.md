# posteriordb benchmark v7 (WP56): 17 house + 5 WP46 breadth posteriors

## Verdict

**Pending: Phase 2 (the oWALNUTS arm) has not run yet.** Per amendment A0,
the commit under test is the coordinator's hash, or the head of `main` at
06:45 local. Phase 1 is complete, and its results are below.

## Phase 1: competitor arms (complete, 132 cells)

CmdStan 2.39.0 and nutpie 0.16.8 were run at their defaults on all 22
posteriors x 3 seeds (560561–560563), strictly sequentially, 02:44–04:32
local, at commit `af2d364d` (the preregistration freeze). Walls are contended
and are not used as evidence.

| arm | house /51 | new five /15 | all /66 |
|---|---:|---:|---:|
| CmdStan 2.39.0 | **34** | **7** | 41 |
| nutpie 0.16.8 | **26** | **3** | 29 |

v6, on different seeds, had CmdStan at 34/51 and nutpie at 29/51 on the
house set.

New five, per model (gates-only = no posteriordb reference draws, so all
parameter-block coordinates are gated and there is no z):

| posterior | tier | CmdStan | nutpie | how the competitors fail |
|---|---|---:|---:|---|
| GLMM_Poisson | gates-only | 0/3 | 0/3 | slow `sigma`: R-hat 1.04–1.19, bulk ESS 18–92. Chain disagreement 0.12–0.73 sd, zero divergences |
| seeds_centered | gates-only | 0/3 | 0/3 | slow `sigma`: bulk ESS 227–404, tail ESS 135–330, **zero divergences on every cell** |
| kilpisjarvi | reference | 3/3 | 0/3 | CmdStan passes at ~4.4 M gradients per cell; nutpie ESS 337–432 |
| grsm_latent_reg_irt | gates-only | 3/3 | 3/3 | — |
| radon hierarchical_intercept_centered | gates-only | 1/3 | 0/3 | `beta[1]` bulk ESS 233–390, the global-to-local coupling WP46 named |

**P7 (CmdStan >= 8/15 on the new five) failed: 7/15.**

Two Phase-1 observations bear on WP46's taxonomy. They are descriptive and
were not preregistered.

- **The `seeds_centered` "silent funnel" is not specific to oWALNUTS.** WP46
  read the zero divergences on `seeds_centered` as refinement suppressing
  Stan's divergence warning. Here CmdStan and nutpie also record **zero
  retained divergences** on all six cells and still fail on `sigma`. On
  these seeds, at least, plain NUTS gives no divergence signal on this
  posterior either.
- **GLMM_Poisson is hard for every sampler, but the competitors do not show
  WP46's corner-trap signature.** Their worst cross-chain disagreement is
  0.12–0.73 pooled sd, against the wall-pinned chains WP46 saw. Their
  failure is slow `sigma` mixing. Whether oWALNUTS reproduces the traps is a
  Phase 2 question.

Process failures, recorded and not rerun:

- CmdStan `lotka_volterra` 560562 errored during sampling: the
  `integrate_ode_rk45` step limit was hit and cmdstanpy raised.
- nutpie `lotka_volterra`: on seed 560561 a nutpie worker panicked
  (`Failed to constrain the parameters of the draw`, then a poisoned mutex),
  and the child process died. Seeds 560562 and 560563 never started. All
  three are recorded as `timeout_or_crash`, as in v6, where nutpie's
  lotka_volterra child also died.
- CmdStan 0/3 on `gp_pois_regr`, `one_comp`, `accel_gp` and centered Eight
  Schools. Its `one_comp` cells also have max |z| 4.85 and 5.07 against the
  reference.

## Infrastructure

The BridgeStan libraries were copied from sibling builds of the same
posteriordb sources: WP48 `dense_metric_posteriordb_v1/models` for the 17,
and WP46 `posteriordb_breadth_v1/models` for the five. The posteriordb
checkout is a copy of WP46's, at `28f8d3d`. Three CmdStan executables were
copied from WP48. The other 19 executables and all 22 nutpie libraries were
built by `prepare_competitors.py`; see `artifacts/compile-status.json`. The
nutpie libraries come from the exact `bridgestan.compile_model(...,
make_args=["STAN_THREADS=true"])` call that `nutpie.compile_stan_model`
makes.
