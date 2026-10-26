# WP74 preregistration: a split-aware chain-disagreement check

Frozen before the first evidence cell. Machine-readable copy: `protocol.json`
(that file governs where the two differ). Ledger number WP74, assigned by the
coordinator (WP71–73 are taken).

## Question and background

The shipped warning (`diagnostics::ChainWarning`, WP44) has four disagreement
checks, each evaluated on a finished run:
- **D1** end-of-warmup step < 0.1 x the chains' median;
- **D2 / D3** a chain's median log density over the last slow warmup window
  / the retained draws sits more than 3 x the median within-chain IQR below
  the median over chains of the chains' medians;
- **D4** `ChainDisagreement`: the all-chain maximum rank R-hat exceeds 1.01
  and drops to at most 1.01 when this one chain is left out.

What is known (open question 7):
- WP44: zero D1–D3 false positives on 60 healthy-or-failing cells, D4 false
  only at R-hat 1.013 / 1.014; sensitivity rests on one wrong-chain cell.
- WP52: it flagged every lost cell in both start arms and named the hidden
  `hmm_drive_0` chain that R-hat missed.
- WP55: 2/12 on silent-funnel cells (it is not a gate-failure detector).
- WP69: on the WP52 two-mode target it reported the 2 one-chain-minority
  splits but **none of the 3 two-versus-two splits**, while max split
  R-hat > 1.01 caught all 12 second-mode cell-arms.

Why 2-2 is missed is structural:
- D4 needs a single chain whose removal fixes R-hat; with two chains per
  mode no single removal does.
- D2/D3 compare each chain with the median over chains, which a 2-2 split
  puts halfway between the groups.
- On the two-mode target the two modes' log densities differ by only
  ln(0.7/0.3) = 0.85 nats, far below 3 IQRs, so no density rule can see that
  split at all.

**Question.** Can a split-aware check, added to the shipped warning,
report every multi-modal split (3-1 and 2-2) without new false positives and
without losing any warning the shipped rule gives?

## Candidate checks (fixed here; `src/split_rules.rs`)

All three are observe-only: they read the finished run's retained draws and its
`RunTelemetry::warmup_end()` / `sampling_end()` window summaries. **No
library change, no kernel change, draws unchanged.** A candidate warning is
the shipped disagreement checks plus the candidate check (additive).

- **K, pairwise agreement clusters (primary; added after the smoke, see
  below).** D4's columns, R-hat and threshold applied to pairs of chains.
  - Needs at least 3 chains and all-chain max R-hat > 1.01.
  - Two chains **agree** iff the max R-hat over parameters of that pair
    alone is <= 1.01.
  - The clusters are the connected components of the agreement graph. The
    reference cluster is the largest. On a size tie it is the one with the
    higher mean retained-draw median log density; if that is tied or
    undefined, the cluster holding the lowest chain index.
  - K fires iff there are at least two clusters **and** the reference
    cluster has at least two chains. It names every chain outside the
    reference cluster.
  - What it covers: a 3-1 split, a clean 2-2 split, and a split with a chain
    that crosses between modes (it disagrees with every other chain and is
    named). It stays silent when no two chains agree (all-chain poor mixing,
    the funnel): that is not a split.
- **S, split R-hat (secondary).** D4's leave-one-out test extended to every
  complementary pair, with D4's columns (every `ChainOutput` sample
  coordinate), D4's R-hat (`diagnostics::rhat`, rank-normalised folded split
  R-hat, NaN-ignoring max over parameters) and D4's threshold 1.01.
  - Needs at least 4 chains and all-chain max R-hat > 1.01.
  - Scores every partition of the chains into two groups of at least two.
    A partition **agrees** iff the max R-hat over parameters is <= 1.01
    within each group.
  - Fires iff some partition agrees. It reports the agreeing partition with
    the smallest larger-group maximum (first in enumeration order on a tie)
    and names its smaller group. For equal groups it names the group with
    the lower mean retained-draw median log density; if that is tied or
    undefined, the group without chain 0.
  - With 4 chains there are exactly 3 partitions (2-2). A 3-1 split has no
    agreeing 2-2 partition, so S is silent there and D4 covers it; all-chain
    poor mixing has no agreeing partition either.
