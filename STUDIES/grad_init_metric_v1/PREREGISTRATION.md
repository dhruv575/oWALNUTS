# WP94 `grad_init_metric_v1`: preregistration

Frozen on `wt/grad-init-metric` (base `main` at `a042a728`; library commits `b512856a` clippy, `d6985347` the
flag) before the first evidence cell; the freeze commit is recorded in `README.md`. `protocol.json` is the
machine-readable copy and wins on any discrepancy. Ledger id `WP94-GRAD-INIT-METRIC-V1`.

## Question

Does the gradient-scaled initial metric qualify as a default-flip candidate? It is nutpie's initial mass
matrix: per chain, before any warmup transition, `mass_i = clamp(|g_i(start)|, 1e-20, 1e20)` with `g` the
log-density gradient at the chain's start (an entry that is not finite becomes 1). WP89
(`STUDIES/sv_stuck_chains_v1`) found that this one difference (`nutpie_init`, oWALNUTS's own starts and
adaptation) took oWALNUTS from 8/480 to 1/240 trapped chains on the WP84 SV model without any guard, because
the trap is a stiff high-`log_sigma` start whose first transitions are rejected under the *identity* metric
(the z-coordinates are wrong by 10-150x for every chain in the identity phase), the step collapses to 1e-7,
and the Stan floor is installed on every coordinate at transition 99. WP90 (`STUDIES/trap_guard_confirmation_v1`)
confirmed the restart guard, now the default, which removes the symptom (the trapped chain is restarted). The
gradient-scaled initial metric removes the cause: the first slow window is sampled with a sane metric. Because
it changes the metric of the first 100 transitions of every chain on every model, it needs the full house
test, and because the guard is now in the defaults, two questions are separated:

- `gradinit` (the candidate): defaults + the gradient-scaled initial metric. Is it at least as good as the
  defaults everywhere (R1-R5), does it leave 0/480 SV chains trapped, and does the guard then fire at all?
- `gradinit-noguard`: the initial metric with the guard opted out. Does the cause-level fix alone remove the
  traps (R6: at most 1/480, the WP89 prediction)?

## The library change (committed before any study cell: `d6985347`)

`src/walnutpie.rs`, behind `#[cfg(feature = "research")]`, default off, bit-identical when off:

- `InitialMetric::{AsGiven, GradientScaled { lower, upper }}`, `InitialMetric::nutpie()` (= 1e-20, 1e20),
  `WarmupConfig::with_initial_metric(..) -> Result<Self, Error>` (bounds finite, `0 < lower <= upper`),
  `WarmupConfig::initial_metric()`.
- **Rule and placement.** In `ChainRun::start_from`, the per-chain entry of every diagonal driver, right
  after the chain's start is known and before anything else: one `log_density_gradient` call at the start,
  then the given diagonal (the identity for the sampler's own metrics) is replaced by
  `clamp(|g_i|, lower, upper)` (1 where that is not finite). `RunMetadata::initial_mass_diagonal` reports
  the mass actually installed. This is nutpie's rule verbatim: nuts-rs 0.17.3 (the version nutpie 0.16.8
  pins), `src/mass_matrix/adapt.rs` `Strategy::init` calls `update_diag_grad(gradient, fill_invalid = 1,
  (INIT_LOWER_LIMIT, INIT_UPPER_LIMIT))` with both limits `1e-20` / `1e20`, and `src/cpu_math.rs`
  `array_update_var_inv_std_grad` sets `variance_i = 1 / clamp(|g_i|, lower, upper)` (the inverse mass),
  replacing a non-finite value by `fill_invalid`; nutpie uses `|g|`, not `g^2`.
- **Interactions.** (i) Best-of-16 starts: the facade chooses the start first (same 16 candidates and chosen
  start per chain in every arm of this study), the rule scales from the chosen start. (ii) Initial-step
  search: the scaling happens before the search, so a configured search probes the scaled metric; the
  multi-chain driver then runs the search per chain instead of sharing chain 0's (the defaults configure
  no search, so this does not arise here). (iii) The Stan windows, the draw-variance estimator, the Stan
  regularisation and dual averaging (from the same initial step 0.5) are unchanged; at the first slow-window
  close the estimated metric replaces the scaled one exactly as it replaces the identity today. (iv) Paper
  adaptation: unchanged, it starts from the scaled metric. (v) Restart guard: unchanged; a replacement
  start of a restarted chain is scaled from its own gradient the same way (the restart path re-enters
  `start_from`). (vi) Admission: one target evaluation per chain start, plus one per possible restart
  (at most `chains / 2`), added to `RunConfig::worst_case_target_evaluations`; the evaluation goes through
  the budget wrapper like any other call. (vii) Rejected: mass adaptation off (`Metric::Identity`), the
  dense, structured and continuation-session facades.
