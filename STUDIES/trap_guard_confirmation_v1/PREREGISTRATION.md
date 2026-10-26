# WP90 `trap_guard_confirmation_v1`: preregistration

Frozen on `wt/trap-guard-confirm` (base `main` at `f5500db3`) before the first evidence cell; the freeze
commit is recorded in `README.md`. `protocol.json` is the machine-readable copy and wins on any
discrepancy. Ledger id `WP90-TRAP-GUARD-CONFIRMATION-V1`.

## Question

Does `guard-0.01-0` qualify as the sampler default? It is the WP67 trapped-chain restart rule
(`WarmupConfig::with_trapped_chain_restart`, research feature) with the step ratio 0.01 instead of 0.1,
scored at the close of the first non-empty slow window (transition 99 of the default 1,000-transition
schedule, check window 0): a chain whose dual-averaging step there is below 0.01 x the chain-median step
is discarded and reruns the whole schedule from an independent best-of-16 uniform(-2, 2) start on its own
seed stream, at most once. Nothing is copied from another chain. The rule is used exactly as WP89 ran it;
nothing is re-tuned and the library is unchanged (`main` `f5500db3`, which already carries WP89's
`with_check_window`).

## What this confirms, and why the earlier confirmation failed

- WP67 (`STUDIES/trapped_chain_restart_v1`) supported the rule at ratio 0.1 on two `lotka_volterra`
  trap events (ratios 0.0023 and 0.025; lowest healthy 0.388 on its models).
- WP69 (`STUDIES/trapped_chain_restart_confirmation_v1`, ratio 0.1) did **not** propose a default. On 60
  fresh lotka seeds 0/240 chains were trapped and the rule fired twice on chains that recovered on their
  own (0.024, 0.027); on the 17-model breadth arm it fired once on a healthy `earnings` chain (0.031) in a
  cell that passes at the defaults, and it missed a real lotka trap at 0.111. At 0.1 the step rule
  separates "currently slow" from "healthy", not "trapped" from "healthy". Those are its two failure
  modes: firings on chains that are not trapped, and no traps to remove on the model it was tuned on.
- WP89 (`STUDIES/sv_stuck_chains_v1`) found a model with a measured trap rate (the WP84 SV model: 8/480
  defaults chains, 1.7 %; the mechanism is a stiff high-sigma start whose first transitions are rejected,
  a step collapse to 1e-7 under the identity metric, and the Stan regularisation floor installed on every
  coordinate at transition 99). The 8 traps sat at ratios 1e-9 to 1.4e-3 at transition 99; the healthy
  minimum over WP89's 156 control cells was 0.07 (funnel 0.076, `earnings` 0.07). At ratio 0.01 the guard
  took the trapped count to 0/480, fired on the 8 traps and on 2 near-traps that carried the full signature
  at transition 99 (3.6e-3, 7.8e-4) and escaped later by luck, and fired on nothing else: 0 of 120 funnel
  chains and 0 of 36 house chains, 110/110 unfired cells bit-identical. The ratio-0.1 rule fired on a
  healthy funnel chain (0.076) and an `earnings` chain (0.07) in the same study, which is why 0.01 is the
  candidate.

WP90 tests that WP69's failure modes are gone at 0.01, on the default-flip panel (WP85's shape): **every
firing on the 22-posterior panel and the funnel is audited against a frozen trapped definition and zero
false firings are tolerated (R7)**; efficacy is measured on the SV model (R6); every unfired cell must be
bit-identical to the defaults (R2); the v7 gates, divergences, ESS per gradient and the funnel tail stand
guard against cost elsewhere (R1, R3, R4, R5); the library's own tests, clippy and an empty library diff
close it (R8).

## Design

Three parts, 564 cells, each run once in `protocol.json`'s manifest order (S, then F, then P; the two
short parts first so that their results exist even if the box is stopped). A started cell is never rerun;
an errored or timed-out cell is a failed cell (R2 and R7 fail on any error).

- **Part 1 (P): the 22 v7 posteriors x 6 fresh seeds x {`defaults`, `guard-0.01-0`}**, 4 x 1,000/1,000,
  4 threads, `Init::best_of(16)` starts drawn in the cell as `Sampler::run_with_init` draws them (same
  seed, same starts in both arms). The same models, gates, two-tier parameter sets (18 reference-tier
  posteriors scored on the posteriordb reference draws with the per-chain shift; 4 gates-only posteriors on
  their parameter-block coordinates, WP46 rule) and BridgeStan libraries as WP85 (the libraries are copied
  byte-identically from WP85's lane and hashed). Seeds 9050101-9050106. 264 cells.
- **Part 2 (F): Neal's 10-D funnel x 30 fresh seeds x {`diag`, `guard-0.01-0`}**, 4 x 2,000/20,000 (the
  usual tail check, WP85 / WP89 harness). Seeds 9080301-9080330. 60 cells.
