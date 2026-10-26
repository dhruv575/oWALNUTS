# WP67 preregistration: early detection and restart of a trapped warmup chain

Frozen before the first evidence cell. Machine-readable copy: `protocol.json`
(that file governs where the two differ). Ledger number: the highest WP in the
README, wiki and ledger is WP63; the three lanes ahead of this one on the
shared box take WP64–WP66, so this study is **WP67**.

## Background

- WP57 (`STUDIES/lotka_volterra_stall_v1`): at the 0.3 defaults
  (`Init::best_of(16)`), `hudson_lynx_hare-lotka_volterra` no longer stalls
  (0/12), but 2 of 48 chains (seeds 5701103 chain 3, 5701106 chain 2) were
  trapped in a secondary mode at log density about -430 against -137, 139–162
  reference SD off, R-hat 1.59, with 4–26x the gradients of a healthy chain.
  Neither `best_of(64)` nor an initial-phase depth cap fixed it. The WP44 step
  rule, emulated at the end of the first slow window S1 (transitions 75–99),
  flagged 10/10 trapped or stalled chains and 0 of 139 healthy chains. Re-read
  from WP57's committed cell files: every healthy chain's S1 step ratio is
  >= 0.304 and every trapped chain's is <= 0.027 (0.055 for one stalled
  uniform-start chain).
- WP44 (`STUDIES/chain_disagreement_warning_v1`) ships the step rule (ratio
  0.1) as an observe-only end-of-warmup warning; its sensitivity rests on one
  positive.
- WP52 (`STUDIES/init_rule_confirmation_v1`) made best-of-16 the default.
- WP33/WP36: `restart_from_best` was removed as a default because a restart
  *copies another chain's state*: the independent-start reading of R-hat no
  longer holds, the density rule fired on merely late chains, and the
  mode-destruction risk could not be bounded (`wiki/negative-results.md`,
  "Chain rescue"; open question 19). WP61's rescue-removal check was 1.023x.

This study tests the item open question 19 names: a step-only restart at the
first slow-window boundary. It differs from the removed rescue in three
preregistered ways: the step rule only (no density rule, which WP57 found
had 26 false positives at S1); one check, at the end of S1 only; and the
restarted chain gets an **independent** fresh best-of-16 start and a fresh
RNG stream, so nothing is copied from another chain. Other chains only decide
*whether* a chain restarts.

## Question

Can a trapped chain be detected at the end of the first slow adaptation
window by the step rule and restarted from the best of a fresh candidate
pool, so that the lotka trapped-chain count falls from 2/48 toward 0, without
changing any draw on runs where no chain is flagged, and without losing gates
or more than 5 % ESS per gradient on six house posteriordb models?

## Implementation (research-only, library commit `8887a0f0`)

`WarmupConfig::with_trapped_chain_restart(TrappedChainRestartConfig::step_rule())`,
behind the `research` Cargo feature; `None` by default; no default changes;
kernel fingerprints untouched. `cargo test --release` and
`cargo test --release --features research` pass on the laptop
(`artifacts/wp67-cargo-test*.log`), including 4 new tests in
`tests/trapped_chain_restart.rs`: an unflagged run is bit-identical (draws,
diagnostics, work totals) to the plain driver at 1 and 4 threads; fewer than
3 chains or a first slow window shorter than 10 transitions is the plain run;
a chain started in a narrow spike is restarted from an independent start in
`[-2, 2]^d` while the other three chains stay bit-identical, deterministically
and thread-count invariantly; combination with chain rescue and the dense
facade are configuration errors; admission accounts for a restart.

- **Detector (fixed in advance).** Statistic `s_c` = the step size used by
  chain `c`'s transition 99, the last transition of the first slow window
  (75–99 at 1,000 warmup), read from `TransitionDiagnostics::step_size`.
  Reference `m` = median of the four `s_c` (mean of the middle two).
  **Flag chain `c` iff `s_c < 0.1 m`.** Evaluated once, after all chains
  completed transition 99 (the chains are synchronised there and nowhere
  else). Skipped with fewer than 3 chains, a first window shorter than 10
  transitions, or any non-finite or non-positive `s_c`. Ratio 0.1 is the
  frozen WP33/WP44 value; it is not re-tuned.
- **Restart action.** The flagged chain's run (transitions 0–99) is discarded;
  its target calls stay in the run's call count and are recorded. The chain
  reruns the full 1,000 + 1,000 schedule from transition 0 from the
  highest-density of 16 fresh evaluable uniform(-2, 2) candidates (up to 100
  draws each), drawn by `sampler::candidate_starts` for one chain with seed
  `splitmix64(base_seed ^ TRAPPED_CHAIN_RESTART_SEED_TAG) + chain`, with the
  initial metric and step, fresh dual averaging and the RNG seed
  `splitmix64(chain_seed ^ TRAPPED_CHAIN_RESTART_SEED_TAG)`. At most one
  restart per chain; the restarted chain is not checked again.