- Tests (`tests/grad_init_metric.rs`, research feature): flag off and explicit `AsGiven` bit-identical to a
  run without the call (1 and 4 threads) with the identity reported as the initial mass; on a Gaussian with
  SDs (0.01, 0.3, 1, 50) each chain's `initial_mass_diagonal` equals `clamp(|g(start)|, ..)` computed from
  the target, exactly, identical at 1 and 4 threads, and the draws differ from the flag-off run; a
  single-chain run with a zero-gradient coordinate gets the lower bound and a large gradient the upper
  bound, exactly; 1- and 4-chain runs through the sampler facade with the guard default complete with the
  expected masses and `Metric::Identity` is rejected; the admission bound grows by `chains` (`+ chains / 2`
  with the guard); bound validation and the dense-facade rejection. `tests/kernel_fingerprint.rs` passes
  with and without `research`; the full suites pass in both feature states; clippy `-D warnings` is clean
  on the library with and without `research` (two pre-existing `--all-targets` failures in WP91's bench
  example and test were fixed in `b512856a`) and on the study crate.

## Design

Three parts, 906 cells, each run once in `protocol.json`'s manifest order (S, then F, then P), split over two
lanes by manifest position (even positions on cores 0-3, odd on 4-7; each lane sequential, one process per
cell). A started cell is never rerun; an errored or timed-out cell is a failed cell (R1 / R3 fail on any
Part 1 error of the `defaults` or `gradinit` arm).

- **Part 1 (P): the 22 v7 posteriors x 6 fresh seeds x {`defaults`, `gradinit`, `gradinit-noguard`}**,
  4 x 1,000/1,000, 4 threads, `Init::best_of(16)` starts drawn in the cell as `Sampler::run_with_init`
  draws them (same seed, same starts in every arm). The same models, gates, two-tier parameter sets and
  BridgeStan libraries as WP85 / WP90 (the libraries are copied byte-identically from WP85's lane and
  hashed). Seeds 9450101-9450106. 396 cells.
- **Part 2 (F): Neal's 10-D funnel x 30 fresh seeds x {`diag`, `gradinit`, `gradinit-noguard`,
  `diag-best16`, `gradinit-best16`}**, 4 x 2,000/20,000. The first three arms use the harness's fixed
  starts (`omega in {-3, -1, 1, 3}`, `x = 0`; WP53 onward) and R5 is scored on them, comparable to WP85 /
  WP89 / WP90. At `x = 0` the x-gradients vanish, so nutpie's rule installs the 1e-20 floor on 9 of 10
  coordinates: a degenerate start nutpie itself never meets (its starts are random) but a legal input of
  the rule. The Windows smoke showed what that costs (below), so the two `-best16` arms repeat the pair
  with the sampler's own `Init::best_of(16)` starts (the same per seed in both); they are reported, not
  ruled. Seeds 9480301-9480330. 150 cells.
- **Part 3 (S): the WP84 SV model x 120 fresh seeds x {`defaults`, `gradinit`, `gradinit-noguard`}**, the
  WP89 / WP90 cell (4 x 1,000/1,000, diagonal metric, best-of-16 starts, per-transition telemetry kept out
  of git and hashed), WP89's census with WP89's anchor frozen. Seeds 9490101-9490222 minus 9490211 and
  9490212 (120 seeds). 360 cells.