- **Part 3 (S): the WP84 SV model x 120 fresh seeds x {`defaults`, `guard-0.01-0`}**, the WP89 cell
  verbatim (4 x 1,000/1,000, diagonal metric, best-of-16 starts, per-transition telemetry kept out of git
  and hashed). Seeds 9090101-9090220. 240 cells.

Arms. `defaults` / `diag` is `Sampler::new()` as shipped (run shape, seed, threads, worst-case admission
only; the funnel sets `Metric::diagonal()` and `Adaptation::default()`). `guard-0.01-0` is the same plus
`Adaptation::Custom` of the configuration `Adaptation::default()` builds (`WarmupConfig::new(0.8)`,
`DEFAULT_WARMUP_EXHAUSTION`, `DEFAULT_METRIC_REGULARIZATION`) with
`with_trapped_chain_restart(TrappedChainRestartConfig::step_rule().with_step_ratio(0.01).with_check_window(0))`.
One `research` build serves both arms; the feature changes no default (WP89's `custom_noop` and
`lowlevel_noop` were bit-identical to `defaults`, and R2 re-measures it on every unfired cell here).

Seeds were grep-verified unused (`git grep -lwE` over `main` for `\b90501[0-9]{2}\b`, `\b90803[0-9]{2}\b`,
`\b9090[12][0-9]{2}\b` and the smoke seed `\b9059901\b`: no hit; no hit in the sibling worktree's
`STUDIES`; the box's lane protocols are checked again before the first cell, `artifacts/environment.json`).

### Harness (every change from the copied sources)

- `src/bin/pdb_cell.rs`: WP89's `pdb_cell.rs` (WP67's, from the v7 harness). Changes: each chain also
  records the warmup-end and retained-window (`RunTelemetry::sampling_end`) step, median log density and
  log-density IQR; the schema name. The trapped-chain check record (every chain's scored step, the
  chain-median step, the scored transition's log density `abandoned_log_density`, which the library fills
  for unfired chains too) was already recorded.
- `src/bin/sv_cell.rs`: WP89's, verbatim, plus the same two window summaries per chain and the schema name.
- `src/bin/funnel.rs`: WP89's (WP85's). Changes: the check record also carries the scored transition's
  log density, the abandoned calls and the replacement start's log density; each chain also records the
  warmup-end IQR and the retained-window step, median log density and IQR; the schema name.
