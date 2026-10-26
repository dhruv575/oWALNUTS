# WP89: why one chain freezes in warmup on the WP84 SV model (`sv_stuck_chains_v1`)

Status: preregistered at `0d88b8f1` (before any evidence cell; harness `23785f41`, base `main`
`522a6c84`); executed 2026-10-26 18:46-20:27 UTC on the shared Linux box, lane 1 (cores 0-3),
pinned, co-tenanted. 1,416/1,416 cells completed; none rerun; no errors. Tables:
`artifacts/results-table.md` (rates, rules), `artifacts/mechanism.md` (telemetry classes);
machine-readable `artifacts/summary.json`, `artifacts/mechanism.json`.

## Verdict

**Question 1, answered.** A chain is trapped when its best-of-16 start sits at log_sigma
above about 1.3 (8/8 oWALNUTS, 17/17 CmdStan; no trap started lower) and its first
transitions are rejected: the identity-metric step then collapses (below 1e-4 by transition
5-6) and the first metric update at transition 99, computed from a window in which the
chain barely moved, installs the Stan regularisation floor (mass 6,000) on every coordinate
(8/8), which locks the chain 1,000-4,300 nats below the mode for the rest of warmup at
807k warmup gradients against 171k for a healthy chain. The warnings named all 8.

**Question 2, answered.** nutpie does not trap because its initial mass matrix is
gradient-scaled: with the same starts rule, nutpie's initial metric alone takes oWALNUTS
from 8/480 to 1/240 trapped chains (`nutpie_init`); its standard-normal starts help a
little (1/240); Stan's step search, the estimator and the window schedule do not.

