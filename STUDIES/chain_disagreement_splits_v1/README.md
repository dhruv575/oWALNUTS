# WP74: a split-aware chain-disagreement check (`chain_disagreement_splits_v1`)

## Verdict

**PROPOSE K** under the frozen rule: (i), (ii) and (iii) all hold for K.
K is an additive, observe-only `ChainWarning` check, so draws do not change
and there is no kernel change. It should ship, documented as covering
splits in which **at least two chains agree**. It does **not** report every
multi-modal split: the motivating replays show one 2-2 split it misses.
S fails (i). G fails (i) and (ii).

**K, the rule.** It runs only when the all-chain maximum rank R-hat
exceeds 1.01. Two chains agree when the maximum R-hat of that pair alone is
at most 1.01. K takes the connected components of this agreement graph,
picks the largest as the reference (on a size tie, the higher retained log
density), and names every chain outside it. It fires only if the reference
holds at least two chains. It uses D4's coordinates, R-hat and 1.01
threshold, with nothing tuned.

**Arm (i), splits: holds for K.** The fresh blocks (6 two-mode seeds and 6
`hmm_drive_0` seeds) produced 5 split cells: one 2-2 and four 3-1.
- K reported **5/5**.
- The shipped rule reported **1/5**: only the `hmm_drive_0` cell, through
  D2 + D4. It missed every two-mode split, including three 3-1 splits.
- In those three 3-1 splits a majority chain had crossed the 8-SD gap
  during sampling, so no single chain removal brought R-hat under 1.01.
- K names the minority chain plus the crossing chain there. So it names
  "exactly one true mode group" on the clean 2-2 split and the `hmm_drive_0`
  cell, but not on the crossing cells.
- S reported only the 2-2 split; it misses whenever a chain is mid-crossing.
- G reported only the `hmm_drive_0` cell. The two modes differ by 0.85 nats,
  about 0.1 of G's threshold.

**Arm (ii), false positives: holds for K and S, fails for G.** Over 51
fresh house cells, 43 pass every gate.
- K and S fire on **none of the 43**.
- G fires on 2 of them, the same chains the shipped D2 already names.
- **The shipped warning itself fires on 3 passing cells** (`hmm_drive_0`
  7402001 / 7402003, `lotka_volterra` 7402001). Each is a transient
  warmup-window density dip (D2) or step dip (D1) on a chain that ends
  within 0.2 reference SD. WP44 saw none at the old `Init::uniform()`
  default. This is not a WP74 clause, but it bears on open question 7.
- On failing cells K fired twice: it repeated D4's chain on `sblrc`
  7402002, and it named the real lotka trap on 7402002.

**Arm (iii), no regressions: holds for K, S and G (0 of 26).** This is
guaranteed by construction, since every candidate is additive, and the
implementation check held on all 96 cells.
- The shipped rule fired on 9 replay cells, and K named the same chains on
  8 of them.
- On the ninth, `arma11` 731401 (a D1 + D2 frozen-start chain whose mean is
  on the reference), K is silent but the shipped finding stays.
- New K findings on wrong cells:
  - `eight_schools_centered` 731402: chain 3, no chain more than 3 SD off,
    R-hat 1.069;
  - radon 731401: chain 1 alongside the shipped chain 0.
- Hashes reproduced 9/9: the WP67 trapped seeds, and WP69's six two-mode
  cells and `hmm_drive_0` 6903102.

**Motivating replays (block IV, not decision).** K reports 5 of WP69's 6
split cells, including 2 of the 3 two-versus-two cells the shipped rule
missed.
- It misses 6903202. Two chains crossed, so even the two chains that end
  in the same mode disagree (pair R-hat 1.025) and no two chains agree.
- R-hat > 1.01 still flags that cell.

## Reading

- **How the shipped warning misses on the two-mode target.** It misses
  two-mode splits whenever no *single* chain explains R-hat, and that is
  usually the case here: 2-2 splits, and 3-1 splits with a chain that
  crossed modes.
- **K fixes the common cases.** Pooled over the fresh and motivating
  cells, K reports 10/11 split cells and the shipped rule 3/11. K added no
  warning on any gate-passing cell.
- **The residual gap is structural.** When crossings leave no two chains
  agreeing, an agreement-based rule has nothing to anchor on. R-hat remains
  the check there.