- `run_study.py`: new. Part 1 scoring is WP85's `run_pdb_cell` applied to WP89's cell output (same gates,
  tiers, ArviZ 0.23.4 statistics, draws saved out of git); Part 3's census is WP89's `analyze` with the
  anchor frozen numerically (WP90 runs no nutpie arm; the draws are stripped to `.npz` at write time as
  WP89's `strip_draws.py` did afterwards); the identity, headline and audit code is new and listed in the
  rules below. `cargo clippy --all-targets -- -D warnings` passes on the study crate on 1.88 (Windows and
  the box).

### Instrument

Lane 1 of the shared c7a.4xlarge box (`taskset -c 0-3`, `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1`),
co-tenanted with another study on cores 4-15 (shared L3 and memory bandwidth): walls are "pinned,
co-tenanted" and enter no rule; trapped counts, draw hashes, gates, ESS and gradient counts are unaffected.
rustc 1.88.0, BridgeStan 2.9.0, posteriordb `28f8d3d` read from its files, ArviZ 0.23.4 from `~/venv`.
Budget about 3 h of lane time: Part 3 about 12 min (WP89: 2.3 s per cell plus trapped-chain overhead),
Part 2 about 2 min, Part 1 about 2.5 h (WP85's 264 cells), builds, library tests and the smoke about 15
min.

## Definitions

- **Fired cell / fired chain.** A guard cell on which a chain restarted (`TrappedChainCheck::restarted`).
- **Bit-identical.** Per chain, the FNV-1a hash of the retained draws and the chain's total target calls are
  equal; per cell, the pooled hash and the target's total call count (start search included) are equal.
- **Passing cell (Part 1).** All v7 gates on the tier's parameter set: rank R-hat <= 1.01, bulk and tail
  ESS >= 400, 0 retained divergences, finite draws, no sampler error.
- **Headline (R4).** WP72 form (c): per model, the per-seed ratio guard / defaults of min bulk ESS per
  target call (every call of the cell: start search, warmup, sampling, and on a fired cell the abandoned
  run and the replacement pool) on seeds where both cells are ok, median over seeds; geomean over the 22
  models, each with at least 5 of 6 paired ok seeds (fewer fails R4). Reported alongside: the median of the
  132 paired per-seed ratios with a 2,000-resample bootstrap 95 % interval, its range and the number of
  pairs not equal to 1.
- **Trapped chain, Part 3 (R6).** WP89's frozen census with WP89's anchor: |median retained log_sigma -
  (-1.852786)| > 1.0 or |median retained h_last - (-10.020535)| > 2.0.
- **Trapped at the defaults, Parts 1-2 (R7).** A fired chain c is trapped iff at least one of:
  - **T1** the defaults cell's chain warnings (`WarmupStep`, `WarmupLogDensity`, `SampledLogDensity`,
    `RHat`, `RHatCluster`) name chain c;
  - **T2** (reference tier only) at the defaults, chain c's retained mean is more than 3 reference SD from
    the reference mean on some reference parameter (WP67 / WP69's definition);
  - **T3** the WP89 signature on the recorded quantities: chain c's step at the scored transition is below
    0.01 x the chain median (true for every fired chain) and its selected-state log density at that
    transition is below the defaults' retained reference level (median over chains of the chain-median
    retained log density) by more than 3 x the median within-chain retained log-density IQR, the library's
    own WP33 log-density scale applied at transition 99. This is what WP89's near-traps satisfied (full trap
    signature at 99, escaped later by luck); WP89 counted those firings as acceptable.
  A firing on a chain for which none of T1-T3 holds is a **false firing**.
- **Restarted chain ok.** The restarted chain is not named by the guard cell's warnings and (reference
  tier) its shift is at most 3 reference SD; reported with the guard cell's gate result.

## Decision rules (frozen; conjunctive)

