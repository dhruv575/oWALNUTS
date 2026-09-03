# kernel_gap_v1 — decomposing the per-gradient gap to Stan's NUTS on ordinary posteriors

Status: matched-condition instrumentation study, executed 2026-09-02 on
branch `wt/kernel-gap` (WP30). Not preregistered (it attributes a known gap
to its mechanism and produces the candidate for a preregistered rerun; it
flips no default). Driver: `src/main.rs` (one cell: model x arm x seed);
`cmdstan_reference.py` (CmdStan 2.39.0 adapted step, inverse metric and
post-warmup positions per chain); `run_table.py` (table, `analyze`);
`build_models.py` (BridgeStan builds, no `STAN_THREADS`, as in
`posteriordb_bench_v3`). The reference NUTS of `examples/kernel_efficiency.rs`
was moved to `examples/support/reference_nuts.rs` so that it runs over any
`Target` (here a BridgeStan model) and reports the same orbit statistics as
the kernel. Artifacts: `artifacts/cells/*.json` (every cell with the
per-transition traces replaced by their summaries), `artifacts/cmdstan/*.json`
(the CmdStan reference per model), `artifacts/results-table.md`,
`artifacts/summary.json`, `artifacts/table-run.log`, `artifacts/funnel/*.log`.

## Question

`posteriordb_bench_v3` has oWALNUTS at 0.4–0.95x CmdStan's minimum bulk
ESS per gradient on the healthy models; `kernel_efficiency_v1` explained
the easy hand-written targets (re-evaluation, U-turn statistic, refinement
rejections); `uturn_default_v1` found `MomentumSum` a wash on posteriordb
under the default warmup (1.06x geomean); `step_collapse_v1` found that
under CmdStan's step and metric on `earnings` the WALNUTS orbit is 49 leaves
against NUTS's 163 with 70 % recursive U-turns and a quarter of the
per-draw ESS. Which factor of

```
ESS/gradient = (ESS per orbit) x (orbits per gradient)
orbits per gradient = 1 / (leaves per orbit x gradients per leaf)
```

is the gap on real posteriors, once warmup is taken out of the comparison?

## Protocol

Six posteriordb models (`28f8d3d`): `earnings-logearn_interaction`,
`kidiq-kidscore_momhsiq`, `mesquite-logmesquite_logvash`, `nes2000-nes`,
`garch-garch11`, `arK-arK`. CmdStan 2.39.0 runs once per model (defaults,
4 chains, 1,000/1,000, seed 84200); for each chain its adapted
`stepsize__`, its adapted inverse metric (posterior variances) and its first
retained draw, unconstrained through BridgeStan, are the step, `M^-1` and
start of that chain in every arm. Both samplers then run **without warmup**
at exactly those values, 4 chains x 2,000 retained draws, depth 10, fresh
seeds 84201–84202 (grep-clean). Arms:

| arm | what it is |
|---|---|
| `nuts-ref` | the reference NUTS (Stan's `base_nuts` 2.21+: multinomial within subtrees, biased progressive across doublings, `p_sharp . rho` on the summed momenta with the two cross checks, divergence at `H - H0 > 1000`) |
| `walnuts` | the oWALNUTS kernel through `Sampler` (`Adaptation::None`, `Metric::fixed_diagonal`, four levels, `delta = 1`, `Endpoints`, `Stop`, initial-evaluation cache) |
| `walnuts+cross` / `walnuts+rhosum` | `UTurnRule::EndpointsWithCross` / `UTurnRule::MomentumSum` |
| `walnuts+delta1000` | refinement never engages |
| `walnuts+levels1` | one level with `AcceptUnlessDivergent`: NUTS with the endpoint U-turn rule inside the oWALNUTS machinery |
| `walnuts+levels1+rhosum` | one level, Stan's exhaustion rule, Stan's U-turn rule: the reference re-expressed in the oWALNUTS machinery (control) |
| `walnuts+accept` | four levels with `AcceptUnlessDivergent` |

Per transition both arms record gradients, leaves, depth, the stop cause,
the number of states in the final orbit and the indices of the selected and
the initial state within it (new `TransitionDiagnostics::{orbit_states,
selected_index, initial_index}`; the reference tracks the same), the
selected refinement level, refinement attempts and reverse-coarser
rejections; per chain the work totals with the new
`WorkTotals::{accepted_forward_micro_steps, refinement_level_built}`
(gradients attached to a built leaf and the refinement-level histogram).
Metric: minimum over unconstrained coordinates of bulk ESS
(`owalnuts::diagnostics::ess_bulk`) over the 8,000 draws. Ratios are to
`nuts-ref` on the same seed, then the seed median; geometric means over the
six models.

Sanity anchor: the reference NUTS reproduces CmdStan's own sampling run at
these settings — leapfrogs per orbit 158/29/49/50/11/33 against CmdStan's
155/29/50/49/11/33, ESS per gradient within 5–10 % (CmdStan's is over the
constrained parameters, 4 x 1,000 draws).

## Results

Seed medians of the ratio to `nuts-ref`; the full table with the absolute
numbers, depths, stop causes, selected-index statistics and non-leaf
gradient accounting is `artifacts/results-table.md`.

| model | arm | ESS/grad | ESS/orbit | leaves/orbit | grads/leaf | stop causes (walnuts) |
|---|---|---:|---:|---:|---:|---|
| earnings | `walnuts` | 0.83 | 0.21 | 0.26 | 1.01 | recursive U-turn 67 %, outer 30 %, reverse-coarser 3 % |
| | `walnuts+rhosum` | 0.90 | 0.86 | 0.95 | 1.00 | recursive 54 %, outer 42 %, reverse-coarser 5 % |
| | `walnuts+levels1+rhosum` | 0.97 | 0.96 | 0.99 | 1.00 | |
| kidiq | `walnuts` | 0.70 | 0.35 | 0.49 | 1.01 | recursive 58 %, outer 40 %, reverse-coarser 2 % |
| | `walnuts+rhosum` | 0.84 | 0.83 | 0.98 | 1.01 | outer 61 %, recursive 35 %, reverse-coarser 4 % |
| | `walnuts+levels1+rhosum` | 0.98 | 0.97 | 0.99 | 1.00 | |
| mesquite | `walnuts` | 0.89 | 0.74 | 0.82 | 1.01 | outer 49 %, recursive 46 %, reverse-coarser 5 % |
| | `walnuts+rhosum` | 0.96 | 0.93 | 0.95 | 1.01 | outer 61 %, recursive 31 %, reverse-coarser 7 % |
| | `walnuts+levels1+rhosum` | 1.01 | 1.01 | 1.00 | 1.00 | |
| nes2000 | `walnuts` | 0.62 | 0.42 | 0.67 | 1.00 | outer 49 %, recursive 49 %, reverse-coarser 2 % |
| | `walnuts+rhosum` | 0.88 | 0.86 | 0.97 | 1.01 | outer 72 %, recursive 24 %, reverse-coarser 4 % |
| | `walnuts+levels1+rhosum` | 0.90 | 0.90 | 1.00 | 1.00 | |
| garch11 | `walnuts` | 0.81 | 0.59 | 0.70 | 1.04 | outer 55 %, recursive 41 %, reverse-coarser 4 % |
| | `walnuts+rhosum` | 0.89 | 0.89 | 0.97 | 1.04 | outer 66 %, recursive 29 %, reverse-coarser 6 % |
| | `walnuts+levels1+rhosum` | 0.96 | 0.96 | 1.00 | 1.00 | |
| arK | `walnuts` | 0.79 | 0.73 | 0.92 | 1.01 | outer 68 %, recursive 30 %, reverse-coarser 2 % |
| | `walnuts+rhosum` | 0.93 | 0.92 | 0.98 | 1.01 | outer 78 %, recursive 19 %, reverse-coarser 3 % |
| | `walnuts+levels1+rhosum` | 0.86 | 0.86 | 1.00 | 1.00 | |

Geometric means over the six models:

| arm | ESS/grad | = ESS/orbit | x orbits/grad | (leaves/orbit | x grads/leaf) |
|---|---:|---:|---:|---:|---:|
| `walnuts` (default kernel) | **0.77** | 0.46 | 1.66 | 0.60 | 1.01 |
| `walnuts+cross` | 0.69 | 0.39 | 1.76 | 0.56 | 1.01 |
| `walnuts+delta1000` = `walnuts+levels1` | 0.77 | 0.46 | 1.66 | 0.60 | 1.00 |
| `walnuts+accept` | 0.77 | 0.46 | 1.66 | 0.60 | 1.01 |
| `walnuts+rhosum` | **0.90** | 0.88 | 1.02 | 0.97 | 1.01 |
| `walnuts+levels1+rhosum` (control) | 0.95 | 0.94 | 1.00 | 1.00 | 1.00 |

## Where the gap is

1. **Gradients per leaf is not a factor.** At CmdStan's step the level-0
   leaf error exceeds `delta = 1` on 0.1–0.7 % of leaves, so refinement
   attempts and reverse checks cost 0.04–0.19 gradients per orbit, 1.0–4 %
   of the leaf gradients (`grads/leaf` 1.00–1.04; the initial re-evaluation
   is cached). `delta1000`, `levels1` and `accept` are bit-identical or
   within 1 % of `walnuts`.

2. **Selection is not a factor.** With the same orbits the oWALNUTS joins
   (multinomial within subtrees, biased progressive across doublings) select
   the same way as the reference: the selected state's relative displacement
   from the initial state is 0.51–0.56 of the orbit in both `nuts-ref` and
   `walnuts+levels1+rhosum` on every model, and `walnuts+levels1+rhosum` is
   at 0.86–1.01x per gradient (0.95 geomean, inside the ±10 % seed spread of
   the minimum-ESS statistic). The 0.60–0.63 displacement of the `walnuts`
   arm is a consequence of its short orbits, not a selection difference.

3. **The gap is leaves per orbit, and it is the endpoint U-turn statistic
   firing where Stan's does not.** The `v10` rule (`rho_end . M^-1 (q_end -
   q_start)` at the two extremes of the merged span, the original Hoffman
   & Gelman criterion) ends the orbit at 0.26x (earnings), 0.49x (kidiq),
   0.67x (nes2000), 0.70x (garch11), 0.82x (mesquite), 0.92x (arK) of the
   reference's leaves, and 41–69 % of orbits end in the *recursive* check
   (a subtree that turned in the endpoint sense and is discarded). Under a
   well-scaled metric the position difference across a span is dominated
   by the fast directions and turns long before the momentum sum does; the
   shorter orbit moves less, so ESS per orbit falls faster than the leaf
   count (0.46x against 0.60x) and the per-gradient ratio is 0.77x — the
   longer trajectory is cheaper per unit of ESS. The cross checks alone
   (`EndpointsWithCross`) make it worse (0.69x): they add stopping
   conditions to a statistic that already stops too early.

   Switching the statistic to Stan's (`MomentumSum`: the sum of the leaf
   momenta against `M^-1 p` at the extremes, with the cross checks, applied
   at every recursive merge and after every doubling exactly as the
   reference does) restores the leaf count to 0.95–0.98x on every model
   and the per-gradient ratio to **0.90x** (0.84–0.96 per model). This is
   the option `step_collapse_v1` asked for: `earnings` goes from 40 to 151
   leaves per orbit at CmdStan's `h = 0.018` (the reference: 158), from
   0.054 to 0.219 ESS per orbit (reference 0.256).

4. **What remains after the statistic is refinement's reverse-coarser
   stops** (the 0.90 → 0.95 between `walnuts+rhosum` and the one-level
   control): with `delta = 1` at CmdStan's step, 3–7 % of orbits end because
   a refined leaf's reverse coarsening passed (the leaf is not reversible
   at that level and the orbit stops there), which is the 0.95–0.98x leaf
   count and the 0.83–0.93x ESS per orbit of `walnuts+rhosum`. It is the
   robustness mechanism's price on a posterior that does not need it, and
   it is the same mechanism `kernel_efficiency_v1` measured at 4–15 % on
   Eight Schools. No kernel option removes it without giving up the
   refinement that carries the funnel tail (`delta1000` and `levels1` are
   plain NUTS); it is a `delta` question for the adaptation, not a kernel
   rule.

5. **Why `uturn_default_v1` saw a wash.** On these six models under the
   default warmup that study measured `MomentumSum` at 0.93 / 1.37 / 1.03 /
   1.18 / 1.27 / 0.91x (earnings, kidiq, mesquite, nes2000, garch11, arK;
   1.12x geomean over the six) — the same direction and size as the 1.17x
   here (0.90 / 0.77), with `earnings` and `arK` the two models where the
   endpoint rule already reaches 0.8–0.9x of Stan's leaf count. The 1.06x
   over all 17 models and the 0.78x worst case came from the other eleven
   posteriors, several of them sampled under the unit-floored metric
   (`step_collapse_v1` 1a) or at the depth cap, where the statistic is not
   what limits the orbit. The kernel-side gap on healthy models under a
   correct metric *is* the U-turn statistic; the earlier "not the U-turn
   rule" reading was made under a warmup that hid it.

## Prototype

No new kernel rule was needed: `UTurnRule::MomentumSum` (opt-in since
`kernel_efficiency_v1`) is the Stan-style test applied at each merge with
the same statistic, and the control arm shows there is no residual U-turn
difference beyond it (`walnuts+levels1+rhosum` builds 0.997x the
reference's leaves). Its effect under matched conditions is the 0.77 →
0.90x above. Defaults are bit-identical: the added fields are counters
(`tests/kernel_fingerprint.rs` unchanged, every test green with and
without `research`).

### Funnel check (`examples/funnel_kernel_options.rs`, now with `--seed` and `--sampler-defaults`)

Neal's 10-D funnel, exact `P(omega < -5) = 0.0478`, 4 x 2,000 / 20,000 per
seed, three fresh seeds 252601–252603, batch-means s.e. (500-draw batches;
known to underestimate on the funnel's autocorrelated `omega`). Pooled
over the three seeds (mean estimate, s.e. combined in quadrature):

| tuning | `Endpoints` (default) | `MomentumSum` |
|---|---|---|
| paper (Appendix C warmup, identity metric, `h = 0.1`, eight levels) | 0.0573, 0.0678, 0.0492 (z +1.1, +2.5, +0.2); pooled 0.0581, z **+2.2** | 0.0476, 0.0394, 0.0504 (z −0.0, −1.6, +0.4); pooled 0.0458, z **−0.5** |
| sampler defaults (`Tuning::default()`, adaptive diagonal, dual averaging 0.8) | 0.0376, 0.0251, 0.0270 (z −0.9, −3.6, −3.1); pooled 0.0299, z **−3.8** | 0.0455, 0.0399, 0.0545 (z −0.3, −1.3, +0.8); pooled 0.0466, z **−0.3** |

`MomentumSum` preserves the tail mass at both tunings on all three seeds
(target calls 1.1–1.2x the endpoint rule at the paper tuning, 1.0–1.8x at
the defaults: longer orbits in the neck). The endpoint rule is high at the
paper tuning and low at the sampler defaults on these seeds; the defaults
result differs from `funnel_defaults_v1` (WP28: |z| <= 2 on seeds
82101–82103 at eight levels) and is consistent with that study's own
caveat that one chain per seed adapts to a step of 0.007–0.02 and the
pooled estimate then depends on which chain it is. Three seeds and an
underestimated s.e. do not settle the default's funnel status; they do
say the candidate is not worse than the default there.

## Recommendation

1. `UTurnRule::MomentumSum` is the fix for the largest kernel-side gap on
   ordinary posteriors and should be re-decided as the sampler default
   **together with** the metric fix of `step_collapse_v1`
   (`DiagonalMetricRegularization::Stan`), on the v3 protocol with fresh
   seeds: the two are one finding — the endpoint statistic loses 0.4–0.5x
   on regressions exactly when the metric is right — and WP26's rejection
   was measured under the warmup that hides it. Expected effect on the
   healthy models: 1.15–1.2x per gradient, `earnings` under `reg`
   recovering its R-hat gate (the 49-leaf orbit was the cause of its 0/2).
2. Until then, users on regressions and time-series models should set
   `Tuning::kernel_options(KernelOptions { u_turn: UTurnRule::MomentumSum, ..Default::default() })`
   with the Stan regularisation.
3. The remaining 5–10 % (refinement's reverse-coarser stops at `delta = 1`
   on posteriors that never need refinement) belongs to the `delta`
   adaptation, not to the kernel; the paper's K-quantile rule already sets
   `delta` from the observed errors and would leave these leaves unrefined.

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 cmdstanpy==1.3.0 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
MAKE=mingw32-make .venv/Scripts/python build_models.py
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/../../target cargo build --release
for m in earnings__logearn_interaction kidiq__kidscore_momhsiq mesquite__logmesquite_logvash nes2000__nes garch__garch11 arK__arK; do .venv/Scripts/python cmdstan_reference.py $m; done
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_table.py run       # ~8 min
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_table.py analyze
for s in 252601 252602 252603; do for u in endpoints rhosum; do ../../target/release/examples/funnel_kernel_options.exe --uturn $u --seed $s; ../../target/release/examples/funnel_kernel_options.exe --uturn $u --seed $s --sampler-defaults; done; done
```

CmdStan 2.39.0 is expected at `CMDSTAN_HOME` in `cmdstan_reference.py`.
