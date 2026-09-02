# step_collapse_v1 — why the default step collapses on `sblrc`/`earnings`, why the `arma11` escapee crawls, and what fixes which

Status: diagnostic study with a preregistered remedy table
(`PREREGISTRATION.md`, committed at `4546d30` before the first table cell),
executed 2026-09-02 on branch `wt/step-collapse` (WP27). Section 1 was
developed on the `posteriordb_bench_v3` seeds (79101–79103) of `sblrc`,
`earnings` and `arma11` and is not preregistered; section 2 is the
preregistered table on fresh seeds 80101–80102; section 3 the decision.
Driver: `src/main.rs` (one posteriordb cell, four chains, per-transition
warmup telemetry: `h`, the dual-averaging statistic, depth, stop, selected
refinement level, energy error, every metric update with its installed
diagonal); `cmdstan_trace.py` (CmdStan 2.39.0 with `save_warmup` from the
same constrained starts); `trace_summary.py` (per-window summary of a
cell); `run_table.py` (the table and `artifacts/results-table.md`).
Per-transition telemetry and draws are regenerable and not committed;
per-cell JSON with the traces stripped is under `artifacts/cells/` (table
cells, and the diagnosis cells as `diag-*`) and `artifacts/cmdstan-cells/`.

## 1. The mechanisms

### 1a. (a) Step collapse is the metric, not the step rule

`sblrc` 79101, chain 0, sampler defaults (`trace_summary.py`): the
dual-averaging statistic sits on its target from the first slow window on
(window means 0.77, 0.80, 0.79, 0.80, 0.80, 0.81) while `h` goes 0.5 → 0.0099
(initial phase) → 0.0034 → 0.0048 → 0.0013 → 0.0011 → 0.0030 at the five
metric updates and ends at 0.0042; no transition exhausts refinement, 8 % of
retained transitions refine, mean depth 4.7, zero depth-cap stops. Nothing
in the step rule is misbehaving: **dual averaging is correctly holding the
step at which the level-0 leaf error is 0.22 — under the wrong metric.**

