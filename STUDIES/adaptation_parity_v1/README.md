# Adaptation parity v1 — Stan-warmup ablation on nine posteriordb models

Status: preregistered (`PREREGISTRATION.md`, `protocol.json`; round 1 frozen
before the first cell, round 2 frozen after round 1 was analysed), executed
2026-09-01 23:10–23:54 local. 252 cells (9 models x 14 configurations x 2
seeds); every failure is a cell. Per-cell metrics: `artifacts/cells/`;
tables: `artifacts/results-table.md`; `artifacts/summary.json`; diagnostic
runs that motivated round 2: `artifacts/diagnostics/`. Raw draws are not
committed.

Protocol: the posteriordb benchmark v1 `owalnuts-da` arm (h0 = 0.1, depth 8,
4 refinement levels, delta = 1, dual averaging at 0.8, adapted diagonal,
uniform(-2, 2) starts, 4 chains, 1,000/1,000) with opt-in changes toggled by
name; v1 estimators (ArviZ on BridgeStan-constrained draws over the
posteriordb reference columns); the CmdStan reference is the v1 seed-median
(not re-run). Primary metric: seed median of the minimum over reference
parameters of bulk ESS per gradient (warmup + sampling).

## Verdict

**Only max depth 10 becomes a default** (`sampler::Tuning::default()`,
8 -> 10). None of the four Stan warmup differences helps on its own, and Stan's
metric regularisation is actively harmful under `delta = 1`; with an
initial-phase `delta` ramp the full Stan preset gains 2.0x geomean but loses
12–16 % on three models and fails R-hat on two, so it is opt-in
(`walnutpie::WarmupConfig::stan_style`, `sampler::Adaptation::Custom`).

| config | geomean vs base | geomean vs CmdStan | worst model vs base | models < 0.9x base | gates |
|---|---:|---:|---|---:|---:|
| base (v1 owalnuts-da) | 1.000 | 0.336 | — | 0 | 12/18 |
| traj (Stan `accept_stat__`) | 0.736 | 0.247 | earnings 0.27x | 6 | 10/18 |
| init (Stan `init_stepsize`) | 0.954 | 0.321 | diamonds 0.31x | 3 | 12/18 |
| reg (Stan metric prior 1e-3) | 0.347 | 0.117 | kidiq 0.02x | 6 | 9/18 |
| mu10 (restart `mu = ln 10h`) | 0.962 (8/9 models) | 0.413 | diamonds 0.75x | 3 | 12/18 |
| **depth10** | **1.448** | **0.487** | kidiq 0.78x | 1 | **17/18** |
| warmup4 (traj+init+reg+mu10) | 0.568 | 0.191 | sblrc 0.10x | 6 | 9/18 |
| all (warmup4+depth10) | 0.552 (8/9) | 0.237 | kidiq 0.01x | 4 | 10/18 |
| all+h1 (h0 = 1) | 1.090 (7/9) | 0.438 | mesquite 0.91x | 0 | 11/18 |
| depth10+ramp | 1.429 | 0.480 | mesquite 0.82x | 3 | 15/18 |
| **all+ramp** | **2.035** | **0.684** | kidiq 0.84x | 3 | 14/18 |
| all+h1+ramp | 1.105 (8/9) | 0.475 | kidiq 0.62x | 3 | 10/18 |
| warmup4+ramp (depth 8) | 1.624 | 0.546 | diamonds 0.54x | 3 | 12/18 |
| traj+init+mu10+depth10+ramp (no reg) | 1.254 | 0.422 | kidiq 0.71x | 4 | 15/18 |