- **G, density clusters (third).** On each window D2/D3 score, with
  their preconditions (>= 3 chains, windows >= 10 transitions, finite
  medians and IQRs):
  - sort the chains' median log densities and cut between neighbours
    wherever the gap exceeds 3 x the median within-chain IQR (D2/D3's scale);
  - with two or more clusters, the reference cluster is the largest (on a
    size tie, the one with the highest medians), and every chain outside it
    is named.
  - G is two-sided. Unlike D2/D3 it sees a 2-2 split whose groups differ by
    more than 3 IQRs (D2/D3 need 6, because the median sits halfway).

## Instrument

- **Machine.** Lane 4 of the shared box: c7a.4xlarge, Ubuntu 24.04, Rust
  1.88.0. Every build and cell runs under `taskset -c 12-15` with
  `RAYON_NUM_THREADS=4`, `OMP_NUM_THREADS=1` and `TMPDIR` under the lane.
- **Co-tenancy.** The study runs core-pinned on a shared box with other
  lanes active (shared L3 and memory bandwidth). Walls are "pinned,
  co-tenanted" and are not evidence. Draws, R-hat, warnings and gate passes
  are not affected.
- **Library.** Main at `90540b21` (WP69 merged), no change. The harness
  enables the `research` feature only because the copied WP69 binaries keep
  their (unused) restart arm; it changes no draw.
- **Models.** BridgeStan 2.9.0 (no `STAN_THREADS`, gcc 13.3.0).
  - The 17 WP69 libraries are copied byte-identically from the WP69 lane.
  - `seeds_centered` and radon `hierarchical_intercept_centered` are built
    the same way by `prepare_models.py`.
  - Hashes are in `artifacts/models.json`.
- **References.** posteriordb `28f8d3d`, read directly from its files.
  `seeds_centered`, radon and the funnel have no posteriordb reference, so
  their replay cells are not scored. Arm (iii) needs no reference.
- **Gates.** v7: rank R-hat <= 1.01, bulk and tail ESS >= 400, 0
  divergences, finite draws, no error, on every posteriordb reference
  parameter (ArviZ 0.23.4, WP69 code). A cell that errors or times out fails
  every gate.

### Harnesses

- **`pdb-cell`.** WP69's `pdb_cell.rs`, defaults arm only: the shipped
  defaults, 4 x 1,000/1,000, `Init::best_of(16)`, `ReplicatedStanTarget`
  (replicated dispatch).
- **`two-mode`.** WP69's `two_mode.rs`, defaults arm only (WP52 target,
  best-of-16 starts).
- **`replay-cell`.** The WP55 harness verbatim (`silent_funnel_diagnostic_v1/src/main.rs`,
  itself the WP44 cell): `Init::uniform()` starts, `Metric::diagonal()`,
  `Tuning::default()`; the 10-D house funnel with starts omega in
  {-3, -1, 1, 3}. Per-chain draw hashes are added.
- **The split-rule record.** Each binary adds one call,
  `split_rules::evaluate(posterior.chains())`. It records:
  - the shipped warnings (via `ChainWarning::from_chains`);
  - K, with every pair's R-hat and the clusters;
  - S, with every partition's R-hats;
  - G, with both windows' medians, IQRs, gaps and clusters.
  
  Apart from that call, only header comments and schema names changed.
- **`run_study.py`.** The WP69 posteriordb plumbing (`reference`,
  `constrain`, `arviz_stats`, `score` without the lotka z gate) plus the
  three cell kinds.
- **`analyze.py`.** Written before the evidence. Its context-only
  comparison with the source studies' recorded warnings reads their
  `artifacts/cells/` files, which are added to the box's sparse checkout.

### Smoke (non-evidence, seed 7409901, before freezing)

Run on the box at the harness committed as drafts `a4da1eb5` (S and G
only) and `69a2e067` (K added). Seed 7409901, one cell of each kind.