Arms. `defaults` / `diag` is `Sampler::new()` as shipped (run shape, seed, threads, worst-case admission
only; the funnel sets `Metric::diagonal()` and `Adaptation::default()`); since WP90 `Adaptation::default()`
carries `DEFAULT_TRAPPED_CHAIN_RESTART` (`TrappedChainRestartConfig::guard()`). `gradinit` is the same plus
`Adaptation::Custom` of the configuration `Adaptation::default()` builds (`WarmupConfig::new(0.8)`,
`DEFAULT_WARMUP_EXHAUSTION`, `DEFAULT_METRIC_REGULARIZATION`,
`with_trapped_chain_restart(DEFAULT_TRAPPED_CHAIN_RESTART)`) with
`with_initial_metric(InitialMetric::nutpie())`. `gradinit-noguard` is `gradinit` with
`without_trapped_chain_restart()`. One `research` build serves every arm; the feature changes no default
(the smoke's `custom_noop`, the `Custom` configuration without the initial metric, must be bit-identical to
`defaults` on every smoke cell; R7).

Seeds were grep-verified unused (`git grep -ohwE` over `main` `a042a728` for `\b94501[0-9]{2}\b`,
`\b94803[0-9]{2}\b`, `\b9490[12][0-9]{2}\b` and the smoke seed `\b9459901\b`): the only hits were 9490211 and
9490212, in `STUDIES/options_flow_v1`'s seed-audit files, so those two are excluded from the S block (the
alternative block 9491101-9491220 had hits too, 9491118 and 9491123, and was not used); the sibling
worktrees' `STUDIES` (functionals, tick-pooling, warm-drift) showed the same two hits only; the box's lane
protocols are checked again before the first cell (`artifacts/environment.json`).

### Harness (every change from the copied sources)

- `src/bin/pdb_cell.rs`: WP90's. Changes: the arm table (`defaults`, `gradinit`, `gradinit-noguard`,
  `custom_noop`); each chain also records `initial_mass_diagonal`; the schema name. The per-chain warmup
  target calls (R3), the check record and the window summaries were already recorded.
- `src/bin/sv_cell.rs`: WP90's (WP89's). Changes: the arm table (WP89's twelve arms and the low-level
  `nutpie_init` path removed: the rule is now the library's, applied inside the four-chain facade run);
  `initial_mass_diagonal` per chain; the schema name.
- `src/bin/funnel.rs`: WP90's. Changes: the arm table, the `-best16` start option (`candidate_starts`, radius
  2, 16 candidates, 100 attempts, highest density), `initial_mass_diagonal` per chain.