The installed diagonal is 101 on the five regression coefficients and 64 on
`sigma` (in the API's mass convention, `1 / variance`), i.e. a variance of
0.0099. CmdStan from the same starts installs an inverse metric of
**1.07e-5** on the coefficients (the posterior variance; the retained
oWALNUTS draws have the same variance) and adapts to `h = 0.10–0.13`. The
`v10` default regularisation is `(n / (n + 5)) var + 5 / (n + 5)`
(`DiagonalMetricRegularization::TowardUnit`): at `n = 500` the additive term
is 0.0099, a thousand times the true variance, so the momentum scale is
30x too large in the stiff directions and the stable step 30x too small —
`0.10 / 30 = 0.0033`, the observed collapse to three digits. Stan's
regularisation `(n / (n + 5)) var + 1e-3 (5 / (n + 5))`
(`DiagonalMetricRegularization::Stan`) floors the variance at 1e-5 instead.

`earnings` 79101 is the same story on three of five coordinates: posterior
variances 1.6e-4, 3.2e-4, 5.1e-4 (CmdStan's inverse metric) are floored to
0.010 (installed mass 99.3, 97.7, 97.4), the step is 0.003 against
CmdStan's 0.017 from the same starts, and 85–114 retained transitions per
chain hit the depth cap. `diamonds` is *not* a collapse case at depth 10 (its
variances are above the floor; the default and the Stan regularisation give
the same `h = 0.003` and the same ESS, and CmdStan's `h` is of the same
order); v1's "diamonds collapse" was the depth-8 cap, fixed in
`adaptation_parity_v1`.

The hypotheses of the task, checked one at a time on `sblrc` 79101–79103
(`artifacts/sweep-sblrc/`, each within seed noise of the baseline's
`h = 0.003`, 0.38–0.63 x1e-3 ESS/gradient):

* the coarse-endpoint statistic under-reporting acceptance —
  `MeanTrajectoryAcceptance` (Stan's `accept_stat__`) gives `h` 0.003–0.007;
* the initial step search — Stan's `init_stepsize` before warmup and after
  every metric update (`research`) gives `h` 0.003–0.004;
* the window schedule / restart reference — `mu = ln 10h` gives 0.003–0.005;
* the initial-phase delta ramp gives 0.003–0.004;
* the new floors (half the search result; a bound of 4x or 10x on the
  shrink within a dual-averaging stream) give 0.003–0.006;
* one chain collapsing while others do not — all four chains collapse to
  the same `h` on every seed.

Switching the regularisation alone (`reg`) gives `h = 0.099–0.115` and
3.6–4.2 x1e-3 ESS/gradient on the three v3 seeds (9x the baseline, 0.55x
CmdStan's 6.7). The `stan_style` preset with the WP24 rule gives the same
(`h` 0.09–0.12, 3.5–3.9): every other Stan-parity difference is inert here.
`adaptation_parity_v1` had rejected Stan's regularisation because, under the
two-sided exhaustion rule, a chain started in a tail could not move, its
window variance was ~0, and the Stan prior installed a mass of 1e4–1e5
(the unit floor hid that at ~6); with the WP24 warmup rule the chain slides
out first, and the prior's real effect can be seen.

### 1b. (b) The post-escape crawl is a start CmdStan cannot leave either

`arma11` 79103 chain 3 starts at log density −3.14e84 (|gradient| 7.7e86;
the third-highest of the four starts, chain 2 starts at −3.6e108 and
escapes). Under the WP24 rule the chain slides: every transition of the
initial phase is an exhaustion at `h` shrinking 13x per transition to 1e-41,
then from transition ~60 the accepted-unless-divergent leaves ride down the
wall with statistic 1 and `h` grows 2.6x per transition — energy 3.1e84 at
transition 50, 1.2e67 at 75, 1.3e51 at 100, 9e30 at 150, and **3.66e5 at
250** with `h = 1.4e-8`. There the descent stops: the transition-start
energy is 3.66e5 at 250, 3.64e5 at 950 and 3.62e5 at 1999. From transition
250 on the dual-averaging statistic is on target (0.80) with level-0 leaves
of error 0.1–0.2, depth 8–9, 700+ leaves per orbit, `h` 1.4e-8 → 5.1e-8,
and the position moves every transition by ~1e-6: a crawl along a valley
whose transverse curvature fixes the stable step at 1e-8 and whose length
to the bulk (log density +258) is O(1) in the parameters.

CmdStan 2.39 from the same start (`cmdstan_trace.py`, chain 3): 50
iterations of divergences down to `h = 1.2e-39`, the same slide (lp
−1.1e69 at 75, −3.2e53 at 100, −9.5e33 at 150), **−3.67e5 at 250** with
`h = 2.2e-7`, then −3.67e5 at 450, −3.65e5 at 999, −3.62e5 at 1999; final
`h` 1.7e-6, 832 of its 1,000 retained draws at treedepth 10, R-hat 1.6 and
min bulk ESS 7 — the same cell as oWALNUTS's (h 5e-8, 660 depth-cap
draws, R-hat 1.6, ESS 7) with a 30x larger step, which is the unit-floor
metric of 1a again (the crawling chain's window variance is ~0; the default
installs 101, Stan's prior 1e5). No warmup option changes it: the delta ramp
is bit-identical on this chain (every wall energy exceeds 1,000 either
way), Stan's statistic, Stan's regularisation and the full `stan_style`
preset all end at `h` 5e-8 to 2e-6 with 590–720 depth-cap draws
(`artifacts/sweep-arma/`); the shrink bound (`shrink:10`) is the negative
control it was meant to be, pinning three chains at `h = 5e-7` (a floored
step cannot slide out of the wall — `freeze_mode_v1`'s step-floor
finding). This start needs far more than 1,000 transitions under either
sampler; it is a start-rule / reporting matter (the new
`diagnostics::ChainDisagreement` names chain 3), and the only remedy that
would help is a cross-chain restart (see `PREREGISTRATION.md`, not run).

Two smaller observations from the same trace: the three healthy `arma11`
chains adapt to `h = 0.10–0.11` under the default and `0.7` under the Stan
regularisation (CmdStan: 0.68–0.95) — the unit floor was binding there too;
and the freeze-mode escape leaves dual averaging four to six orders of
magnitude below the step the chain could use once it reaches the bulk,
which the window restarts (`mu = ln h` at the current `h`) recover only
geometrically.

### 1c. (c) `hmm_drive_0`: per-chain R-hat attribution

`diagnostics::Summary` now carries `chain_disagreement: Option<ChainDisagreement>`
(present when the maximum rank R-hat exceeds 1.01 and there are at least
three chains): the maximum R-hat over parameters with each chain left out,
and the list of chains whose removal alone brings it below 1.01. A run with
one chain in a second mode reports that chain; a run where no single chain
explains the failure reports an empty list with the leave-one-out values.
The `Display` of a `Summary` prints the line. Unit test:
`diagnostics::tests::chain_disagreement_names_the_odd_chain_out`.

## 2. The preregistered table

Seeds 80101–80102, 7 models x 10 arms + CmdStan from the same starts; every
cell ran once (`artifacts/table-run.log`, 41 minutes, no failure). Full
tables with per-seed detail: `artifacts/results-table.md`; per-cell JSON
(traces stripped): `artifacts/cells/`, `artifacts/cmdstan-cells/`. Seed
median of the minimum bulk ESS per gradient x1e3, then `x baseline`;
`gates` = seeds passing R-hat <= 1.01, bulk/tail ESS >= 400, zero
divergences; `h` = per-chain final step on 80101.

| model | baseline | **reg** | reg+ramp | reg+research | mean-accept | ramp | research | research+floor 0.5 | shrink 10 | stan-style | cmdstan |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sblrc | 0.40 (0/2) | **3.89 (9.7x, 1/2)** | 3.75 (9.4x, 2/2) | 4.36 (10.9x, 2/2) | 0.47 (1.2x, 0/2) | 0.55 (1.4x, 0/2) | 0.52 (1.3x, 0/2) | 0.33 (0.8x, 0/2) | 0.43 (1.1x, 0/2) | 3.25 (8.1x, 2/2) | 7.12 (2/2) |
| earnings | 0.20 (2/2) | 0.38 (1.9x, **0/2**) | 0.44 (2.2x, 0/2) | 0.47 (2.4x, 0/2) | 0.20 (1.0x, 2/2) | 0.22 (1.1x, 2/2) | 0.13 (0.7x, 2/2) | 0.17 (0.8x, 2/2) | 0.21 (1.1x, 2/2) | 0.15 (0.8x, 0/2) | 0.79 (2/2) |
| diamonds | 0.17 (2/2) | 0.16 (0.9x, 2/2) | 0.08 (0.5x, 0/2) | 0.18 (1.1x, 2/2) | 0.17 (1.0x, 2/2) | 0.19 (1.1x, 2/2) | 0.17 (1.0x, 2/2) | 0.17 (1.0x, 2/2) | 0.18 (1.0x, 1/2) | 0.18 (1.0x, 2/2) | 0.23 (2/2) |
| arma11 | 13.1 (2/2) | 37.3 (2.9x, 2/2) | 31.9 (2.4x, 2/2) | 22.5 (1.7x, 2/2) | 13.3 (1.0x, 2/2) | 13.2 (1.0x, 2/2) | 8.3 (0.6x, 2/2) | 5.2 (0.4x, 1/2) | 0.07 (0.01x, 0/2, 2 frozen) | 19.1 (1.5x, 2/2) | 62.3 (2/2) |
| kidiq | 2.18 (2/2) | 2.32 (1.1x, 2/2) | 2.08 (1.0x, 1/2) | 1.87 (0.9x, 2/2) | 1.71 (0.8x, 1/2) | 2.24 (1.0x, 2/2) | 1.75 (0.8x, 2/2) | 1.67 (0.8x, 2/2) | 2.34 (1.1x, 2/2) | 1.59 (0.7x, 1/2) | 4.68 (2/2) |
| mesquite | 2.95 (2/2) | 2.85 (1.0x, 2/2) | 3.38 (1.1x, 2/2) | 2.96 (1.0x, 2/2) | 2.81 (1.0x, 2/2) | 3.07 (1.0x, 2/2) | 3.24 (1.1x, 2/2) | 2.01 (0.7x, 0/2) | 3.28 (1.1x, 2/2) | 2.63 (0.9x, 2/2) | 3.97 (2/2) |
| nes2000 | 2.48 (2/2) | 3.07 (1.2x, 2/2) | 3.13 (1.3x, 2/2) | 2.67 (1.1x, 2/2) | 2.14 (0.9x, 2/2) | 2.51 (1.0x, 2/2) | 2.76 (1.1x, 2/2) | 1.64 (0.7x, 1/2) | 2.40 (1.0x, 2/2) | 2.90 (1.2x, 2/2) | 5.07 (2/2) |
| geomean x baseline, 7 models | 1 | **1.79** | 1.65 | 1.71 | 0.96 | 1.09 | 0.91 | 0.72 | 0.50 | 1.32 | — |
| geomean, 3 controls | 1 | 1.08 | 1.11 | 0.98 | 0.87 | 1.03 | 0.99 | 0.70 | 1.05 | 0.91 | — |
| cells passing | 12/14 | 11/14 | 9/14 | 12/14 | 11/14 | 12/14 | 12/14 | 8/14 | 9/14 | 11/14 | 14/14 |

Final steps (80101, per chain): `sblrc` baseline 0.0029–0.0035, `reg`
0.10–0.11, CmdStan 0.12–0.13; `earnings` baseline 0.0027–0.0032, `reg`
0.013–0.019, CmdStan 0.016–0.018; `arma11` baseline 0.06–0.11, `reg`
0.03–0.80, CmdStan 0.13–0.81; `kidiq` baseline 0.05–0.07, `reg` 0.10–0.11,
CmdStan 0.09–0.11. Every non-metric arm leaves `sblrc` and `earnings` at
0.003–0.006. Retained depth-cap rate: `earnings` baseline 0.115 and 0.108,
every `reg` arm 0.000 (CmdStan 0.000); `diamonds` 0.19–0.25 for every
oWALNUTS arm, CmdStan 0.79.

### Predictions

| | prediction | result |
|---|---|---|
| P1 | `reg` >= 3x on `sblrc` and `earnings`, >= 1.0x on `diamonds`; `h` within 0.5–2x CmdStan; non-metric arms leave `h` within 2x baseline | **half**: `sblrc` 9.7x, `h` 0.85x CmdStan; `earnings` **1.9x** (2.4x with the re-search), `h` 0.9x CmdStan; `diamonds` 0.90x (its `h` is not floored; seed spread 0.15–0.19 either way). Non-metric arms: `h` 0.003–0.006 on both models, held |
| P2 | no control below 0.9x baseline under `reg` beyond seed noise | **held**: kidiq 1.06x, mesquite 0.97x, nes2000 1.24x |
| P3 | `reg` >= 0.5x CmdStan on `sblrc`, `earnings`; `reg+research` and `stan-style` within 0.7–1.4x of `reg` everywhere | **half**: `sblrc` 0.55x, `earnings` 0.48x; `reg+research` within 0.6–1.2x (arma11 0.6x); `stan-style` 0.4–1.0x (earnings 0.40x, kidiq 0.69x) |
| P4 | `shrink:10` freezes an `arma11` chain | **held**: one chain per seed at `h = 5e-7`, min bulk ESS 7, R-hat 1.53 |
| P5 | `reg` has no frozen `arma11` chain and passes where baseline passes | **held**: 0 frozen, 2/2 (2.9x baseline, 0.6x CmdStan) |

### What the table says

1. **The Stan regularisation is the remedy for the collapse, and it is not
   free on `earnings`.** `reg` is the only single option that moves the
   collapsed models (`sblrc` 9.7x with `h` at CmdStan's; `earnings` 1.9x
   with `h` at CmdStan's and zero depth-cap orbits against 11 %) and it
   costs nothing on the controls (1.08x geomean, kidiq 1.06x, nes2000
   1.24x, `arma11`'s healthy chains 2.9x). But on `earnings` the `reg`
   chains end with min bulk ESS 164–179 and R-hat 1.019–1.021 where the
   baseline had 1,100 and 1.003 at 13x the gradients: at CmdStan's step
   and metric the WALNUTS orbit is a third of NUTS's (`reg` 80101 chain 0:
   49 leaves per orbit, 70 % of orbits ended by the recursive U-turn, macro
   length 0.63; CmdStan 163 leapfrogs at the same `h`, depth 6–8; the
   baseline's 707 leaves at `h = 0.003` reach macro length 1.9) and the
   per-draw ESS is a quarter of CmdStan's (250 vs 1,050 per coordinate on
   4,000 draws). That is the kernel-side gap of `adaptation_parity_v1`
   finding 5, now with a location: the U-turn rules under a well-scaled
   metric on a correlated regression. It is outside a warmup study, and it
   is why `earnings` loses its gate under every metric-fixing arm
   (`reg`, `reg+ramp`, `reg+research`, `stan-style`: 0/2 each).
2. **Nothing on the step side matters for (a).** Stan's statistic, Stan's
   `init_stepsize` at every window boundary, the delta ramp, a floor at
   half the search result and a bound on the within-stream shrink leave
   the collapsed `h` where it is (P1's second clause) and the seven-model
   geomean within 0.72–1.09x; the floor arms are net losses (the search
   result overshoots on `mesquite`/`nes2000`/`arma11` and the floor holds
   `h` there: 0.70x on the controls, 8/14 gates).
3. **`shrink:10` is the negative control** it was preregistered as: the
   `arma11` chains that need to slide through 30 orders of magnitude are
   pinned at the bound (2 frozen chains, 0.01x), while every other model is
   unchanged (1.05x on the controls). Any floor on the warmup step is
   incompatible with the WP24 escape.
4. **`diamonds` is not a collapse model at depth 10**: every arm including
   CmdStan runs at `h = 0.003–0.004`; the `reg+ramp` loss there (0.47x, 0/2)
   is one seed's two chains at R-hat 1.02 and is not seen under `reg` or
   `reg+research`.
5. **`arma11` 80101–80102 have no wall start**; the unit floor was still
   costing 2.9x on the healthy chains (`reg` `h` 0.67–0.80 vs CmdStan
   0.69–0.81, baseline 0.06–0.11).

## 3. Decision

**No default flip.** The preregistered rule required `reg` to fix all three
collapsing models with no control loss; it fixes `sblrc` (9.7x, gates 1/2
on an R-hat 1.011 miss), lifts `earnings` 1.9x but drops its gates (R-hat
1.02 from the short-orbit kernel behaviour at the corrected metric), and
leaves `diamonds` (not a collapse case) within seed noise. `sblrc`'s cell
alone is not enough to make a default of a change that turns a passing
`earnings` into a failing one.

What becomes of each candidate:

* `DiagonalMetricRegularization::Stan` stays opt-in and is now the
  **recommended option for regressions whose coefficients have posterior
  scales below ~0.1** (the unit floor `5 / (n + 5)` is 0.0099 at `n = 500`):
  `Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::Stan))`.
  The `stan_style` preset carries it too but loses 10–30 % on the controls
  and `earnings` here; `reg` alone is the better opt-in.
* `WarmupConfig::with_step_floor_relative_to_search` and
  `with_max_window_shrink` are kept as opt-in options with their table rows
  as the warning: neither helps a collapse (P1) and both hurt elsewhere.
* The per-chain R-hat attribution (`diagnostics::ChainDisagreement`) is in
  `Summary` unconditionally — it costs one R-hat per chain per parameter
  and only computes when the pooled R-hat already fails.

Follow-ups this study points at, in order: (i) the retained-kernel orbit
length under a correctly scaled metric on correlated regressions
(`earnings` `reg`: 49 leaves vs NUTS's 163 at the same `h`; the
`UTurnRule` alternatives and the recursive check are the suspects) — the
fix for that is what would let the Stan regularisation be the default;
(ii) a scale-free regularisation (shrink toward the window's own median
variance rather than toward one) as a default candidate that does not
inherit Stan's absolute 1e-3 floor; (iii) a cross-chain restart at the last
slow window for the `arma11`-type start that both samplers crawl on, or an
init rule that rejects starts with |log density| beyond ~1e18 on this
model (44 % of uniform draws; `freeze_mode_v1` appendix).

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 cmdstanpy==1.3.0 posteriordb numpy pandas xarray
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
MAKE=mingw32-make .venv/Scripts/python build_models.py
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/../../target cargo build --release
bash run_cell.sh sblrc__blr 79101 baseline && .venv/Scripts/python trace_summary.py artifacts/telemetry/sblrc__blr-baseline-79101.json 0
.venv/Scripts/python cmdstan_trace.py artifacts/telemetry/sblrc__blr-baseline-79101.json
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_table.py run      # ~40 min, resumable
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_table.py analyze
```

CmdStan 2.39.0 is expected at `CMDSTAN_HOME` in `cmdstan_trace.py`.