**Draft 1 (S, G).**
- **Two-mode cell.** It ended 2-2 by the frozen end-mode definition: chains
  0 and 2 minor, 1 and 3 major, max R-hat 1.668.
  - But chain 2 crossed the boundary once and spent 49.3 % of its retained
    draws in the major mode.
  - Pairwise R-hats: {1, 3} 1.006; every other pair 1.57–1.83.
  - The shipped warning was silent. **S was silent:** in the only
    candidate partition, {0, 2} disagrees internally (1.573) because chain 2
    holds both modes. G was silent too (maximum gap 0.07 of its threshold).
- **`eight_schools_centered`** (`pdb-cell`): R-hat 1.0735, fails; no rule
  fired.
- **Funnel** (replay): R-hat 1.026; no rule fired.
- **Radon** (replay): R-hat 1.006; no rule fired.
- The implementation check held on all 4 cells.

**The change before freezing.** That two-mode cell is exactly the case the
question is about: a split the shipped rule misses. It showed that S's
requirement that *both* groups agree internally fails whenever a chain is
caught mid-crossing. Before freezing I therefore added K (only the
reference cluster must agree internally) and made it the primary
candidate, ahead of S and G.
- K was designed after seeing this one non-evidence cell, so that cell is
  not evidence for K.
- The thresholds, columns and R-hat are D4's; nothing was tuned to a
  number.

**Draft 2 (K added).**
- All 4 cells gave the same draw hashes as draft 1.
- On the two-mode cell, K's clusters are {1, 3}, {0}, {2}, so it names
  chains 0 and 2: exactly the minor-ending group.
- On the other three cells every chain is its own cluster, so K is silent.
- The implementation check held on all 4 cells.

**Analysis dry run.** `analyze.py` ran end to end on these smoke cells
relabelled into blocks I–IV (in `tmp/`, not kept).

Smoke cells are in `artifacts/smoke-v1/` (draft 1) and `artifacts/smoke/`
(draft 2). None is evidence.

## Arms and cells (strictly sequential in this order; none rerun; failures are results)

| block | arm | cells | what | role |
|---|---|---|---|---|
| I | (i) | 6 | two-mode target, fresh seeds 7401201–7401206 | decision |
| I | (i) | 6 | `hmm_drive_0`, fresh seeds 7401101–7401106 (`pdb-cell`) | decision |
| II | (ii) | 51 | 17 house models x fresh seeds 7402001–7402003 (`pdb-cell`) | decision |
| III | (iii) | 14 | WP55 replays (`replay-cell`, seeds 731401–731403): its 12 silent-funnel positives (funnel10, `eight_schools_centered`, `seeds_centered`, radon centred) plus the two other WP55 cells where the shipped warning fired (`hmm_drive_0` 731401, `arma11` 731401) | decision |
| III | (iii) | 10 | WP44's targeted wrong-chain block replayed (`replay-cell`): `hmm_drive_0` and `lotka_volterra` x 97464–97468, `Init::uniform()` | decision |
| III | (iii) | 2 | the WP57/WP67 trapped `lotka_volterra` seeds 5701103, 5701106 at the current defaults (`pdb-cell`) | decision |
| IV | (i) | 7 | motivating replays of WP69: two-mode 6903201–6903206 (the three missed 2-2 splits are 6903201/02/05) and `hmm_drive_0` 6903102 | reported, not decision |

96 cells in all.
- **Fresh seeds.** None of the fresh seeds appear in any protocol,
  preregistration, README or driver in the repository or sibling worktrees.
- **Interpretation of "WP44's targeted bad-start cells".** WP44 had no
  forced-start block. Its targeted cells were the `hmm_drive_0` /
  `lotka_volterra` block at 97464–97468 under the then-default
  `Init::uniform()`, which held WP44's only positive (lotka 97467). I replay
  that block, plus the WP57/WP67 trapped-chain seeds, which are this
  project's reproducible bad-start cells.
- **Replays reproduce runs, not necessarily the source studies' draws.**
  The WP44/WP55 cells ran on Windows, and WP64 found that Linux reproduces
  pass counts but not draws. The WP67/WP69 cells ran on this box at the same
  kernel, so their hashes are expected to reproduce (expected values are in
  `protocol.json`). Arm (iii) compares the shipped and candidate warnings on
  the *same* replayed run; the source studies' recorded warnings are context
  only.
- **Timeouts.** `pdb` and replay 2,700 s (WP44/WP55), two-mode 1,800 s.