- **Telemetry.** `RunTelemetry::trapped_chain_checks` on every chain: score,
  median, threshold, flag; on a restarted chain also the abandoned run's
  target calls, the replacement start, its log density, its evaluation count
  and the new seed.

## Instrument

Lane 4 of the shared box (`LANES.md`): AWS c7a.4xlarge, 16 dedicated AMD
cores, Ubuntu 24.04, Rust 1.88.0. Every build and cell runs under
`taskset -c 12-15` with `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1` and
`TMPDIR` under `~/lanes/trapped_chain_restart_v1/`. **The study runs
core-pinned on a shared box with three other lanes active (shared L3 and
memory bandwidth), so every wall-clock number is "pinned, co-tenanted".**
Gradient counts, ESS per gradient, draw hashes and pass counts are not
affected by co-tenancy, and they carry the evidence.

- Models: Stan programs and data copied from the shared read-only posteriordb
  checkout (`~/infra/posteriordb`, commit `28f8d3d`) by `prepare_models.py`;
  libraries built with the BridgeStan 2.9.0 source (release tarball sha256
  `b6034f83…05a4c`) under the lane, gcc 13.3.0, no `STAN_THREADS`; hashes in
  `artifacts/models.json`. The lotka data file hash equals WP57's; the `.stan`
  hash differs from WP57's Windows copy (line endings of the checkout).
  This is a different build and platform from WP57, so WP57's trajectories
  need not reproduce bit for bit.
- Python: the shared `~/venv` (arviz 0.23.4, bridgestan 2.9.0, numpy 2.5.4),
  read-only. posteriordb is read directly from its files.
- Sampler: the shipped `owalnuts::sampler` at the library commit:
  `Metric::diagonal()`, `Tuning::default()` (`RejectLeaf`),
  `Limits::admit_worst_case()`, 4 chains x 1,000 / 1,000 on 4 threads,
  starts `Init::default()` = `Init::best_of(16)` drawn by `candidate_starts`
  as `Sampler::run_with_init` draws them, `ReplicatedStanTarget` construct
  seed 1.
- Arms: `defaults` = `Adaptation::default()`; `restart` =
  `Adaptation::Custom` of the configuration `Adaptation::default()` builds
  plus the restart.

### Harness changes (WP57 and v7 code, copied and parametrised)

`src/bin/trap_cell.rs` is WP57's `src/main.rs` with:
1. arms `defaults`, `restart`, `custom_noop` (smoke only) replacing WP57's
   five; start candidates fixed at 16;
2. a 20th telemetry field `epoch` per row (0 = the chain's first run, 1 =
   after a restart), set when a chain's transition index does not increase;
3. per chain `step_at_transition_99`, `effective_seed` and
   `trapped_chain_checks` in `chains_data`;
4. schema name and timing-estimand text.

`src/bin/pdb_cell.rs` is posteriordb v7's `src/main.rs` with:
1. arm `restart` replacing `dense`;
2. an FNV-1a draw hash per chain and over all chains (WP57's hash);
3. per chain `total_target_calls`, `step_at_transition_99`, `effective_seed`
   and `trapped_chain_checks`;
4. schema name.

`run_study.py` combines WP57's driver (lotka cells: `profile`, gates, the
WP57 z gate, telemetry) and v7's oWALNUTS arm (`run_owalnuts`, `metrics`,
`arviz_stats` verbatim) with:
1. one manifest over blocks L1, R, L2 and both arms;
2. `profile` restricted to a chain's final epoch, with the abandoned
   epoch-0 run summarised separately;
3. posteriordb read from its files instead of the `posteriordb` package;
4. per-chain reference shift, trapped chains, the emulated detector, and
   draw hashes and per-chain target calls for the fingerprint rule;
5. Linux paths, no `windows_dll_path_setup`, and `measured_on.json`
   recording the CPU affinity and environment.

`analyze.py` is new (written now, before the evidence).

### Smoke (non-evidence, seed 6709901, before freezing)

Recorded in `artifacts/smoke/smoke-summary.json` and summarised below at the
freeze. Lotka `defaults`, `restart`, `custom_noop` and `defaults --plain`,
and `eight_schools_centered` `defaults` and `restart` through `pdb-cell`. It
checks that the routes agree where the detector does not fire.

Result (run on the box at the harness files committed with this
preregistration): lotka `defaults`, `restart`, `custom_noop` and
`defaults --plain` all give draw hash `e95ec23a65e63a31` and 282,540 target
calls, with no chain flagged (transition-99 steps 0.0195, 0.0481, 0.0074,
0.0107; smallest ratio 0.49); `eight_schools_centered` `defaults` and
`restart` both give `2049b6de567c7c4f` and 320,156 calls. A lotka cell takes
about 6 s of pinned, co-tenanted wall on this box. The restart path itself is
exercised by the unit tests, not by the smoke (no seed is known to trap on
this build).

