# WP69 preregistration: confirmation of the trapped-chain restart

Frozen before the first evidence cell. Machine-readable copy: `protocol.json`
(that file governs where the two differ). Ledger number WP69, assigned by
the coordinator (WP68 is lane 3's `refinement_levels10_v1`).

## Background

WP67 (`STUDIES/trapped_chain_restart_v1`, merged at `fec52186`) supported
its frozen rule on two events:
- `lotka_volterra` trapped chains fell from 2/48 to 0/48 on WP57's seeds;
- there were no trap events on 12 fresh seeds;
- 40/40 non-firing pairs were bit-identical;
- the detector never fired on 6 house models x 3 seeds.

Its README recommended this confirmation and asked it to include:
- many fresh lotka seeds;
- a broad posteriordb specificity panel;
- a case where a chain sits in a *genuine* second mode, which WP67 never
  observed;
- the wall cost of the synchronisation point.

The coordinator specified the four arms and the decision rule below.

## Detector and restart: unchanged from WP67, nothing re-tuned

The library is at `8887a0f0` (`WarmupConfig::with_trapped_chain_restart(TrappedChainRestartConfig::step_rule())`,
research feature, default off).

- **Detector.** Flag chain `c` iff the step it used at transition 99 (the
  last transition of the first slow window) is below 0.1 x the median over
  chains. The rule is evaluated once, with the chains synchronised there.
  It needs at least 3 chains.
- **Restart.** The flagged chain reruns the full schedule from transition 0:
  - from the best of 16 fresh uniform(-2, 2) candidates on an independent
    seed stream;
  - with the initial metric and step, and fresh dual averaging and RNG;
  - at most once per chain.
- **Arms.** `defaults` = `Adaptation::default()`; `restart` =
  `Adaptation::Custom` of that configuration plus the restart.

## Instrument

- **Machine.** Lane 4 of the shared box: c7a.4xlarge, Ubuntu 24.04, Rust
  1.88.0. Every build and cell runs under `taskset -c 12-15` with
  `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1` and `TMPDIR` under the lane.
- **Co-tenancy.** The study runs core-pinned on a shared box with other
  lanes active (shared L3 and memory bandwidth). Walls are therefore
  "pinned, co-tenanted", and arm (d) is read only as a ratio. Gradients,
  ESS per gradient, hashes and passes are not affected.
- **Models.** `prepare_models.py`, unchanged from WP67 except for the model
  list: BridgeStan 2.9.0 source in the lane, gcc 13.3.0, no `STAN_THREADS`.
  WP67's 7 libraries are reused byte-identically and the other 10 are
  built the same way. Hashes are in `artifacts/models.json`.
- **References.** posteriordb `28f8d3d`, read directly from its files.
- **Software.** Python is the shared `~/venv` (arviz 0.23.4, bridgestan
  2.9.0).
- **Sampler.** The shipped defaults, 4 x 1,000/1,000 on 4 threads, starts
  `Init::best_of(16)`.
- **Gates.** v7: rank R-hat <= 1.01, bulk and tail ESS >= 400, 0
  divergences, finite draws, no error, on every posteriordb reference
  parameter. Arm (a) also requires max |z| <= 4, the WP57/WP67 lotka gate.

### Harness changes

- **`src/bin/trap_cell.rs`, `src/bin/pdb_cell.rs`.** WP67's files; only
  their header comments changed.
- **`src/bin/two_mode.rs`.** WP52's `init_rule_confirmation_v1` two-mode
  harness with:
  1. arms `defaults` / `restart`, both with best-of-16 starts (the
     `uniform` / `best_of_16` start arms are gone);
  2. a per-chain and all-chain FNV draw hash, per-chain target calls, the
     transition-99 step and the restart check records;
  3. `chain_warning_chains`;
  4. the schema name.
- **`src/bin/sync_cost.rs`.** New. A 100-D standard Gaussian with an
  analytic gradient, `chains` x 1,000/1,000 on `min(chains, 4)` threads,
  with shared best-of-16 starts. Each cell runs:
  - one untimed warm-up run;
  - then 7 interleaved (defaults, restart) pairs, in reverse order on odd
    repeats. The wall is measured around `Sampler::run`.

  The repeat's ratio is the median restart wall over the median defaults
  wall. Every run's draw hash and target calls are recorded.
- **`run_study.py`.** WP67's driver with:
  1. a manifest over blocks C, M, D, A, B;
  2. cell kinds `lotka` / `pdb` / `two_mode` / `sync`;
  3. the z gate applied to arm A cells only;
  4. new `run_two_mode` and `run_sync`;
  5. the smoke extended to two-mode and sync.
- **`analyze.py`.** New; it reuses WP67's pair and fingerprint helpers. It
  was written before the evidence.

### Smoke (non-evidence, seed 6909901, before freezing)

Run on the box at the harness files committed with this preregistration
(except one change, below):
- **lotka.** `defaults`, `restart`, `custom_noop` and `defaults --plain`
  all give hash `7a569c515eb0f54d` and 279,952 calls, with no flag.
- **two-mode.** `defaults` and `restart` both give `c2bfe831f01b79ee` and
  56,157 calls, with no flag. One chain started in the minor mode and none
  ended there; R-hat 1.002; no warning.
- **`eight_schools_centered`.** Both arms give `409e84b3c1016609` and
  270,735 calls.
- **sync, 4 chains, repeat 0.** Identical draws. Defaults walls were
  0.0383 / 0.0383 / 0.0395 s and restart walls 0.0384 / 0.0387 / 0.0390 s,
  a ratio of 1.0101.

**The one change after the smoke.** A whole 4-chain run takes about 38 ms
here, and the run-to-run spread (about 3 %) is of the same order as the 2 %
threshold. So before freezing I raised the pairs per repeat from 3 to 7.
The 1,000/1,000 shape and the 5 repeats were kept. No evidence cell had
run.

## Arms and cells (strictly sequential in this order; none rerun; failures are results)

1. **C (c): `hmm_drive_0`, 12 cells.** Seeds 952202, 600602, 600605 are
   **declared targeted replications** of the second-mode cells from WP52
   (952202) and WP60 (600602, 600605). They come from a different build
   (Windows), so the second mode need not reappear. Seeds 6903101–6903103
   are fresh. Each seed runs `defaults` then `restart`.
2. **M (c): synthetic bimodal target, 12 cells.** The WP52 two-mode target
   (d = 10, 0.7 N(+4 e1, I) + 0.3 N(-4 e1, I), 8 SD apart), on fresh seeds
   6903201–6903206.
3. **D (d): synchronisation cost, 15 cells.** A 100-D Gaussian at 1, 4 and
   16 chains, 5 repeats each (seeds 6904001–6904005).
4. **A (a): efficacy, 120 cells.** `lotka_volterra` on 60 fresh seeds
   (6901001–6901060) x 4 chains, both arms.
5. **B (b): breadth, 102 cells.** The 17 house posteriordb models x 3 fresh
   seeds (6902001–6902003), both arms.

261 cells in all. The seeds were grepped over the repository and sibling
worktree protocols, and none had been used (apart from the declared
targeted seeds). Timeouts:
- lotka cells: a 1,200 s cooperative cap and a 1,500 s backstop;
- `pdb` cells: 2,700 s;
- two-mode and sync cells: 1,800 s.

## Definitions

- **Trapped chain (A).** A chain of a completed cell more than 3 reference
  SD off on some parameter. In a cell that did not complete, every chain
  that had not finished.
- **False positive (A).** A flagged chain whose defaults counterpart is not
  trapped.
- **False positive (B).** Any flagged chain in a B cell whose defaults cell
  passes every gate. Zero are tolerated.
- **Firing.** A cell with a flagged chain: actual in the restart arm,
  emulated from the transition-99 steps in the defaults arm.
- **Second mode.**
  - `hmm_drive_0`: a chain more than 3 reference SD off.
  - Two-mode target: a cell whose chains do not all end in the same mode.
- **The warning reports it.** `chain_warnings` is non-empty on the cell.
- **Efficiency.** Min bulk ESS / total target calls, including the start
  search, abandoned runs and replacement pools.
  - Per model: the geometric mean over seeds where both arms completed.
  - The ratio is restart / defaults; the headline is the geometric mean
    over the 17 models.
- **Sync overhead.** Per chain count, the median over the 5 repeats of the
  repeat ratio, minus 1.
- **Fingerprint.** On every defaults/restart pair of A, B and C:
  - the flagged sets are equal and the transition-99 steps are equal;
  - a non-firing pair is bit-identical (draw hash and total target calls);
  - every unflagged chain of a firing pair is bit-identical.

  In D, every run of a cell must have the same hash and calls.

## Predictions (written before any evidence cell)

- **P1.** Arm A: defaults has 4–16 trapped chains of 240, and restart has
  at most 1. Earlier studies on these code paths saw about 2 % of chains
  trapped, but that figure includes targeted seeds.
- **P2.** Arm A: the detector has sensitivity 1 on trapped chains that
  reached transition 99, and 0 false positives.
- **P3.** Arm B:
  - fires only on `lotka_volterra` cells;
  - 0 flags on cells that pass at the defaults;
  - passes restart >= defaults;
  - geomean ESS/gradient ratio >= 1.00 (1.0000 on every model where it
    never fires).
- **P4.** Arm C: **0 firings** on all 24 cells; a mode is not a trap,
  because a second mode's step is not 10x smaller. On every
  `hmm_drive_0` cell with a second-mode chain, and on every mixed two-mode
  cell, the chain-disagreement warning is non-empty.
  - *My own expectation, recorded separately:* the warning half of P4 will
    fail on cells with two chains in each mode. WP52 saw the warning
    silent on 2 of 3 mixed two-mode cells, because leave-one-out R-hat
    cannot isolate one chain when two chains share each mode. Max split
    R-hat > 1.01 should still report every mixed cell.
- **P5.** Arm D: overhead under 2 % at 4 and 16 chains. At 1 chain the
  restart path is not entered (fewer than 3 chains), so that ratio
  measures timing noise only.
- **P6.** The fingerprint holds everywhere.

## Decision rule (frozen; coordinator's)

- **(a)** Arm A: restart trapped < defaults trapped (so defaults needs at
  least 1), with 0 false positives.
- **(b)** Arm B: all four of
  - passes restart >= defaults (of 51);
  - geomean ESS/gradient ratio >= 0.99;
  - every unflagged cell bit-identical;
  - 0 false positives (B).
- **(c)** Arm C: zero firings over all 24 cells, both arms, actual and
  emulated.
- **(d)** Arm D: sync overhead < 0.02 at 4 chains and at 16 chains.
- **Fingerprint.** A failure anywhere means the verdict is FAILED
  (implementation).

**PROPOSE THE DEFAULT** iff (a), (b), (c) and (d) all hold and the
fingerprint holds. A default change would bump `ALGORITHM_REVISION` and needs
the house v7-style validation afterwards. Otherwise **DO NOT PROPOSE**. The
warning half of P4 is reported but is not a decision clause. **No default is
changed in this study.**