**Question 3, answered.** Three candidates each took the trapped rate from 8/480 to 0/480
(nutpie's 0/480) with every frozen rule R1-R5 holding: unfired cells bit-identical to the
defaults, the funnel P5 within 2 s.e. of exact, the house models at or above the defaults'
passes and the library tests and clippy clean. **Proposed for confirmation (not flipped):
`guard-0.01-0`, the WP67 restart rule at ratio 0.01 instead of 0.1 at transition 99**:
10 firings on 480 chains, 8 on the trapped chains and 2 on near-traps that would have
recovered by transition 157 and 325 (both restarts ended at the mode), none on the funnel
or the house models, 110/110 unfired cells bit-identical. `guard-0.01-1` (same ratio at
transition 149, this study's `with_check_window(1)`) is equal on every rule with 9 firings;
`restart` (ratio 0.1) qualifies too but fired on a healthy funnel chain (seed 8903004 chain
0, ratio 0.076; the cell stayed within the gates), which the 0.01 guards did not, so the
looser ratio is not the one proposed. No default changed in this study. Cost of the guard:
none observed (Part C medians 2.3 s per cell against 2.3 s for the defaults; a restarted
chain repeats 100 of 1,000 warmup transitions).

Trapped chains / 480: nutpie 0 (0 %), oWALNUTS defaults 8 (1.7 %; 8/120 cells, WP84 saw
21/300), CmdStan 17 (3.5 %; 17/120 cells, WP84 39/300); `restart`, `guard-0.01-0`,
`guard-0.01-1` 0 each. Part B / 240: `nutpie_init` 1, `normal` 1, `median16` 0, `uniform` 2,
`small_step` 2, `grad_metric` 4, `early_windows` 5, `unit_reg` 5, `stan_search` 8.

## The mechanism (question 1), with numbers

Every trapped chain, in every sampler and arm, is the same event:

1. **It starts at log_sigma > 1.3.** oWALNUTS defaults: the 8 trapped chains started at
   log_sigma 1.57-1.97 (median 1.74; 8/8 above 0.5); CmdStan's 17 at 1.30-1.97 (median 1.71).
   No chain that started below 1.3 was trapped in any arm. Among the 472 healthy defaults
   chains the chosen best-of-16 start has log_sigma quartiles -1.0 / 0.0 / 1.0 (22 % above
   0.5): best-of-16 does not single out large sigma, but one chain in four starts there.
2. **The start is a stiff basin.** At sigma = e^1.7 = 5.5 the h recursion turns the
   z-coordinates into a stiff, strongly coupled ridge: the trapped chains' max |gradient| over
   S1 is 3.9e6 to 5.8e11 (median 2.5e7) against 1.5e3 for healthy chains at the mode, and the
   start log density is -2.5k to -10.6k (healthy: -2.4k median, but those move).
3. **The first transition decides.** Healthy chains that start at high log_sigma are flung
   by the first transition (step 0.5-0.6, depth 1-3) to the low-sigma side (log_sigma after
   transition 0: median -1.42 over healthy chains; -32 to -53 in the smoke cell) where the
   geometry is benign (max |gradient| 4e2-2e3), and climb to the mode in about 25
   transitions. A trapped chain's first transitions are rejected (refinement exhausted at
   step 0.5-1.2): its log_sigma after transition 0 equals its start (8/8).
4. **Dual averaging then collapses the step.** Under the identity metric the trapped chain's
   step is below 1e-4 by transition 5-6 (median 5) and 9e-6 at transition 10; it crawls
   (90 % of transitions move, at the 1e-6 scale) at 700-900 gradients per transition,
   depth 8-10. Healthy chains sit at 4e-4 through the identity phase too (depth 8-9, 800
   gradients per transition: the identity metric is wrong by 10-150x on z for everyone),
   and jump to 0.03-0.1 at the first metric update.
5. **The first metric update locks it.** At transition 99 the trapped chain's window variance
   is about 0, so Stan's regularisation installs the floor 1e-3 x 5/30 on every coordinate:
   mass 6,000 on 100 % of coordinates (8/8 trapped chains; healthy chains: median mass 9).
   The step after the update is 1e-7 to 1e-13; later windows re-install larger floors
   (1.1e4, 2e4, ...). The chain ends warmup at log_sigma 1.5-1.8, 2,000-4,000 nats below the
   mode (S1 median -2,427 vs +524), with 807k warmup gradients against 171k, zero divergences,
   and R-hat 1.59 on the cell.
6. **Near-traps show the same signature and escape by luck.** Two defaults chains with the
   full signature (start 1.83/1.86, step 2e-6 at transition 10, mass 6,000 at 99) escaped at
   transitions 150 and 325, after a metric update computed from a window in which they had
   moved; the smoke's 9989017 chain 2 escaped at about 200. They cost 377k warmup gradients
   and left no warning.

The chain warnings `WarmupStep` and `SampledLogDensity` named exactly the 8 trapped chains
(0 missed, 0 false; `RHatCluster` added the healthy partner on one cell and `RHat` 1.011 on
another). CmdStan: the same picture from `stepsize__` (1e-6 to 1e-10 from the end of the
initial window on; 17 cells with R-hat 1.6), with the Stan `init_stepsize` overshoot to 11-14
at transitions 1-2 first.

## Why nutpie does not trap (question 2)

nutpie's step is 0.25-0.5 from the first transition on (medians at the checkpoints 0.34-0.37;
0/480 chains trapped, 0 cells with R-hat > 1.01). Part B separates its two differences:

