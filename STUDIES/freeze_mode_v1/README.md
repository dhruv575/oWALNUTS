# freeze_mode_v1 — why oWALNUTS chains freeze from bad starts, and the rule that lets them out

Status: diagnostic study with a preregistered confirmation table, executed
2026-09-02 on branch `wt/freeze-mode`. Section 1 (diagnosis) and section 2
(the candidate rule) were developed against the three `posteriordb_bench_v2`
seeds of `arma11` and `lotka_volterra` and are *not* preregistered; section
3 is the preregistered arm table (candidate list and predictions written and
committed before the table was run), section 4 the side checks that gate a
default flip. Driver: `src/main.rs` (one posteriordb cell from the v2 starts
with per-transition telemetry), `src/bin/checks.rs` (funnel tail mass,
centered Eight Schools). Per-transition telemetry of every run is under
`artifacts/telemetry/` (uncommitted, regenerable); tables and per-cell
summaries under `artifacts/`.

## 1. The mechanism

### 1a. What the frozen chains do

The v2 driver's starts are `sampler::uniform_starts` with the cell's seed, so
the study driver reproduces the v2 cells bit for bit (final `h` values equal
to the v2 metrics to all digits). Two new additive diagnostics on
`walnutpie::TransitionDiagnostics` (`step_size`, `position_changed`, and the
dual-averaging input `acceptance_statistic`) make the per-transition trace
readable.

`arma11`, all seven frozen chains (78101 chain 0; 78102 chains 2–3; 78103
chains 0–3): the start's log density is **−4.5e19 to −1.8e115** with a
gradient about 220–300 times that (the healthy chains start at −3e2 to
−2e5). The ARMA(1,1) moving-average recursion `err[t] = y[t] − mu − phi
y[t−1] − theta err[t−1]` grows like `theta^t` over `T = 200` observations, so
for `|theta| > 1` the log density is `−C theta^400` and 44 % of uniform(−2,
2) starts have `|logp| > 4e18` (Monte Carlo over 4,000 draws, `analysis`
in this README's appendix). From such a start:

1. Transitions 0–30: every leaf of every level lands in the overflow region
   (`err` overflows, Stan throws, BridgeStan maps it to a recoverable
   failure, the kernel sees `logp = −inf`): 15 recoverable failures per
   transition (1 + 2 + 4 + 8 attempts), every transition an exhaustion, dual
   averaging sees statistic 0 and shrinks `h` by ~13x per transition.
2. Once `h < ~1/|grad|` the momentum kick `h · grad` is O(1) and the position
   update `h · v` is below the unit in the last place of the coordinates:
   `q + h v == q`. The kinetic energy of the kicked momentum is itself below
   the ulp of `U ~ 1e50` (`5e84 < 2e87`), so the level-0 endpoint error is
   **exactly 0**, the leaf is "accepted", and the statistic is 1. After 3–6
   such leaves the accumulated kick exceeds one ulp of `U`, the error jumps
   to `~1e33–1e87`, all levels fail, the orbit ends in exhaustion with
   statistic 0. Mean statistic ≈ 0.8: **dual averaging has a stable
   equilibrium at `h ≈ 1e-20 … 1e-68` in which the position never changes.**
   Every retained transition is both a divergence and an exhaustion, and all
   1,000 draws equal the start (bulk ESS 4).

`lotka_volterra`, the slow chains (78102 chains 1 and 3, 78103 chain 1): the
start's log density is a mundane −1.3e4 (ODE solution far from the data,
lognormal residual scale `sigma ~ e^-1.5`), and the chain **does move** — by
`H_0 ≈ 0.08` per transition (13,004 → 12,843 over 2,000 transitions).
Every transition ends in an exhaustion after 20–100 leaves at `h ≈ 1e-5`,
with an endpoint error of ≈ 50 **that does not depend on `h`**: it is the
`rk45` tolerance (relative 1e-5, `max_num_steps` 500) multiplied by the 1e4
residual scale, a numerical discontinuity of the log density that
refinement cannot shrink. `delta = 1` ends the orbit at every such jump;
dual averaging pins `h` to the value at which the next jump is ~20 leaves
away; the chain crawls. CmdStan, started from these exact points, rejects
them at initialisation ("lognormal_lpdf: Location parameter is nan" — the
ODE solution is NaN after the exp/log round trip of the init file): the
starts sit on the solver's failure boundary.

### 1b. Why NUTS escapes and WALNUTS does not