| rule | condition |
|---|---|
| R1 | Part 1: guard passes >= defaults passes over the 132 cells per arm; every Part 1 cell completes |
| R2 | every unfired guard cell of Parts 1-3 is bit-identical to its defaults / diag cell (chains and cell); every fired cell's untouched chains are bit-identical per chain; no cell of either arm errored or timed out |
| R3 | Part 1: per model, guard retained divergences over 6 seeds <= defaults'; no cell passing at the defaults has more retained divergences in the guard arm |
| R4 | Part 1 headline guard / defaults >= 0.98 over all 22 models (paired per-seed median and interval reported) |
| R5 | Part 2: 30/30 guard cells complete and pooled P5(guard) within 2 between-seed s.e. of 0.0477903523; the funnel firing count is reported (prediction 0) |
| R6 | Part 3: guard trapped chains 0 of 480 (defaults' count reported) |
| R7 | every firing on Parts 1-2 listed (step, chain-median step, ratio, log density at transition 99 against the chain median, T1-T3, restarted chain ok, guard cell gates); false firings over Parts 1-2 = 0; Part 3's firings listed the same way for the record |
| R8 | `tests/kernel_fingerprint.rs` passes without and with `research`; `tests/trapped_chain_restart.rs` passes; `cargo clippy --all-targets --all-features -- -D warnings` on the library and `--all-targets -- -D warnings` on the study crate pass on 1.88; `git diff f5500db3 -- src tests Cargo.toml Cargo.lock` is empty |

**QUALIFIES** (proposed for the flip; the coordinator applies it) iff R1-R8 all hold. Otherwise the guard
stays research-only. An implementation error anywhere (a cell error, a bit-identity failure) fails the
study. No default is changed by this study.

## Predictions (written before any evidence cell)

- **P1.** Part 1 firings: 0 (tolerance 0-2). If any, on `lotka_volterra` (WP69: a real trap at 0.111 and
  near-traps at 0.024 / 0.027; WP67: traps at 0.0023 / 0.025) or `GLMM_Poisson` (WP85: 2 of 6 defaults
  cells had rank R-hat > 1.1), and every one on a chain trapped at the defaults (T1 or T3). No firing on
  `earnings` (WP69 minimum 0.031, 3x above the cut), `accel_gp` (0.143) or any other model.
- **P2.** Part 1 passes: defaults 98-112 of 132 (WP85: 105 with the same models, gates and harness);
  guard = defaults unless a lotka or GLMM cell that fails at the defaults passes after a true firing (then
  guard > defaults).
- **P3.** R4 headline exactly 1.0000 if no Part 1 chain fires (every unfired cell bit-identical, every
  ratio 1); within [0.99, 1.02] otherwise; paired per-seed median 1.0000 with a degenerate interval.
- **P4.** Part 2: 0 firings (WP89: 0 at 0.01 over 120 funnel chains, healthy minimum 0.076; at 2,000
  warmup the first slow window closes at transition 199 with every chain adapted); 30/30 bit-identical to
  `diag`; P5 within 2 s.e. with probability about 0.95 (WP85 diag 0.0492 +- 0.0017, WP89 diag 0.0503 +-
  0.0012).
- **P5.** Part 3: defaults trapped 3-16 of 480 (WP89: 8), guard 0; guard firings 6-16 (WP89: 10 on 120
  seeds, 8 traps + 2 near-traps), each on a chain the census calls trapped at the defaults or that carries
  the WP89 signature (T3); every restarted chain ends at the mode.
- **P6.** R2 holds everywhere (WP89: 110/110, 30/30, 9/9 unfired cells and 31/31 fired cells' untouched
  chains; WP69: 123/123).
- **P7.** R8 holds; no library change is needed.
- **Verdict predicted: QUALIFIES.**

## The proposed flip (D; applied by the coordinator only if every rule holds)

As `protocol.json` `proposed_flip`:

1. **Default.** A const constructor `TrappedChainRestartConfig::guard()` (= `step_rule()` with step ratio
   0.01 and check window 0; minimum 3 chains and 10 window transitions; replacement best of 16
   uniform(-2, 2) candidates, 100 attempts) and a new constant
   `sampler::DEFAULT_TRAPPED_CHAIN_RESTART: Option<TrappedChainRestartConfig> = Some(TrappedChainRestartConfig::guard())`,
   installed by `Adaptation::warmup_config`'s `with_defaults` for the sampler's own adaptation modes
   (`DualAveraging`, `Paper`) exactly where `DEFAULT_CHAIN_RESCUE` would be installed
   (`Metric::supports_chain_rescue`: the identity and diagonal facades; dense and structured keep
   rejecting the option, so nothing is installed there). `Adaptation::Custom` stays as given (opt-out: a
   `Custom` configuration without the option).
2. **Research gate lifted** from `WarmupConfig::with_trapped_chain_restart`, `TrappedChainRestartConfig`
   and its constructors, `TrappedChainCheck`, `RunTelemetry::trapped_chain_checks`,
   `TRAPPED_CHAIN_RESTART_SEED_TAG`; `tests/trapped_chain_restart.rs` loses its feature gate.
3. **Not a new kernel.** `ALGORITHM_REVISION` and the kernel fingerprints (`tests/kernel_fingerprint.rs`
   pins `walnutpie::RunConfig` runs, which take no sampler default) do not move: the WP68
   `refinement_levels10_v1` precedent, as with the MomentumSum, RejectLeaf and best-of-16 flips.
   Sampler-level draws change only on fired chains (R2 is the measurement).
4. **Python.** No signature change; draws follow the Rust default; the config dict, `DEFAULTS`, README
   table and CHANGELOG document the restart.
5. **Docs.** `wiki/open-questions.md` items 12, 19 and 23 closed to this flip; the chain-warnings note
   states that a restarted chain is an independent start, so independent-chain R-hat remains valid (unlike
   chain rescue, WP36).

## Smoke (disclosed, non-evidence; diagnostic seed 9059901, before the freeze)

Filled in before the freeze commit; see the section of the same name in `README.md` for the outcome. The
smoke runs the pipeline once per kind in the lane's scratch artifacts (`artifacts/smoke/`, committed
without draws or telemetry): `kidiq` `defaults` and `guard-0.01-0` (bit-identical expected; a
reference-tier cell), one gates-only `defaults` cell (`GLMM_Poisson`), one funnel pair, one SV pair, and
the analysis code over the smoke cells. Local (Windows) functional checks before shipping: the funnel at
200/2,000 and one SV guard cell at the smoke seed, to validate the recorded fields the driver reads; both
arms of the funnel were bit-identical there (844,864 calls, no firing).