## Definitions

- **Off chain.** A chain whose retained mean is more than 3 reference SD
  from the posteriordb reference mean on some reference parameter (the
  WP44 / WP69 wrong / second-mode chain).
- **Split.**
  - Two-mode target: the chains do not all end in the same mode (end mode =
    the majority mode of the chain's retained draws, WP69 harness).
  - `hmm_drive_0`: at least one off chain.
  - The kind is 3-1 if one chain is apart and 2-2 if two are.
- **Reported.** The candidate warning names at least one chain on the cell.
- **New warning.** The candidate check itself (S or G) fires on the cell,
  whether or not a shipped check also fires.
- **False positive.** A new warning on an arm (ii) cell that passes every
  gate.
- **Regression.** On an arm (iii) cell, a chain the shipped disagreement
  checks name that the candidate warning does not.
  - The candidates are additive, so a regression can only come from an
    implementation error. Clause (iii) is therefore a check that the
    candidate keeps every shipped finding on the cells where the shipped
    rule is known to fire, not an empirical risk.
  - What the new checks add on those (mostly wrong) cells is reported.
- **Implementation check.** On every completed cell, the shipped warnings
  recorded through `split_rules` equal the harness's own
  `Posterior::chain_warnings()` / `Summary::chain_warnings`:
  - text for text on `pdb` and replay cells;
  - chain for chain on two-mode cells.

## Predictions (written before any evidence cell)

- **P1.** Arm (i):
  - K reports every fresh split: 2-2 and crossing splits through K, 3-1
    through D4 and K.
  - Both fresh blocks together give at least one 2-2 split. WP69 saw three
    2-2 splits in 6 two-mode cells.
  - On every reported 2-2 split without a crossing chain, K names exactly
    one true mode group.
- **P1b.** S reports every clean 2-2 split but misses any split with a
  chain caught mid-crossing. Whether S passes (i) depends on whether such a
  chain occurs among the fresh cells.
- **P2.** G misses every two-mode 2-2 split (0.85 nats is far below 3
  IQRs), so G fails clause (i) whenever a two-mode 2-2 split occurs. On
  `hmm_drive_0` (second mode about 62 nats down, 3 x IQR about 6.5) G
  reports any split it sees.
- **P3.** Arm (ii): zero false positives for K and S (a gate-passing cell
  has reference-parameter R-hat <= 1.01, and K and S need > 1.01 on the
  unconstrained coordinates) and for G (healthy
  WP44 margins were a 0.29 IQR maximum gap against 3). The shipped warning
  fires on no passing cell.
- **P4.** *My expectation, not a clause.* K fires on at least one failing
  arm (ii) cell where no chain is off: a noise warning on a marginal-R-hat
  cell such as `eight_schools_centered`, `one_comp` or `accel_gp`, where two
  chains happen to agree and the others do not. This is the practical cost
  the decision rule does not count.
- **P5.** Arm (iii): zero regressions for K, S and G. The WP67 seeds and the
  WP69 motivating replays reproduce their recorded draw hashes, and the
  shipped warning names lotka chain 3 / chain 2 again.
- **P6.** Motivating replay (block IV): K reports all three WP69 2-2 splits
  (6903201/02/05), and the shipped rule again misses them.
- **P7.** The implementation check holds on every completed cell.

## Decision rule (frozen)

- **(i)** Every fresh split cell of arm (i) is reported, and at least one
  fresh 2-2 split occurred. If none occurred, (i) is not tested and nothing
  is proposed.
- **(ii)** Zero false positives over the 51 arm (ii) cells.
- **(iii)** Zero regressions over the 26 arm (iii) cells.
- **PROPOSE K** iff (i), (ii) and (iii) all hold for K. Otherwise
  **PROPOSE S** iff they all hold for S. Otherwise **PROPOSE G** iff they
  all hold for G. Otherwise **DO NOT PROPOSE**.
- A proposal is a warning change: a new observe-only `ChainWarning` variant
  and its summary line. It is not a kernel change, and draws are unchanged,
  so there is no fingerprint issue. **No library code changes in this
  study.**
- An implementation-check failure means FAILED (implementation).
- Block IV and P4 are reported but are not decision clauses.