- **The fresh evidence is thin.** It contains a single 2-2 split.
- **The shipped rule fires on healthy cells more often than WP44
  reported.** Under the current best-of-16 default it fired on 3 of 43
  gate-passing house cells (warmup-window checks), against WP44's 0 of 60
  under the old uniform-start default.

## Design (frozen at `b0a1cfe9` before the first cell)

- **Library.** Main at `90540b21`, unchanged. The three candidates live in
  `src/split_rules.rs` and read finished runs only.
- **Candidates.**
  - **K** was added after the non-evidence smoke (seed 7409901). There S
    missed a 2-2 split whose chain 2 had crossed. The change is disclosed in
    `PREREGISTRATION.md`.
  - **S** scores every complementary partition and requires both groups to
    agree.
  - **G** clusters the chains' median log densities on D2/D3's 3-IQR
    scale.
- **Cells.** 96, run once in order, 03:00–03:58 UTC 2026-10-26, all ok.
  - **I:** two-mode 7401201–06 and `hmm_drive_0` 7401101–06, at the
    defaults with best-of-16 starts.
  - **II:** 17 house models x 7402001–03 at 4 x 1,000/1,000, through
    `ReplicatedStanTarget`.
  - **III:** replays.
    - WP55: the 12 silent-funnel positives plus `hmm_drive_0` and `arma11`
      731401, through the WP55/WP44 harness with `Init::uniform()`.
    - WP44's targeted `hmm_drive_0` / `lotka_volterra` block 97464–68.
    - The WP67 trapped seeds 5701103 / 5701106.
  - **IV:** WP69's two-mode 6903201–06 and `hmm_drive_0` 6903102.
- **Machine.** Lane 4 under `taskset -c 12-15`; pinned and co-tenanted,
  and walls are not evidence.
- **Definitions.**
  - **Split:** for the two-mode target, the chains' end modes differ; for
    `hmm_drive_0`, some chain is more than 3 reference SD off.
  - **False positive:** a candidate firing on a gate-passing arm (ii) cell.
  - **Regression:** a shipped-named chain that the candidate does not name.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | K reports every fresh split, at least one 2-2 occurs, and K names one true group on clean 2-2 splits | 5/5; one 2-2, named correctly | yes |
| P1b | S misses splits that contain a crossing chain | missed 3/4 3-1 crossing cells | yes |
| P2 | G misses two-mode 2-2 splits, and reports `hmm_drive_0` splits | missed all two-mode splits; reported the `hmm_drive_0` split | yes |
| P3 | 0 false positives for K, S and G, and the shipped warning silent on passing cells | K 0, S 0; G 2; shipped fired on 3 | partly (K, S held; G and shipped failed) |
| P4 | K noise warning on a failing cell with no off chain (expectation) | `sblrc` 7402002 (duplicating D4) and ESC 731402 | yes |
| P5 | 0 regressions, and hashes reproduce | 0; 9/9 | yes |
| P6 | K reports all three WP69 2-2 splits | 2/3 (missed 6903202) | no |
| P7 | the implementation check holds | 96/96 | yes |

## What follows

- **Ship K as a new observe-only `ChainWarning` variant**, printed in the
  same "chain k disagrees with the other chains" line. Its documentation
  should say three things:
  - it covers splits with at least two agreeing chains;
  - a cell with R-hat > 1.01 and no warning is still a failure;
  - it can name a chain that crossed modes, not only the minority group.
- No `ALGORITHM_REVISION` bump: draws are unchanged.
- **Open question 7 should record two things:**
  - the residual miss (6903202);
  - the shipped warmup-window checks firing on 3/43 healthy cells under
    best-of-16 starts.
- **Untested:** a cross-mode-aware variant. One example: cluster chains by
  pairwise R-hat restricted to the first half or the second half of the
  retained draws.

## Files

- **Frozen design** (at `b0a1cfe9`): `PREREGISTRATION.md`, `protocol.json`.
- **Code:** `src/split_rules.rs`, `src/bin/{pdb_cell,two_mode,replay_cell}.rs`,
  `run_study.py`, `analyze.py`, `prepare_models.py`.
- **Results:** `artifacts/cells/` (96 cells), `artifacts/summary.json`,
  `artifacts/results-table.md`.
- **Logs and inputs:** `artifacts/run-log.txt`, `artifacts/analyze-log.txt`,
  `artifacts/measured_on.json`, `artifacts/models.json`,
  `artifacts/smoke{,-v1}/`.
- **Not in git:** the draws.
- **Checksums:** `CHECKSUMS.sha256`.