## Cells (strictly sequential, in this order; none rerun; failures are results)

1. **L1** (lotka, 24 cells): seeds 5701101–5701112, each `defaults` then
   `restart`. **Declared targeted replication, not fresh**: WP57's block A
   seeds, where defaults trapped 2/48 chains on Windows.
2. **R** (regression, 36 cells): `eight_schools_centered`, `hmm_drive_0`,
   `arma11`, `garch11`, `gp_pois_regr`, `one_comp_mm_elim_abs` in that order;
   seeds 6701301–6701303 ascending; each `defaults` then `restart`.
3. **L2** (lotka, 24 cells): fresh seeds 6701201–6701212, each `defaults`
   then `restart`; secondary, pooled with L1 for efficacy.

84 cells. The seeds were grepped over the repository and every sibling
worktree's protocols: none had been used. Lotka cells have a cooperative
1,200 s cap and a 1,500 s process backstop (WP57); regression cells a 2,700 s
process timeout (v7).

## Definitions

- **Gates** (CmdStan-free), on every posteriordb reference parameter: rank
  R-hat <= 1.01, bulk ESS >= 400, tail ESS >= 400, 0 retained divergences,
  finite draws, no sampler error; lotka cells also max |z| <= 4 (WP57). A
  cell that errors or times out fails every gate.
- **Chain shift**: per chain, max over reference parameters of
  |chain mean - reference mean| / reference SD.
- **Trapped chain** (outcome, defined without the detector): a chain of a
  completed cell with shift > 3 (the WP44/WP52 "off reference" rule; WP57's
  trapped chains were 139–384 SD off, healthy ones under 0.11); in a cell that
  did not complete, every chain that had not finished.
- **Flagged chain**: restart arm, a chain the library restarted; defaults
  arm, the same rule emulated on the defaults run's steps at transition 99.
- **Firing cell**: a restart cell with a flagged chain.
- **Wrong-chain cell**: a completed cell with a chain shift > 3.
- **Efficiency**: min-over-parameters bulk ESS / total target calls (start
  search, abandoned run and replacement pool included); per model the
  geometric mean over seeds where both arms completed; ratio restart /
  defaults per model; geometric mean over the six models.

## Predictions (written before any evidence cell)

- **P1.** L1 defaults has 1–3 trapped chains of 48 (WP57: 2; the different
  build may move them).
- **P2.** L1 restart has at most 1 trapped chain of 48 (expected 0).
- **P3.** The detector flags every defaults trapped chain that reached
  transition 99 (sensitivity 1), and at most 1 lotka defaults chain that is
  not trapped.
- **P4.** Fingerprint: on every pair the restart arm's flagged set equals the
  defaults arm's emulated set and the transition-99 steps are equal; every
  non-firing pair is bit-identical (all-chain draw hash and total target
  calls); every non-flagged chain of a firing pair is bit-identical per chain
  (draw hash and target calls).
- **P5.** The detector fires on 0 of the 18 regression cells, so the
  regression arm is identical (equal passes, efficiency ratio exactly 1).
- **P6.** Pooled over L1 and L2, the restart arm spends fewer target calls
  than defaults if at least one restart occurs.
- **P7.** A restarted chain ends trapped in at most 1 case.

## Decision rule (frozen)

- **E (efficacy).** Pooled over L1 and L2 (96 chains per arm): defaults has
  >= 2 trapped chains and restart has at most `floor(defaults / 2)`. If
  defaults has fewer than 2 pooled, efficacy is not evaluable and the rule
  cannot pass (verdict **inconclusive, no events**).
- **F (fingerprint).** P4 on every pair, without exception. A failure is an
  implementation fault: verdict **failed (implementation)** whatever else
  holds.
- **G (lotka gates).** Lotka cells passing every gate: restart >= defaults,
  pooled over L1 and L2.
- **R1.** Regression cells passing every gate: restart >= defaults (of 18).
- **R2.** Geometric mean of the six per-model efficiency ratios >= 0.95.
- **R3.** Wrong-chain regression cells: restart <= defaults.

**SUPPORTED** iff E, F, G, R1, R2 and R3 all hold. Then, and only then, the
README recommends a default-flip *confirmation* study (fresh seeds, broader
posteriordb; the house rule that any default flip needs a v7-style
validation). Otherwise NOT SUPPORTED (or INCONCLUSIVE / FAILED as above) and
no default change is proposed. **No default is changed in this study.**

My own expectation, for the record: the Linux build will produce lotka
trapping at a rate similar to WP57's (about 1 in 24 chains), the restart will
remove most of it, and the regression arm will be bit-identical because the
step rule will not fire there. The risk I see is too few events: with about
4 trapped chains expected over 96, E can fail on the event count alone.
