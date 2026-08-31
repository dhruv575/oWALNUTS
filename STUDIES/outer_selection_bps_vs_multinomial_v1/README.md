# outer-selection-bps-vs-multinomial-v1

Evidence class: preregistered reverse ablation on the production default; three
fresh seeds; exploratory sampling evidence (not a public benchmark claim).
Executed 2026-08-31. Protocol frozen before sampling in `protocol.json` /
`PREREGISTRATION.md`.

**Question.** Does the biased-progressive outer join `min(1, W_new/W_old)`
(oWALNUTS's default) buy anything over the exact normalized multinomial outer
join `W_new/(W_old+W_new)` when trajectories, stopping, metric, and adaptation
are identical? This is the transferable mechanism hypothesized in
`wiki/nextstat-0.10.1-clean-room-study.md`.

**Design.** Exact v38 noncentered Eight Schools density, four frozen
unconstrained starts, 4 sequential chains, 1,000 discarded + 1,000 retained,
initial step 0.3, depth 8, refinement levels 8, `max_error` 1.0, target
acceptance 0.95, dual-averaged step and Welford diagonal mass. Arms differ only
in `RunConfig::with_research_outer_orbit_selection`. Seeds 82001–82003. Work
unit is retained fused target calls (one call = one leapfrog gradient).

## Result

| | BPS (default) | exact multinomial | ratio BPS/multinomial |
|---|---:|---:|---:|
| bulk ESS per call, geomean over six functionals | — | — | **1.7453** |
| min tail ESS/call ratio over functionals | | | 1.4387 |
| min squared-functional bulk ESS/call ratio | | | 1.6398 |
| self-retention (retained draw equals previous) | 0.39% | 10.74% | |
| lag-1 ACF, `mu` | +0.221 | +0.520 | |
| lag-1 ACF, `sd_theta` | +0.029 | +0.312 | |
| mean depth / leaves built / calls per transition | 3.77 / 13.46 / 14.59 | 3.67 / 12.62 / 13.85 | |
| E-BFMI range over 12 chains | 0.856–1.014 | 0.836–1.052 | |
| retained divergences / invalid / depth caps | 0 / 0 / 0 | 0 / 0 / 0 | |

All six cells passed the per-cell health gates (max rank R-hat 1.00629, min
bulk ESS 1,139, min tail ESS 670). Full tables: `artifacts/RESULTS.md`;
machine-readable: `artifacts/summary.json`; raw cells:
`artifacts/cell-{arm}-{seed}.json`.

**Verdict.** `bps_advantage_confirmed_default_stands`. Primary ratio 1.745
≥ 1.10 with every safety gate satisfied. Removing biased progressive selection
costs roughly 43% of bulk ESS per gradient and 30% of tail ESS per gradient on
this target, at 5% fewer calls per transition. The mechanism is as predicted:
BPS almost never retains the initial state (0.4% vs 10.7%) and lag-1
autocorrelation drops by about 0.3 on every functional. E-BFMI, depth and
leaf distributions are essentially unchanged, so this is a selection effect,
not a trajectory-length effect.

**What this does and does not say.** The outer join rule is a material
efficiency lever and the default is the right one. It does *not* explain the
NextStat public-API gap: oWALNUTS already uses BPS, so the gap must come from
implementation throughput, adaptation, or density specialization (clean-room
plan items 2–4). No source change is made or justified by this study.

## Reproduce

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu run --release   # refuses to overwrite artifacts
python analyze.py
```

`CHECKSUMS.sha256` pins protocol, sources, and artifacts.