CmdStan 2.39 was run from each of the seven frozen `arma11` starts
(`cmdstan/out/*.init.json`, two seeds each). **It escapes from all of them**,
including log density −1.8e115, reaching `lp ≈ 258` within warmup. The
warmup trace (`cmdstan/out/trace-78101c0.csv`, `trace-78103c1.csv`) shows
how: after ~30 iterations of divergences dual averaging reaches `h ≈ 1e-28`
(`1e-59` for the −1e115 start), where the leapfrog's *drift term* `h² ∇/2 ≈
0.02` moves `theta` downhill by 0.003–0.01 per step. The energy error of
that step is astronomically **negative** (`H` drops by 5e49): Stan's
divergence test is one-sided (`H − H_0 > 1000`), the leaf is accepted with
multinomial weight `∞`, `accept_stat = min(1, exp(H_0 − H)) = 1`, and `h`
*grows* 2.6x per iteration while the trajectory rides the integrator's
instability down the wall (`U` falls ~4x per iteration, ~400 iterations
from 1e114 to the bulk). Once the trajectory sits below `H_0`, a leaf's own
error — which at `U ~ 1e103` is rounding noise of ±1e89 with a random sign
— never ends the tree either.

WALNUTS' acceptance test is the two-sided `|H_end − H_start| ≤ delta` per
leaf (it has to be: the reverse-coarsening check needs a symmetric
statistic), so the same downhill leaf exhausts every level, the orbit
stops, and `exp(−|ΔH|) = 0` shrinks `h` toward the no-op equilibrium of 1a.
The existing `ExhaustionRule::AcceptBelowDivergenceThreshold` and the
`stan_style` preset's initial `delta = 1000` are two-sided as well, which
is why both froze in v2.

So the freeze is **(b) + (a)**: the two-sided leaf test turns every
downhill step into an exhaustion at the initial leaf, and the coarse
endpoint statistic then drives `h` into a floating-point no-op equilibrium.
It is not (c) the level cap (the first attempt already overflows or already
cannot move), not (d) momentum (2,000 fresh momenta per frozen chain, none
succeeded), and not (e) the start check (Stan's rule accepts the same
starts and Stan escapes; a check that rejected them would discard 44 % of
`arma11` starts NUTS handles).

## 2. The rule: `ExhaustionRule::AcceptUnlessDivergent`

When a leaf fails `delta` at every refinement level, keep the finest
attempt unless it is divergent in Stan's sense: `H_end − H_0 > 
divergence_threshold`, with `H_0` the transition's initial Hamiltonian
(one-sided, relative to the transition, not the leaf), and feed Stan's
`min(1, exp(H_0 − H_end))` to the coarse-endpoint step statistic for that
leaf. Energy differences below the rounding noise of `H_0` (`|H_0| · 2^-40`,
`walnutpie::HAMILTONIAN_NOISE_RELATIVE`) count as zero: they cannot be
resolved, and without this the chain re-pins after its first slide (the
noise band between the no-op equilibrium and the slide band has a 50 %
rejection rate, and five consecutive rejections after a window restart
were measured to drop `h` four orders of magnitude into the no-op
equilibrium; Stan survived the same dip by luck, two rejections). The
reverse-coarsening check applies to the kept leaf as to any accepted level.

The rule differs from the frozen kernel only on leaves whose absolute error
exceeds `delta` at every level. On the healthy v2 cells of the DA arm, the
retained transitions contain **zero** such leaves on 14 of 17 models (the
exceptions: the centered Eight Schools, 41/1/39 of 4,000 transitions, and
the two freeze models), so the retained draws of those 14 models are
unchanged by construction; warmup differs wherever early leaves exhaust.
`tests/freeze_mode.rs` reproduces both the pin and the escape on a
4-D Gaussian with an exponential wall (no BridgeStan needed), and asserts
bit-identical draws from a start where nothing exhausts.

Iterations that were tried and dropped, with the trace that killed each
(section 1 telemetry, `artifacts/telemetry/arma11-exhaust-signed-*`):
per-leaf signed error `H_end − H_start ≤ threshold` (escapes 2 of 7: the
noise band re-pins the chain); transition-relative rise without the
rounding tolerance (escapes 4 of 7: the post-restart fall-through).

## 3. Preregistered arm table

Written before the table was run. Cells: `arma11` and `lotka_volterra`,
seeds 78101–78103, the v2 starts, 4 chains, 1,000/1,000, `Sampler`
defaults (`h0 0.5`, depth 10, four levels, `delta 1`, adapted diagonal
metric, dual averaging at 0.8, initial-evaluation cache) plus the arm's
options. ESS is the rank-normalised bulk ESS over the unconstrained
coordinates (`owalnuts::diagnostics`), minimum over coordinates; "frozen"
= a chain with no run of 50 transitions in which ≥ 45 move the position.

| arm | what |
|---|---|
| `baseline` | defaults (the v2 `owalnuts-da` cell) |
| `exhaust-accept` | `ExhaustionRule::AcceptBelowDivergenceThreshold` (two-sided; existing) |
| `mean-accept` | `DualAveragingAcceptance::MeanTrajectoryAcceptance` (Stan's statistic; existing) |
| `stan-style` | `WarmupConfig::stan_style(0.8)` (existing preset; the v2 `owalnuts-stan-style` cell) |
| `step-floor` | `WarmupConfig::with_minimum_step(1e-3)` (new, negative control) |
| **`exhaust-signed`** | `ExhaustionRule::AcceptUnlessDivergent` (new, section 2) |
| `exhaust-signed+mean-accept` | the new rule with Stan's statistic |
| `stan-style+exhaust-signed` | the new rule under the Stan preset |
| **`warmup-signed`** | `WarmupConfig::with_warmup_exhaustion_rule(AcceptUnlessDivergent)`: the new rule for the discarded transitions only, the frozen `Stop` for retained draws (amendment 1, below) |

Amendment 1 (written after the first funnel side check, before the table):
the first funnel run at the sampler defaults (4 chains x 2,000 / 20,000)
gave tail mass 0.0141 ± 0.0047 (z = −7.2) for `exhaust-signed` against
0.0236 ± 0.014 (z = −1.7, min bulk ESS 137) for `baseline`, with 812
retained exhaustions in the baseline. A leaf whose energy drops by more
than the divergence threshold is accepted forward but would be rejected in
reverse — Stan's asymmetry — and in the funnel neck that costs tail mass.
The candidate for the default is therefore the rule **during warmup only**
(`warmup-signed`): adaptation needs no reversibility, the retained kernel
stays the validated two-sided one. `exhaust-signed` stays in the table as
the kernel-side reference; P1–P5 apply to `warmup-signed` as written for
`exhaust-signed`, with P6: `warmup-signed`'s funnel tail mass is within
|z| < 2 of 0.0478 and its retained exhaustion count is of the baseline's
order.

Not run, excluded by the section 1 telemetry: "reject and refresh momentum
up to N times" (every frozen `arma11` chain tried 2,000 fresh momenta with
zero successful first leaves — the failure is in the leaf test, not the
momentum); "treat an all-exhausted transition as acceptance 0 with a
clamped shrink" (dual averaging already feeds 0 and every `h` from 0.5 down
to 1e-20 fails every leaf, so a clamp can only choose where to freeze);
"Stan-style init retry requiring a successful leapfrog" (Stan's own
`init_stepsize` accepts these starts at `h ~ 1e-28` — a no-op leapfrog
"succeeds" — and Stan escapes them, so the check would neither reject the
frozen starts nor be needed).

Predictions:

* P1: `exhaust-signed` has zero frozen chains on all six cells and its
  minimum bulk ESS on `arma11` is within 0.7–1.3x of the healthy v2 chains'
  (≥ 400 on every seed).
* P2: `baseline`, `exhaust-accept`, `step-floor` freeze on every `arma11`
  cell that froze in v2 (they do not touch the two-sided test), and
  `mean-accept` alone does not escape (the leaf is still rejected).
* P3: `stan-style` freezes on `arma11` as in v2; `stan-style+exhaust-signed`
  escapes.
* P4: on `lotka_volterra` `exhaust-signed` has zero frozen chains on all
  three seeds, but the 78102 chains that start on the solver boundary stay
  slow (bulk ESS < 400 on that seed) under every arm: a crawl through
  numerical noise is not a freeze, and the gradient count of that cell
  rises (long orbits instead of exhaustions).
* P5: `exhaust-signed+mean-accept` escapes like `exhaust-signed`; its
  `arma11` ESS per gradient is not better than `exhaust-signed`'s beyond
  seed noise (the parity study measured Stan's statistic alone at 0.74x).

Default-flip rule (section 4): `warmup-signed` becomes the `sampler`
default if P1 holds for it, the funnel tail mass is preserved (|z| < 2 against
0.0478 at the sampler defaults), the centered Eight Schools do not lose
more than seed noise, and the frozen fingerprints (`tests/kernel_fingerprint.rs`,
which pin `RunConfig` defaults, untouched by a `sampler` flip) still pass.

## 3. Results

(filled in after the table.)

## 4. Side checks

(filled in after the checks.)

## Appendix: start-density Monte Carlo

`.venv/Scripts/python`, BridgeStan 2.9.0, 4,000 uniform(−2, 2) draws per
model: `arma11` — `P(|logp| > 1e5) = 0.51`, `> 1e15` 0.46, `> 4e18` 0.44,
`> 1e30` 0.41, median 3e5, 90th percentile 5e101; `lotka_volterra` — 750 of
4,000 draws throw (ODE failure), the rest have `|logp| < 1e5` (median 4e3).

## Reproduce

```
uv venv --python 3.11 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 numpy
git clone --depth 1 --filter=blob:none --sparse https://github.com/stan-dev/posteriordb posteriordb  # 28f8d3d
# copy arma11 / lotka_volterra .stan and data into models/ (see build_models.py), then
MAKE=mingw32-make .venv/Scripts/python build_models.py
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu CARGO_TARGET_DIR=$PWD/target cargo build --release
bash run_table.sh          # the arm table (~40 min, lotka dominates)
target/release/checks funnel exhaust-signed artifacts/checks/funnel-exhaust-signed.json
python analyze.py          # artifacts/results-table.md
```
