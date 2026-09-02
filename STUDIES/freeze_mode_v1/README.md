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

Full per-cell table: `artifacts/results-table.md` (from `analyze.py`);
per-cell JSON with the four chains' escape transitions and final steps:
`artifacts/table/`. Seed medians (frozen chains of 12 / seeds with min bulk
ESS >= 400 / median min bulk ESS / median min bulk ESS per gradient x1e3):

| arm | arma11 | lotka_volterra |
|---|---|---|
| baseline | 7 / 0/3 / 4.4 / 0.035 | 0 / 1/3 / 6.8 / 0.026 |
| exhaust-accept | 7 / 0/3 / 4.4 / 0.035 | 0 / 1/3 / 122 / 0.48 |
| mean-accept | 7 / 0/3 / 4.4 / 0.035 | 0 / 1/3 / 6.7 / 0.027 |
| stan-style | 7 / 0/3 / 4.4 / 0.026 | 0 / 2/3 / 763 / 3.2 |
| step-floor | 9 / 0/3 / 4.1 / 0.0036 | 3 / 1/3 / 7.2 / 0.0058 |
| **exhaust-signed** | **0 / 3/3 / 1418 / 13.5** | **0 / 2/3 / 842 / 2.9** |
| exhaust-signed+mean-accept | 2 / 2/3 / 1413 / 12.8 | 0 / 2/3 / 752 / 2.6 |
| stan-style+exhaust-signed | 2 / 1/3 / 7.2 / 0.0032 | 0 / 2/3 / 745 / 3.1 |
| **warmup-signed** | **0 / 3/3 / 1418 / 13.5** | **0 / 2/3 / 842 / 2.9** |

`arma11`: `warmup-signed` and `exhaust-signed` produce identical cells (the
retained transitions never exhaust once the chain is in the bulk, so the
retained rule is inert there): every one of the seven v2-frozen chains
escapes, at warmup transitions 6-85 (start log density -4.5e19 to
-1.8e115), all twelve final steps are 0.03-0.12, max R-hat 1.003, min bulk
ESS 1,290-1,460 against the healthy v2 chains' ~1,400 (P1 held). Every
two-sided arm -- `baseline`, `exhaust-accept`, `mean-accept`, `stan-style` --
freezes exactly the v2 chains with the same final steps to three digits
(P2 and the first half of P3 held); `step-floor` freezes two more (floored
warmup steps fail every leaf) at 10x the gradients (P2 held).
`exhaust-signed+mean-accept` re-freezes two 78103 chains (Stan's statistic
at the no-op pin sends orbits to depth 10, 4.2 M gradients, without leaving
it) and `stan-style+exhaust-signed` re-freezes one chain per seed on
78101/78103 (the preset's Stan metric prior and initial step search after
the slide): P5 and the second half of P3 did **not** hold -- the rule works
with the coarse-endpoint statistic and the default warmup, not with Stan's.

`lotka_volterra`: no arm has a frozen chain by the study's definition except
`step-floor` (3); `warmup-signed` / `exhaust-signed` pass 78101 and 78103
(min bulk ESS 900 and 842; the baseline's 78103 was 6.8 with one chain at
`h = 3.6e-6`) and, as predicted (P4), not 78102, whose two chains start on
the `rk45` failure boundary: they move every transition (escape at 0-2)
but crawl down a stiff valley at `h ~ 3e-6 to 4e-5` with depth-9/10 orbits
(2.6 M gradients on the cell, min bulk ESS 4.5). No arm passes that seed;
`stan-style` (the v2 stan-style arm) is at the same 2/3.

## 4. Side checks

`src/bin/checks.rs`, `artifacts/checks/`; sampler defaults, seed
`0x0f0f2026`.

| check | variant | grads | retained exhaustions | divergences | min bulk ESS | max R-hat | tail mass (exact 0.0478) | z |
|---|---|---:|---:|---:|---:|---:|---|---:|
| funnel 4 x 2,000/20,000 | baseline | 2,483,660 | 812 | 9 | 137 | 1.019 | 0.0236 +- 0.0142 | -1.70 |
| funnel | exhaust-accept | 2,550,810 | 19 | 19 | 243 | 1.011 | 0.0133 +- 0.0047 | -7.30 |
| funnel | exhaust-signed | 2,509,800 | 26 | 27 | 249 | 1.010 | 0.0141 +- 0.0047 | -7.20 |
| funnel | **warmup-signed** | 2,535,045 | 748 | 9 | 148 | 1.024 | 0.0214 +- 0.0142 | -1.85 |
| eight schools centered 4 x 1,000/1,000 | baseline | 164,460 | 2 | 0 | 21 | 1.138 | | |
| eight schools centered | exhaust-signed | 145,936 | 1 | 1 | 104 | 1.027 | | |
| eight schools centered | **warmup-signed** | 145,914 | 1 | 0 | 104 | 1.027 | | |

Two findings beyond P6 (held: `warmup-signed` |z| = 1.85, 748 retained
exhaustions against the baseline's 812, the same draw-generating kernel
after warmup): (i) **any rule that keeps exhausted leaves in retained
transitions loses the funnel neck at the sampler's four levels** -- the
existing two-sided `AcceptBelowDivergenceThreshold` (z = -7.3) as much as
the one-sided rule (z = -7.2). `kernel_efficiency_v1` had cleared
`AcceptBelowDivergenceThreshold` on the funnel at eight levels, where
nothing exhausts; at four levels the exhaustion stop *is* what keeps the
tail mass, so neither accepting rule is a retained-phase default. (ii) The
baseline funnel at the sampler defaults is itself poor from these starts
(min bulk ESS 137, z = -1.7): a separate matter (four levels, `h0 = 0.5`),
recorded, not pursued.

Fingerprints: `tests/kernel_fingerprint.rs` (which pins `RunConfig`
defaults, untouched) and the full suites pass with and without `research`
before and after the default flip; `tests/sampler_api.rs` mirrors the new
default in its direct `WarmupConfig`s.

## 5. Decision

`warmup-signed` becomes the `sampler` default: `Adaptation::DualAveraging`
and `Adaptation::Paper` apply `sampler::DEFAULT_WARMUP_EXHAUSTION =
ExhaustionRule::AcceptUnlessDivergent` to the discarded transitions;
retained transitions keep `Tuning::kernel_options` (the frozen `Stop`);
`Adaptation::Custom` is used as given. The kernel revision is unchanged:
no retained draw of the frozen kernel changes, and warmup differs only
where a leaf exhausts. Not recommended: the rule for retained draws
(section 4), Stan's statistic or preset with the rule (section 3), a step
floor, an init check. The v3 posteriordb protocol is the breadth
confirmation.

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