- `run_study.py`: WP90's driver with three arms, the two-lane split (`run all <lane> <lanes>`), the
  `initial_mass` summaries (the SV cell keeps the mass on `mu`, `log_sigma`, `beta` and the median over
  `z`), and the WP94 rules below; the scoring (WP85's `run_pdb_cell` on the cell output) and the SV census
  (WP89's `analyze`, anchor frozen) are unchanged. `cargo clippy --release --all-targets -- -D warnings`
  passes on the study crate on 1.88 (Windows and the box).

### Instrument

Lanes 1-2 of the shared c7a.4xlarge box (two cells at a time, `taskset -c 0-3` and `4-7`,
`RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1`), co-tenanted with another study on cores 8-15 (shared L3 and
memory bandwidth): walls are "pinned, co-tenanted" and enter no rule; trapped counts, draw hashes, gates,
ESS and gradient counts are unaffected. The build and the smoke run while lanes 1-2 are still occupied by
WP93 (at `nice -n 10`, pinned to cores 0-3, 4 jobs); no evidence cell starts before WP93's processes are
gone. rustc 1.88.0, BridgeStan 2.9.0, posteriordb `28f8d3d` read from its files, ArviZ 0.23.4 from
`~/venv`. Budget about 3 h of lane time once the lanes are free: Part 3 about 10 min on two lanes (WP90:
2.3 s per cell; the candidate's cells are faster), Part 2 about 4 min, Part 1 about 1.1-1.3 h (WP90: 264 cells
in 1 h 24 min on one lane; 396 cells here on two lanes), the post-processing a few minutes.

## Definitions

- **Fired cell / fired chain.** A cell on which a chain restarted (`TrappedChainCheck::restarted`); the
  `defaults` and `gradinit` arms carry the guard, `gradinit-noguard` cannot fire.
- **Bit-identical** (the smoke's `custom_noop` check only; R7). Per chain, the FNV-1a hash of the retained
  draws and the chain's total target calls are equal; per cell, the pooled hash and the target's total call
  count are equal.
- **Passing cell (Part 1).** All v7 gates on the tier's parameter set: rank R-hat <= 1.01, bulk and tail
  ESS >= 400, 0 retained divergences, finite draws, no sampler error.
- **Headline (R2).** WP72 form (c): per model, the per-seed ratio `gradinit` / `defaults` of min bulk ESS
  per target call (every call of the cell: start search, warmup, sampling, the candidate's one gradient per
  chain start, and on a fired cell the abandoned run and the replacement pool) on seeds where both cells
  are ok, median over seeds; geomean over the 22 models, each with at least 5 of 6 paired ok seeds (fewer
  fails R2). Reported alongside: the median of the 132 paired per-seed ratios with a 2,000-resample
  bootstrap 95 % interval and its range; the same for `gradinit-noguard`.
- **Warmup gradients (R3).** Per chain, the target calls of the discarded transitions (`WorkTotals`; a
  fired chain's abandoned run is excluded, as in WP90's chain totals). Per cell, the ratio `gradinit` /
  `defaults` of the median over the 4 chains; per model, the median over paired ok seeds; the geomean over
  models and the per-model values are reported.
- **Trapped chain, Part 3 (R6).** WP89's frozen census with WP89's anchor: |median retained log_sigma -
  (-1.852786)| > 1.0 or |median retained h_last - (-10.020535)| > 2.0.

## Decision rules (frozen; conjunctive)

| rule | condition |
|---|---|
| R1 | Part 1: `gradinit` passes >= `defaults` passes over the 132 cells per arm; every Part 1 cell of every arm completes |
| R2 | Part 1 headline `gradinit` / `defaults` >= 0.98 over all 22 models (paired per-seed median and interval reported; per-model table) |
| R3 | Part 1: the warmup-gradient ratio reported per model with its geomean; no model where the candidate's gates drop (per model, `gradinit` passes >= `defaults` passes) |
| R4 | Part 1: per model, `gradinit` retained divergences over 6 seeds <= `defaults`'; no cell passing at the defaults has more retained divergences in the `gradinit` arm |
| R5 | Part 2: 30/30 `gradinit` cells complete and pooled P5(`gradinit`) within 2 between-seed s.e. of 0.0477903523 (`diag`, `gradinit-noguard` and the `-best16` pair reported) |
| R6 | Part 3: `gradinit-noguard` trapped chains <= 1 of 480 AND `gradinit` trapped chains = 0 of 480; the guard's firing count under `gradinit` reported (prediction: near 0) |
| R7 | `tests/kernel_fingerprint.rs` passes without and with `research` (the fingerprints are untouched by the flag); `tests/grad_init_metric.rs` and `tests/trapped_chain_restart.rs` pass; `cargo clippy --all-targets --all-features -- -D warnings` on the library and `--all-targets -- -D warnings` on the study crate pass on 1.88; every smoke `custom_noop` cell bit-identical to its `defaults` / `diag` cell |

**QUALIFIES for a default-flip confirmation** (proposed, not flipped) iff R1-R7 all hold. Otherwise the flag
stays research-only. Bit-identity to the defaults is not a rule: a candidate that changes the initial
metric is allowed to change the draws everywhere. An implementation error anywhere (a cell error, a failed
integrity check) fails the study. No default is changed by this study.

## Predictions (written before any evidence cell)

- **P1.** Part 1 passes: defaults 88-100 of 132 (WP90: 92; WP85: 105); `gradinit` within -3..+4 of the
  defaults (the initial metric changes every chain's first 100 transitions; the gates are dominated by
  the retained window).
- **P2.** R2 headline geomean in [0.97, 1.08]: the metric is draw-adapted by transition 100 either way, so
  retained ESS is unchanged in expectation and the gradient count moves with the first window's cost;
  paired per-seed median in [0.95, 1.10]. Models with a stiff start (kilpisjarvi, lotka_volterra, one_comp,
  GLMM_Poisson) gain; no model below 0.85 (reported, not ruled).
- **P3.** R3 warmup-gradient geomean ratio in [0.80, 1.02]: fewer identity-phase gradients on the badly
  scaled models (WP89: 800 gradients per transition at depth 8-9 under the identity metric on the SV
  model; the Windows SV smoke below: 0.52x), about equal elsewhere; no model's pass count drops.
- **P4.** No new divergences on any model (R4 holds); divergence totals equal to the defaults' on at least
  18 of 22 models.
- **P5.** Funnel P5 within 2 s.e. for `diag`, `gradinit` and `gradinit-noguard` (WP85 diag 0.0492 +- 0.0017,
  WP89 0.0503 +- 0.0012, WP90 0.0458 +- 0.0016); 0 firings in the `gradinit` arm. Reported: the fixed-start
  `gradinit` arms spend more target calls than `diag` (the 1e-20 floor on the x-coordinates; the smoke's
  3x at 200 warmup should shrink at 2,000 warmup because only the first window is affected), the `-best16`
  pair about equal.
- **P6.** SV: defaults trapped 3-16 of 480 with 6-16 guard firings (WP90: 8 and 13); `gradinit-noguard`
  trapped 0-2 of 480 (WP89 `nutpie_init`: 1/240); `gradinit` 0 of 480 with 0-3 guard firings.
- **P7.** R7 holds: fingerprints untouched, the flag-off tests pass, clippy clean, `custom_noop`
  bit-identical to `defaults` on every smoke cell.
- **Verdict predicted: QUALIFIES for a confirmation.**

## The proposed next step (not applied by this study)

If every rule holds: a default-flip confirmation (WP85 / WP90 shape) of `InitialMetric::nutpie()` installed
by `Adaptation::warmup_config`'s `with_defaults` for the sampler's own adaptation modes on the identity-adapting
and diagonal facades (dense and structured keep rejecting it), the research gate lifted from
`with_initial_metric` / `InitialMetric`, `ALGORITHM_REVISION` and the kernel fingerprints unchanged
(`tests/kernel_fingerprint.rs` pins `walnutpie::RunConfig` runs, which take no sampler default),
sampler-level draws changed everywhere, so that confirmation's rules are this study's and not bit-identity.
The zero-gradient start (the funnel harness's `x = 0`) is the one known weakness of the rule as stated: a
coordinate whose gradient vanishes at the start gets mass 1e-20; the confirmation should decide whether the
sampler's own starts (uniform(-2, 2) candidates) can produce it on any house model, and whether a floor
relative to the other coordinates is wanted.

## Smoke (disclosed, non-evidence; diagnostic seed 9459901)

Windows, before shipping (the release build of this harness; outputs in the session scratchpad, not
committed):

- Funnel at 200/2,000, fixed starts: `diag` and `custom_noop` bit-identical (`ac24405e4def9b40`, 593,617
  calls); `gradinit` and `gradinit-noguard` bit-identical to each other (`fef4b3e980dbcbec`, no firing),
  P5 0.0858 +- 0.054 against `diag` 0.0724 +- 0.035, but 1,761,160 calls (3.0x), min bulk ESS 10 vs 29, 2
  warnings: the initial mass per chain was `[4.2-4.8, 1e-20 x 9]`. That is the `x = 0` start (zero
  x-gradients). With `-best16` starts: `diag-best16` 620,535 calls, `gradinit-best16` 630,638 calls (1.02x),
  P5 0.0766 vs 0.0431, initial masses 0.1-2.4 on every coordinate. The `-best16` arms were added to the
  design because of this, before the freeze.
- SV quadruple (4 x 1,000/1,000): `defaults` and `custom_noop` bit-identical (`66ff654564cae219`, 804,848
  calls); `gradinit` = `gradinit-noguard` (`95c4788bf34415a4`, no firing, no warning), 493,027 calls
  (0.61x), warmup calls per chain 83,821-99,590 against 165,122-184,918 (0.52x); the initial masses were
  54-134 on `mu`, 21-310 on `log_sigma`, 7,400-72,000 on `beta` (prior SD 0.002) and 1.6-4.8 (median) on
  the `z` block, i.e. the rule puts the scale on `beta` that WP89 showed the Stan floor cannot (`beta`'s
  variance is 4e-6).
- The box smoke (`box/smoke.sh`, run before the freeze is recorded in README.md): kidiq and GLMM_Poisson
  at every arm, the funnel sextuple, the SV quadruple, the `custom_noop` identity checks written into
  `artifacts/environment.json`, and the analysis pass over the smoke cells; results in `artifacts/smoke/`
  and in README.md.

Changes made because of the smoke, all before any evidence cell: the `-best16` funnel arms (reported, not
ruled) and the weakness note above. No rule, seed or prediction changed after this file was frozen.