- **The initial mass matrix is the mechanism.** `nutpie_init` (nutpie's rule mass_i =
  clamp(|g_i(start)|, 1e-20, 1e20) at the best-of-16 start, then oWALNUTS's own adaptation)
  trapped 1/240 chains (0.4 %) against the defaults' 8/480 (1.7 %), with the same starts rule;
  the one trap started at log_sigma 2.00. The gradient at a stiff start is exactly the
  information the identity metric lacks: scaling z by 1/|g| lets the first transition move.
- **The start rule matters too, less cleanly.** `normal` starts (nutpie's) trapped 1/240,
  `uniform` 2/240, `median16` 0/240 (the median candidate rarely sits at the box edge), so
  avoiding log_sigma > 1.5 starts helps; but CmdStan with uniform starts trapped 17/480,
  so the start rule is not what separates nutpie from Stan.
- **Not the mechanism:** `stan_search` (Stan's `init_stepsize`) 8/240, `small_step`
  (initial step 0.05) 2/240, `grad_metric` (nutpie's estimator from transition 100 on)
  4/240, `early_windows` (first metric at transition 20) 5/240: the step rule and the
  estimator in the Stan windows do not help because the chain is already frozen when the
  first window closes. `unit_reg` (the `TowardUnit` floor) trapped 5/240 and wrecked every
  healthy chain (final step 0.004 against 0.12, 20 s per cell): the model's `beta` has prior
  SD 0.002 (variance 4e-6), so a floor of 0.17 is 4e4x too large there. Even Stan's floor
  (1.7e-4 at window 1, 1e-5 at window 5) is 2.5-40x too large on `beta`, which is what holds
  the healthy final step at 0.12.

With 60 seeds per arm (about 4 expected events) the B rates separate `nutpie_init`,
`median16` and `normal` from `stan_search` and the defaults, but not the arms in between.

## Candidates (question 3)

Three candidates ran on the Part A seeds, paired with `A-defaults` (same 16 candidates and
chosen start per chain, so an unfired candidate cell must be bit-identical). Rules as frozen
in `protocol.json` (R1 efficacy, R2 fingerprint, R3 funnel, R4 house models, R5 library):

| candidate | R1: trapped / 480 (Fisher p vs nutpie's 0/480) | R2: unfired cells bit-identical; fired | R3: funnel P5 (exact 0.0478), fired, identical to `diag` | R4: house passes vs defaults 5/9; fired; unfired identical | R5 | qualifies |
|---|---|---|---|---|---|---|
| `restart` (ratio 0.1, t=99; WP67) | 0 (p 1.0); holds | 110/110; 11 chains on 10 cells; holds | 0.0502 +- 0.0013 (within 2 s.e.); fired 1 (8903004 chain 0, ratio 0.076); 29/30 identical; holds by the P5 clause | 6 vs 5 (`earnings` 8904002 fired on chain 3 at ratio 0.07 and the cell passed, R-hat 1.004 vs 1.012; a cell the defaults fail); 8/8 identical; holds | holds | yes |
| `guard-0.01-0` (ratio 0.01, t=99) | 0 (p 1.0); holds | 110/110; 10 chains on 10 cells; holds | 0.0503 +- 0.0012, fired 0, 30/30 identical; holds | 5 vs 5, fired 0, 9/9 identical; holds | holds | yes (proposed) |
| `guard-0.01-1` (ratio 0.01, t=149) | 0 (p 1.0); holds | 111/111; 9 chains on 9 cells; holds | 0.0503 +- 0.0012, fired 0, 30/30 identical; holds | 5 vs 5, fired 0, 9/9 identical; holds | holds | yes |

R5 is `cargo test` with and without `research` and `cargo clippy --all-targets --all-features
-- -D warnings` on 1.88 (`artifacts/wp89-*.log`), the same for all three since they share
the library change.

What fired, chain by chain (`artifacts/summary.json`, `arms.C-*.fired_cells`): the 8 trapped
`A-defaults` chains (seeds 8901027, 051, 052, 060, 078, 083, 088, 117) had step-to-median
ratios 1e-9 to 1.4e-3 at transition 99 and 3e-9 to 3e-3 at 149, so every candidate fired on
all 8 and every replacement chain ended at the mode (candidate trapped: 0). The 2 near-traps
of `A-defaults` (8901076 chain 2, ratio 3.6e-3 at 99, would have escaped at 157; 8901101
chain 3, ratio 7.8e-4 at 99 and 1.4e-3 at 149, would have escaped at 325) were fired on by
both `restart` and `guard-0.01-0`; `guard-0.01-1` fired on 8901101 only. `restart` also fired
on 8901117 chain 2 (ratio 1.5e-2, the third near-trap, escaped at 150). In every fired cell
the untouched chains stayed bit-identical to the defaults' (`untouched_identical` true,
31/31 cells). No candidate fires on nutpie-class behaviour: the `diag` funnel's healthy
chains have ratios down to 0.076 at transition 99 (30 cells x 4 chains), the house models'
down to 0.07 (`earnings`), so ratio 0.1 catches healthy chains and 0.01 did not on the 156
control cells of this study.

Cost: Part C walls equal the defaults' (medians 2.26-2.28 s against 2.3 s); a fired chain
repeats the first window (100 or 150 of 1,000 warmup transitions) and ends warmup at the
mode instead of 800k gradients below it. The guard's residual risk is a healthy chain with a
step below 1 % of its siblings' at transition 99 on a model not in this study; the
confirmation study (v7 posteriors x fresh seeds, `guard-0.01-0` vs `defaults`, R2-style
bit-identity on every unfired cell) is the test for that.

## Predictions

Frozen in `PREREGISTRATION.md` before the first evidence cell; evaluated by hand against
`artifacts/summary.json` (the driver scores only P1 and P3a automatically).

- P1 (trapped / 480: defaults 3-16, CmdStan 8-28, nutpie 0-1): **held**, 8 / 17 / 0.
- P2 (mechanism: retained median log_sigma > 0.5 for every trapped chain; step below 0.1 x
  the median by the end of the initial window; first installed metric at the floor on every
  coordinate; at least 80 % start at log_sigma > 0.5; more than 1,000 nats below the healthy
  chains): **held** on all five clauses for the 8 defaults' traps: end-of-warmup log_sigma
  1.49-1.83 (retained medians the same, 8/8 > 0.5); step 1e-7 at transition 99 against a
  healthy 4e-4 (collapse window `init` 8/8); floor share 1.00 (8/8); start log_sigma 1.57-1.97
  (8/8 > 0.5); retained log density -489 to -3,791 against +525 (gap 1,014-4,316 nats).
- P3a (`nutpie_init` 0-1 of 240): **held**, 1 (start log_sigma 2.00; its step reached
  1e-4 at transition 11 rather than 5, the gradient-scaled metric slowed the collapse but did
  not stop it).
- P3b (`unit_reg` at most half the defaults' rate, not zero): **not held**, 5/240 (2.1 %)
  against 1.7 %. The floor is not the amplifier: with mass 6 instead of 6,000 on every
  coordinate the trapped chain still crawls (its step is 1e-7 at transition 99 either way),
  and the `TowardUnit` floor wrecked the healthy chains (final step 0.0039 vs 0.12).
- P3c (`uniform` at least as often as the defaults; `normal` and `median16` within a factor
  of 2): **not held**, `uniform` 2/240 (0.8 %), `normal` 1/240, `median16` 0/240. All three
  are below the defaults' 1.7 %; `median16` and `normal` avoid the box-edge start (the
  defaults' best-of-16 picks a start at log_sigma > 1.5 for 8 % of chains). With 4 expected
  events per arm the B rates separate `median16`/`normal` from `stan_search`, not from the
  defaults.
- P3d (`small_step`, `stan_search`, `grad_metric` within a factor of 2; `early_windows` at
  least as often): **held** at the bounds: 2, 8, 4 and 5 of 240 (0.8 %, 3.3 %, 1.7 %, 2.1 %).
- P4 (each candidate removes at least 80 % of traps; `restart` fires on at least one
  `earnings` cell and the guards on none; no candidate fires on the funnel; `guard-0.01-0`
  fires on at least one A-defaults chain that would have recovered): **three of four clauses
  held**: 100 % removed (8 -> 0, each); `restart` fired on `earnings` 8904002, the guards
  on no house cell; `guard-0.01-0` fired on 8901076 chain 2 and 8901101 chain 3 (both would
  have recovered). **Not held**: `restart` fired on the funnel (8903004 chain 0, ratio 0.076
  at transition 99; the guards did not fire on any funnel chain).
- P5 (R2 holds for every candidate): **held**, 110/110, 110/110, 111/111 unfired cells
  bit-identical and all 31 fired cells with untouched chains bit-identical.

## Design (frozen at `0d88b8f1`)

`PREREGISTRATION.md` and `protocol.json`. Model: the WP84 `Sv` target (copied verbatim) on the
WP84 data (seed 84084, first 250 returns). All SV cells 4 x 1,000/1,000, 4 threads, diagonal
metric. Part A: 120 fresh seeds x {nutpie, CmdStan, oWALNUTS defaults}. Part B: 9 oWALNUTS
arms x 60 fresh seeds. Part C: 3 candidates on the Part A seeds (same starts as A-defaults).
Controls: the funnel at 4 x 2,000/20,000 on 30 seeds (`diag` + candidates); `earnings`,
`eight_schools_centered`, `hmm_drive_0` on 3 seeds by the v7 gates (`defaults` +
candidates). Trapped chain: |median retained log_sigma - anchor| > 1.0 or |median h_last -
anchor| > 2.0, anchor = the A-nutpie medians (-1.853, -10.02). Within a block the cells ran
seed-major with the arms in the listed order (the manifest generator); block order as
listed. The real-data variant was skipped (no reuse licence for the Deribit receipts, as in
WP84). Disclosed smokes before the freeze: `artifacts/smoke/` (30 diagnostic seeds; the
near-trap that motivated the design; `custom_noop` and `lowlevel_noop` bit-identical to
`defaults`; the numpy density equal to Stan's to 9e-11).

## Library change

`TrappedChainRestartConfig::with_check_window(k)` (research feature, `src/walnutpie.rs`,
default 0 = WP67's first-window boundary; `tests/trapped_chain_restart.rs` checks window 1
scores transition 149 and stays bit-identical). No default changed; `ALGORITHM_REVISION`
untouched. `cargo test` (default and research) and `cargo clippy --all-targets -D warnings`
pass on 1.88 (`artifacts/wp89-cargo-test-*.log`, `artifacts/wp89-clippy-research.log`).

## Amendments and deviations

- Analysis-only, after the cells: the funnel part of `analyze()` read the SV cells' keys
  (`status == "ok"`, `draw_hash`) from the funnel cells, which `funnel.rs` (WP85's harness)
  never writes (`tail_mass`, `draws_fnv`); the first table reported 0 funnel cells and R3
  false for every candidate. Fixed in `run_study.py` (`funnel_ok`, `funnel_fired`) and the
  analysis rerun on the unchanged cells; the rule's definition did not change.
- Analysis-only, after the cells: `strip_draws.py` (moves the retained draws out of the cell
  JSONs into `artifacts/draws/*.npz`, out of git, hashed), a None-guard in the results-table
  formatter, and `mechanism.py` (telemetry classes). No cell, rule or definition changed.
- The two Windows-side launcher scripts shipped with CRLF endings and had to be fixed on the
  box before the run started; no cell was affected.
- Pipeline note: within a block the manifest runs seed-major (nutpie, CmdStan, defaults per
  seed), not arm-major as the preregistration's prose suggested; `protocol.json`'s generator
  was the frozen one.

## Files

`PREREGISTRATION.md`, `protocol.json`, `run_study.py` (driver, scoring, analysis),
`mechanism.py`, `strip_draws.py`, `checksums.py`, `src/bin/{sv_cell,pdb_cell,funnel}.rs`,
`models/` (WP84 data and Stan twin). `artifacts/cells/*.json` (1,416 cells, draws stripped),
`artifacts/summary.json`, `artifacts/results-table.md`, `artifacts/mechanism.{json,md}`,
`artifacts/run-log.txt`, `artifacts/measured_on.json`, `artifacts/models.sha256`,
`artifacts/telemetry-hashes.sha256` (1,260 telemetry and 1,260 draw files on the box, out of
git), `artifacts/smoke/`, the cargo logs, `CHECKSUMS.sha256`.

## Reproduce (on the box, lane 1)

```
taskset -c 0-3 cargo build --release -j4            # owalnuts research feature, three binaries
taskset -c 0-3 python run_study.py smoke            # diagnostic seeds, not evidence
taskset -c 0-3 python run_study.py run              # resumable; never reruns a written cell
python strip_draws.py && python run_study.py analyze && python mechanism.py
python checksums.py
```
