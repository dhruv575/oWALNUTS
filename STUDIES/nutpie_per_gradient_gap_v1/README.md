# nutpie per-gradient gap v1 — the gap is mass-matrix adaptation, not accounting or refinement (WP58)

Status: preregistered at `93201f95` before the first evidence cell (base
`f097391c`). Amendment A1 (`b0825557`) was committed after the seed-5858101
block and before every cell it adds. Executed 2026-10-25 on the shared
16-core Windows machine, strictly sequentially. All 225 preregistered cells
and the 12 A1 cells are recorded, and none was rerun. Tables:
`artifacts/results-table.md`. Machine-readable: `artifacts/summary.json`.
Walls are contended and are not used. Gradients, ESS and R-hat are the
evidence.

## Verdict

**The frozen rule gives documentation only. Neither refinement arm closes
the gap: `py-levels1` closes 5 % of the pooled PyMC-model gap and
`py-delta2` closes 7 %.** The gap reproduces WP47: nutpie has 1.70x
oWALNUTS's min bulk ESS per gradient over the three PyMC models on the
Python path (gauss100 1.66, eight 1.42, hier 2.10) and 1.64x on the Rust
path. It decomposes as follows (fractions of the pooled log gap, Python
path):

| component | share of gap | evidence |
|---|---:|---|
| gradient accounting | **0.15 %** | oWALNUTS reported = counted callbacks exactly (every cell, both paths). nutpie's counted callbacks exceed `n_steps` by 0.06–0.10 % (initialisation). Best-of-16 start selection costs 64 calls (0.03–0.09 %). |
| WALNUTS refinement | **5–7 %** (Rust: −12 %, 0 %) | Only 0–6.5 % of selected leaves are refined. Reverse checks are ≤ 3 % of sampling gradients. Removing refinement (levels1) loses gates on eight / eight_nc / gp / LV. |
| step-size statistic | **−63 %** (makes the gap larger) | `rs-meanaccept` (Stan's `accept_stat__`) adapts to the same h (0.45–0.50) and inflates hier warmup to 85 % of gradients. |
| warmup cost | **44 %** (hier 83 %, gauss100 16 %, eight 1 %) | On hier oWALNUTS spends 72 % of its gradients in warmup, nutpie 49 %. Per sampling gradient the hier gap is only 1.14x. |
| mass matrix (nutpie's final metric transplanted, step adaptation only) | **44 %** Python, **60 %** Rust | gauss100 62–68 % (sampling efficiency +31–36 %), hier 41–83 % (warmup share 0.72 → 0.51), eight 5–25 %. nutpie's own switch from gradient-based to draw-based metric costs it 34–37 % of the gap. |
| two nutpie runs that differ only in starts and density implementation | 15 % | `nutpie` vs `nutpie-counted`: 0.96 / 1.15 / 1.16x. This is roughly the 3-seed noise and start floor. |

So the cause is (b), adaptation. It is the diagonal mass-matrix estimate:
nutpie's gradient-based `sqrt(var(x)/var(grad))` is less noisy on a 100-D
Gaussian and converges in fewer warmup gradients on hier. It is not (a),
(c) or (d), and not the WALNUTS kernel. On eight, the residual is mostly
unexplained, and there nutpie buys its per-gradient lead with divergences.
nutpie fails the gates on eight (0/3), eight_nc (0/3) and gp_pois_regr
(0/3, 140–192 divergences per run), while oWALNUTS-default passes 3/3 on
all three.

## Predictions

| id | prediction | outcome |
|---|---|---|
| P1 | accounting < 15 % of the gap | **Held**: 0.15 %. |
| P2 | py-levels1 recovers >= 50 % | **Failed**: 5 % (Rust −12 %). |
| P3 | py-delta2 recovers less than levels1 | **Failed**: delta2 7 % > levels1 5 %. Both are near zero. |
| P4 | default >= 0.9x nutpie on gp_pois_regr and lotka_volterra, both paths | **Failed** on gp_pois_regr (0.87 Python, 0.83 Rust; nutpie diverges in every run). lotka_volterra: 9.6x / 11.2x, because one nutpie seed has a stuck chain (R-hat 2.77, min ESS 5). |
| P5 | step statistic is the largest adaptation factor (meanaccept f >= 0.5, above nutpiemetric) | **Failed**: −0.63 vs +0.60. |
| P6 | metric explains little on gauss100 (\|f\| < 0.25), less than the statistic on hier | **Failed**: gauss100 0.62 / 0.68; hier metric 0.83 vs statistic −1.05. |
| P7 | eight_nc gap (Rust) within 1.25x of the PyMC eight gap (Python) | **Held**: 1.38 vs 1.42 (quotient 0.97). The path is not the cause. |
| P8 | Rust and Python default ESS/grad within 0.8–1.25x | **Held**: 1.04 / 1.01 / 1.07. |

## Decision rule (frozen) and recommendations

levels1 closes 5 % and delta2 7 %, both below 50 %, and each loses one
posteriordb gate cell (5/6 vs 6/6). **Rule outcome: report the
decomposition, documentation only.** No default was changed. The kernel
fingerprints are untouched and no library code was edited.

1. **Docs.** Replace the integrations README sentence "nutpie gets 1.6–2.4x
   more ESS per gradient" with the decomposition. The gap is mass-matrix
   adaptation: estimator noise on large well-scaled models, and warmup cost
   on hierarchical ones. It is not gradient accounting (0.15 %) or WALNUTS
   refinement (≤ 7 %). On eight, eight_nc and gp_pois_regr, nutpie's lead
   comes with divergences that fail the gates.
2. **Usability failure (docs, and a candidate for a separate study).** The
   Python package's `init=None` draws unchecked uniform(-2, 2) starts, and
   every `lotka_volterra` cell (12/12, all three seeds) died at transition 0
   with "current position is not evaluable". `init="uniform"` (A1) runs
   12/12, 10/12 passing the gates. The Rust default is `Init::best_of(16)`, so
   the Python default does not mirror it. Document `init="uniform"` for
   Stan, ODE and constrained models. Aligning the Python default is a
   default change and needs its own study.
3. **Not rule-driven follow-up.** A preregistered study of an opt-in
   gradient-informed diagonal metric estimate (nutpie's
   `sqrt(var(x)/var(grad))`) and of faster early metric windows. The
   transplant closes 44–60 % of the pooled gap but **loses gates** on
   gp_pois_regr (Rust 1/3) and lotka_volterra (Rust 1/3). The nutpie metric
   on those models comes from runs that diverge or stick, so the follow-up
   must keep the posteriordb gates.

## Model class

The bridge model shows that the path (PyMC callable vs Stan) does not
matter: eight 1.42x vs eight_nc 1.38–1.48x. Per gradient, nutpie also leads
on gp_pois_regr (1.15x / 1.21x). That is not a lead in reliability, because
nutpie passes 0/9 gates on eight, eight_nc and gp_pois_regr, against
oWALNUTS-default's 9/9. The brief's "0.6–1.6x on posteriordb" overstates
v6: v6's geomean is 0.90x, and only four models are above 1. The smooth,
well-scaled PyMC models are not where refinement costs: gauss100 never
refines.

## What was run

* Models: the WP47 PyMC models gauss100, eight and hier (`callpath_targets.py`
  copied verbatim), the bridge `eight_nc`, and the two posteriordb models
  chosen by the frozen v6 rule, `gp_pois_regr` (1.056) and `lotka_volterra`
  (1.046). The BridgeStan libraries were copied from the sibling build in
  `dense_metric_posteriordb_v1/models` (same posteriordb sources). The Rust
  harness implements the PyMC densities natively (gradient agrees with PyMC
  to 3e-11).
* Paths: the Python package (study venv, WP47's package versions, extension
  built with `maturin develop --release` at `f097391c`). A counted Python
  callable is used, either `from_pymc(model)` or a BridgeStan callable. Runs
  are **threads=1** (WP47: Python callables hold the GIL), `init=None`, with
  nutpie at cores=1. The Rust harness (`rust/`, `sampler::Sampler`,
  `Init::default()`, threads=4) covers all six models.
* 4 chains x 1,000 / 1,000, seeds 5858101–5858103. Gates: rank R-hat
  ≤ 1.01, bulk/tail ESS ≥ 400 over every unconstrained coordinate (plus the
  eight theta), no retained divergence.

## Anomalies and limits

* Twelve `lotka_volterra` py-* cells are errors (`init=None`; see
  recommendation 2). They stay recorded. A1 replaces them in the statistics.
* nutpie `lotka_volterra` seed 5858101 has a stuck chain (R-hat 2.77, 4.0M
  gradients). It dominates that model's gap. The nutpie metric transplanted
  from it, and from gp_pois_regr's diverging runs, is not a good metric. The
  nutpiemetric arms on those two models measure that.
* `py-levels1-uinit` `lotka_volterra` seed 5858103 has a stuck chain (R-hat
  1.59). This is levels1's failure mode.
* Only three seeds. The nutpie vs nutpie-counted spread (4–16 %) bounds
  what per-model fractions mean. Pooled fractions are more stable than
  per-model ones.
* The Python package exposes no acceptance statistic. The Rust value is the
  arm's own dual-averaging statistic over the last 100 warmup transitions,
  which is 0.80 by construction.
