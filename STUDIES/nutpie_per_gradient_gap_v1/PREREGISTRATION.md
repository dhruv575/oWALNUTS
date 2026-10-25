# Preregistration — nutpie_per_gradient_gap_v1 (WP58)

Frozen 2026-10-25 on `wt/nutpie-gap` (base `f097391c`: `Init::default()` =
`best_of(16)`, `Tuning::default()` nonfinite policy `RejectLeaf`, fixed
`Metric::dense()` warmup defaults) before the first evidence cell.
`protocol.json` is the machine-readable copy and is authoritative for arm
definitions, order and statistics.

Setup before the freeze, not evidence: the study venv (WP47's package
versions), `maturin develop --release` of this worktree's extension, the Rust
harness build, a value/gradient check of the native Rust densities against
the numpy and PyMC ones (5 points per model; gradient differences <= 3e-11),
a check that the BridgeStan Python package loads the three copied libraries
on Windows, and a smoke run on seed 1 (outside the evidence seeds) in a
scratch directory outside `artifacts/`: `eight` nutpie / nutpie-counted /
py-default / py-nutpiemetric / rs-default / rs-nutpiemetric, `eight_nc`
nutpie / py-levels1 / rs-meanaccept / rs-nutslike and `hier` rs-default.
`protocol.json` (including predictions P1–P8 and the decision rule) was
written before the smoke run. The smoke outputs were looked at to check the
plumbing; what they showed is disclosed here because it was seen before the
freeze: callback counts equal the reported counts exactly for oWALNUTS on
both paths and nutpie's counted callbacks exceed `n_steps` by 55–57 per
four-chain run; on `eight_nc`, rs-meanaccept adapted to h ≈ 0.39–0.47
(nutpie 0.62–0.71); with nutpie's metric transplanted oWALNUTS adapted to
h ≈ 0.59–0.63 on `eight`; `hier` rs-default spent 71 % of its gradients in
warmup. Single-seed values; no prediction or rule was changed after seeing
them. The smoke directory is deleted.

## Question

WP47 measured, on three PyMC models through the Python package, that nutpie
0.16.8 achieves 1.6–2.4x oWALNUTS's minimum bulk ESS per gradient. How much
of that gap is (a) gradient accounting, (b) model class, (c) the WALNUTS
kernel's refinement (levels, `delta`), and (d) adaptation (the step-size
statistic and the mass matrix)?

## Design

Six models: the WP47 PyMC models `gauss100`, `eight` (noncentered Eight
Schools), `hier` (157-D hierarchical regression), reused verbatim
(`callpath_targets.py`); the bridge model `eight_nc` (posteriordb noncentered
Eight Schools, the same model in Stan's parametrisation); and the two
posteriordb models chosen by a fixed rule from v6 (`protocol.json`):
`gp_pois_regr` and `lotka_volterra`.

Two oWALNUTS paths: the Python package (`owalnuts.sample` on a counted Python
callable: `from_pymc(model)` or a BridgeStan `log_density_gradient` callable,
threads=1, `init=None`), and a Rust harness (`rust/`, the `sampler::Sampler`
facade with `Init::default()`, threads=4; native Rust densities for the PyMC
models, `ReplicatedStanTarget` for the Stan models). nutpie runs through
`compile_pymc_model` (PyMC models; WP47's arm) or `from_pyfunc` around the
counted density callable (Stan models; and, as `nutpie-counted`, PyMC models).

Arms (full definitions in `protocol.json`): nutpie, nutpie-counted,
nutpie-drawmetric (`use_grad_based_mass_matrix=False`); py-default, py-delta2
(`max_error=2`), py-levels1 (`max_refinement_levels=1`), py-nutpiemetric
(nutpie's final metric, mass adaptation off); rs-default, rs-delta2,
rs-levels1, rs-meanaccept (only the dual-averaging statistic changed to
Stan's `accept_stat__`), rs-nutslike (levels 1 + exhaustion accepted unless
divergent + mean-trajectory statistic), rs-nutpiemetric. 4 chains x 1,000 /
1,000; fresh seeds 5858101–5858103 (unused on every branch); strictly
sequential, one cell at a time, in the frozen order. 225 cells.

Per cell: gradients split into start selection / initial evaluation /
warmup / sampling, counted callbacks against the reported count, min bulk and
tail ESS, max rank R-hat, divergences, mean tree depth, gradients per
retained transition, leaves built, refined-leaf fraction, reverse-check
calls, step size, acceptance statistic where exposed, and ESS per gradient
(total and sampling-only).

## Statistic and decomposition

Per (model, arm): geometric mean over seeds of min bulk ESS / total
gradients. `gap = ln(nutpie) - ln(default)` on the same path. Fraction closed
by arm X: `f_X = [ln(X) - ln(default)] / gap`, pooled over a model set as
sum of numerators over sum of gaps. Accounting share: the change in the
pooled PyMC gap when both sides use counted callbacks instead of reported
counts. Model class: the default gap on PyMC vs posteriordb models, with the
`eight` / `eight_nc` bridge. Kernel: f of levels1, delta2. Adaptation: f of
rs-meanaccept and the nutpiemetric arms, plus `ln(nutpie) -
ln(nutpie-drawmetric)` as a fraction of the gap.

## Predictions

* P1: accounting explains < 15 % of the PyMC-model gap.
* P2: py-levels1 recovers at least half of the gap on the PyMC models
  (pooled f >= 0.5).
* P3: py-delta2 recovers less than py-levels1 on the PyMC models.
* P4: on gp_pois_regr and lotka_volterra oWALNUTS-default stays >= 0.9x
  nutpie per gradient (each model, both paths).
* P5 (own): the step statistic is the largest adaptation factor:
  rs-meanaccept pooled f on the PyMC models >= 0.5 and above
  rs-nutpiemetric's.
* P6 (own): the mass matrix explains little on gauss100 (|f| < 0.25) and
  less than the step statistic on hier.
* P7 (own): the eight_nc gap (Rust path) is within a factor 1.25 of the PyMC
  eight gap (Python path).
* P8 (own): Rust and Python default ESS per gradient agree within
  0.8–1.25x on every PyMC model.

P1–P4 are the coordinator's predictions, recorded as given.

## Decision rule (frozen)

If py-levels1 or py-delta2 closes >= 50 % of the pooled gap on the three
PyMC models (Python path) **and** the same arm on the Rust path passes at
least as many gate cells as rs-default on gp_pois_regr + lotka_volterra (6
cells) and no fewer than 5/6, recommend a preregistered default-candidate
study for that arm. Otherwise report the decomposition and recommend
documentation only. The diagnostic arms do not trigger the rule. No default
is changed by this study; failures are results and are not rerun.

## Amendment A1 (committed after the seed-5858101 block, before every cell it adds)

All four `lotka_volterra` py-* cells of seed 5858101 failed at transition 0:
the package's `init=None` draws unchecked numpy uniform(-2, 2) starts, chain
0's start is not evaluable (the ODE solve throws; the callable returns -inf)
and `owalnuts.sample` raises "current position is not evaluable". These are
results and stay recorded; the `init=None` cells of the later seeds run as
preregistered. A1 appends, after the frozen 225-cell plan, four arms on
`lotka_volterra` only — `py-default-uinit`, `py-delta2-uinit`,
`py-levels1-uinit`, `py-nutpiemetric-uinit` — identical except
`init="uniform"` (Stan's redraw rule); their start-search calls count in
the total gradients. They stand in for the py-* arms on `lotka_volterra` in
the Python-path statistics (P4). The decision rule's Python-path fractions
are on the PyMC models and are unaffected.