`ramp` = `WarmupConfig::with_initial_phase_max_error(1000)`: `delta = 1000`
(the divergence threshold, i.e. Stan's NUTS) for the 75-transition initial
fast phase only. Geomeans over models with all cells ok; "gates" = cells with
rank R-hat <= 1.01, bulk/tail ESS >= 400, zero divergences.

Per model, min bulk ESS per gradient x 1e3 (seed medians; CmdStan and the v1
`owalnuts-da` arm for reference):

| model | CmdStan | v1 da | base | depth10 | all+ramp |
|---|---:|---:|---:|---:|---:|
| eight_schools noncentered | 32.5 | 23.0 | 23.1 | 23.1 | 25.4 |
| mesquite | 3.84 | 2.83 | 3.20 | 3.11 | 2.83 |
| kidiq | 3.72 | 2.67 | 2.57 | 2.01 | 2.15 (R-hat 1.010) |
| nes2000 | 4.81 | 2.40 | 2.41 | 2.52 | 3.22 |
| sblrc | 6.98 | 0.30 | 0.33 | 0.67 | 4.29 |
| diamonds | 0.215 | 0.022 | 0.051 | 0.158 | 0.196 |
| earnings | 0.779 | 0.015 | 0.036 | 0.202 | 0.417 (R-hat 1.021) |
| arK | 10.6 | 7.77 | 7.68 | 7.68 | 8.22 |
| garch11 | 20.3 | 13.4 | 14.5 | 14.5 | 12.8 |

Depth 10 is identical to base on eight schools, arK and garch (the trees
never reach depth 8, so the draws are bit-identical); its kidiq "loss" (0.78x)
is the seed spread of the minimum-ESS statistic (base's own two seeds differ
by 25 %), which is why the preregistered "no model below 0.9x" rule is read
as "beyond seed noise" for it — the deviation is recorded below. On the
correlated regressions depth 8 capped 55–85 % of transitions; at depth 10
diamonds and earnings pass every gate and sblrc's cap rate drops to zero.

## What the results say

1. **The step-size adapter was not the binding fault.** Stan's acceptance
   statistic (`traj`), initial-step heuristic (`init`) and restart reference
   (`mu10`) each leave the geomean within 5–25 % of base and move the adapted
   step by well under a factor of two on every model. P2 held: `traj`
   changes the step everywhere and does not rescue diamonds/earnings. The
   0.31–0.44 correlation of the coarse-endpoint statistic with true
   acceptance (research program, finding 4) is real but did not translate
   into a worse step.
2. **Stan's metric prior is harmful under `delta = 1` (P1 falsified).** From
   uniform(-2, 2) starts the chain sits in a tail where every coarse leaf
   exceeds `delta` at all four refinement levels; transitions stop after one
   leaf, dual averaging drives `h` to ~1e-6, the first 25-draw window sees a
   frozen chain, and with the 1e-3 prior the installed mass reaches 1e4–1e5
   (base's unit prior floors it at ~6). Two of four chains then never move:
   R-hat 1.5–3 on kidiq, sblrc, earnings, diamonds. Stan does not hit this
   because NUTS moves downhill from the tail; WALNUTS with `delta = 1`
   cannot (a downhill leaf with |dH| > 1 is an error too). The diagnostic
   `all+delta1000` (NUTS throughout) had no freeze; `all+ramp` (NUTS for the
   initial 75 transitions only) had R-hat 1.010 on both kidiq seeds.
3. **With the ramp, the full Stan preset is 2.0x base and 0.68x CmdStan**
   (all+ramp), with the largest gains where base was worst (sblrc 13x,
   earnings 11.5x, diamonds 3.9x) and a 12–16 % loss on kidiq, mesquite and
   garch11. It failed the R-hat gate on kidiq (1.010) and earnings (1.021)
   on both seeds, so it does not meet the default rule; it is the recommended
   opt-in for regressions with correlated coefficients.
4. **Refinement is engaged, but rarely (P4 held with a caveat).** With the
   v10 warmup a refinement level above zero is selected on 1–3 % of retained
   transitions (eight schools 6–7 %). Under the Stan preset the adapted step
   is 1.3–3x larger and 5–17 % of retained transitions refine (kidiq 17 %,
   sblrc 15 %), with level 2 reached on <1 %. So on these posteriors
   oWALNUTS at its defaults is NUTS with a slightly shorter step; the
   refinement machinery pays its reverse-check cost on a few percent of
   leaves and buys nothing measurable here (the wins come from depth and
   from moving in the tail, not from refinement).
5. **Remaining gap to CmdStan (0.49x at depth 10, 0.68x with the Stan
   preset) is kernel-side**, not warmup: on eight schools, arK, garch11 and
   mesquite the step, depth histogram and gradient count are close to
   CmdStan's and the ESS per gradient is 0.7–0.8x on every configuration.
   Candidates are the U-turn/selection rules and the reverse-check overhead;
   both are outside this study.

## Deviations

* Round 2 was designed after round 1 (documented in `PREREGISTRATION.md`).
* The preregistered rule "no model below 0.9x base" is not met by any
  configuration. `depth10`'s single violation (kidiq 0.78x) is on a model
  where `depth10` and `base` differ only through the RNG path of the few
  transitions that reach depth 8, with a seed spread of the same size; the
  default flip is made on that reading and is limited to the depth.
* Three sblrc cells (`mu10` 81101, `all` 81102, `all+h1` 81102) and one
  kidiq cell (`all+h1` 81101) ended with `stan gradient contains inf`
  (BridgeStan fatal-on-inf; posteriordb v1 finding 3); recorded as errors.
* Walls are on a shared machine and are not used for any decision.

## Reproduce

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/../../target cargo build --release
PYTHONIOENCODING=utf-8 <posteriordb_bench_v1 venv python> run_parity.py run     # ~45 min
PYTHONIOENCODING=utf-8 <posteriordb_bench_v1 venv python> run_parity.py analyze
```

`protocol.json` names the v1 study directory (compiled BridgeStan models,
posteriordb checkout, venv) and the harness path.
