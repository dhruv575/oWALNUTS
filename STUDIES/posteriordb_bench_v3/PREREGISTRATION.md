# posteriordb benchmark v3 — preregistration

Frozen before execution on 2026-09-02 (see `protocol.json`; its SHA-256 is the
first line of `CHECKSUMS.sha256`). Nothing in this file or in `protocol.json`
is edited after the first evidence cell starts; deviations are appended under
"Deviations" with a timestamp.

## Question

`STUDIES/posteriordb_bench_v2` (seeds 78101–78103, sampler 0.2.0 defaults)
recorded the DA arm at 32/51 gates, 0.233x CmdStan's bulk ESS per gradient
over all 17 models (0.447x excluding `arma11` and `lotka_volterra`, where
oWALNUTS chains froze) and 0.77x CmdStan's wall per gradient. `STUDIES/
freeze_mode_v1` (WP24) then traced the freeze to WALNUTS' two-sided leaf test
driving dual averaging into a floating-point no-op equilibrium, and made
`ExhaustionRule::AcceptUnlessDivergent` the `sampler` default for warmup
transitions (`sampler::DEFAULT_WARMUP_EXHAUSTION`); on the v2 seeds it
unfroze all twelve `arma11` chains (min bulk ESS 1,418, 3/3) and took
`lotka_volterra` to 2/3. **Does that default hold up on the full v2 protocol
with fresh seeds — does it recover `arma11`, leave every other model within
seed noise of v2, and move the breadth figures past the v2 release gate?**
This is the breadth confirmation named in the WP24 ledger entry.

## What is identical to v2

Model set (17 posteriordb posteriors, commit `28f8d3d`), 4 chains, 1,000
warmup, 1,000 retained, `Tuning::default()` (`h0 = 0.5`, depth 10, 4
refinement levels, `delta = 1`), `Metric::diagonal()`, dual averaging at 0.8,
`Init::uniform()` starts drawn through `sampler::uniform_starts` with the
cell seed, `Limits::admit_worst_case()`, `ReplicatedStanTarget` on a
BridgeStan 2.9.0 / Stan 2.39.0 library built **without** `STAN_THREADS`,
CmdStan 2.39.0 via cmdstanpy 1.3.0 defaults, nutpie 0.16.8 defaults, ArviZ
0.23.4 estimators, gates (rank R-hat <= 1.01, bulk and tail ESS >= 400 on
every reference parameter, zero sampling divergences, finite draws, no
sampler error), metrics, 45-minute cell timeout, strictly sequential run
order, the frozen-chain definition (> 500 of 1,000 retained transitions in
refinement exhaustion), and the driver (`run_posteriordb.py`, edited only
for the arm list, the v2 comparison and the predictions).

## What differs

1. **The harness is rebuilt against the current `src/`** (`3e2da75`, main
   after the WP24 merge), so `Adaptation::DualAveraging` applies
   `ExhaustionRule::AcceptUnlessDivergent` to warmup transitions. Retained
   transitions keep the frozen `Stop` rule, so the draw-generating kernel
   after warmup is the v2 kernel (revision string unchanged). The harness
   records the rule in each cell's `warmup_config`. The stan-style arm uses
   `Adaptation::Custom(WarmupConfig::stan_style(0.8))`, which is used as
   given (two-sided, exactly as v2): it is the within-study control for
   "same seeds, same build, no rule change".
2. **Seeds 79101, 79102, 79103** (grep of `wiki/`, `STUDIES/`, `src/`,
   `integrations/` before freezing: no occurrence as a seed).
3. **Four arms**: `owalnuts-da`, `owalnuts-stan-style`, `cmdstan`, `nutpie`.
   The paper arm is dropped (it tracked DA at 0.995x per gradient in v2 and
   shares the DA arm's warmup rule; nothing in the WP24 decision depends on
   it). 17 x 4 x 3 = 204 cells.
4. **Compiled models**: the v2 compiled libraries, venv and posteriordb
   checkout were in the removed v2 worktree and no longer exist, so every
   model is compiled fresh with the same toolchain and flags (recorded in
   `protocol.json`). The posteriordb checkout is a fresh shallow clone at
   the same commit, as in v2.

Before freezing, the rebuilt harness was smoke-tested on `arma11` with seed 1
(DA arm only, not a study seed, output deleted) to confirm that the rebuilt
binary picks up the new default — the chains move and the final steps are
O(0.1) rather than 1e-20.

## Preregistered analysis

1. Per-model table and head-to-head as v2 for the two oWALNUTS arms:
   geometric mean over models complete on both sides of seed-median ratios
   of min bulk ESS/gradient, min bulk ESS/s and wall per gradient against
   CmdStan and nutpie; wins per model; outright wins.
2. v2-vs-v3 table: per model and arm (da, stan-style, cmdstan, nutpie), the
   seed-median v3/v2 ratio of ESS/gradient and ESS/s, and the headline
   numbers side by side. The cmdstan, nutpie and stan-style rows measure
   seed noise and machine load; the DA row measures the WP24 rule plus seed
   noise.
3. Predictions (`protocol.json`):
   * **P1** owalnuts-da passes all gates on >= 33 of 51 cells (v2: 32).
   * **P2** owalnuts-da passes >= 2 of 3 `arma11` seeds (v2: 0/3).
   * **P3** owalnuts-da geomean bulk ESS/gradient vs CmdStan >= 0.40 over
     all 17 models (v2: 0.233); **P3b** >= 0.45 over the 16 models excluding
     `lotka_volterra` (whose seed-dependent ODE-boundary starts are outside
     the WP24 fix).
   * **P4** no model has owalnuts-da seed-median bulk ESS/gradient below
     0.8x its v2 value: the rule only changes warmup where a leaf exhausts,
     so the healthy models should differ from v2 by seed noise only.
   * **P5** owalnuts-da geomean wall per gradient <= 1.0x CmdStan (v2:
     0.771).
   Also expected but not gated: `lotka_volterra` DA between 1/3 and 3/3
   depending on whether a seed starts on the `rk45` failure boundary;
   centered eight schools, `accel_gp`, `one_comp` still fail for every arm;
   stan-style freezes on `arma11` wherever a start is past the overflow
   wall (about 44 % of starts per chain).

No default changes from this study. The release gate for a breadth claim is
P1, P3 and P5 together.

## Reporting

`artifacts/summary.json`, `artifacts/results-table.md`, `README.md`
(verdict), `LEDGER-ENTRY.md`, `CHECKSUMS.sha256` (raw draws hashed, not
committed; CmdStan CSVs neither hashed nor committed). Failures are results;
no cell is rerun; nothing is tuned after seeing results. A driver crash is
relaunched and the interrupted cell re-run from scratch (seeded), logged
below.

## Load caveat

Shared 16-thread machine (Intel Core Ultra 7 255H, Windows 11); other agents
may run during execution. Walls are upper bounds; ESS per gradient is the
machine-independent primary figure.

## Deviations

(none at freeze)
