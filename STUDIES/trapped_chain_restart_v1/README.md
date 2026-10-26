# WP67: early restart of a trapped warmup chain (`trapped_chain_restart_v1`)

## Verdict

**Supported under the frozen rule. All six clauses hold (E, F, G, R1, R2,
R3), so a default-flip *confirmation* study is recommended. The efficacy
evidence rests on two events.**

- **Trapped chains on `lotka_volterra`, 12 WP57 seeds x 4 chains: 2/48 at
  the defaults, 0/48 with the restart.** The defaults trapped the same two
  chains as WP57 did on Windows (5701103 chain 3, 5701106 chain 2). Their
  starts were the same, and so was R-hat (1.592 and 1.595 here, 1.59 there).
  The restart flagged exactly those two chains at transition 99. Both
  restarted chains ended in the main mode, at shifts of 0.06 and 0.07
  reference SD. Both cells then passed every gate (R-hat 1.003 / 1.004),
  using 4.6x / 2.4x fewer gradients and 9.5x / 5.9x less wall.
- **Fingerprint rule: 42/42 pairs.**
  - On every pair the restart arm's flagged set equals the defaults arm's
    emulated set, and the transition-99 steps are equal.
  - All 40 non-firing pairs are bit-identical to the defaults (draw hash and
    total target calls).
  - In the 2 firing pairs, all 6 untouched chains are bit-identical per
    chain.
- **Regression arm (6 house models x 3 seeds): identical to the defaults.**
  The detector fired on 0 of 72 chains, so passes are 12 = 12 of 18,
  wrong-chain cells 1 = 1, and the geomean ESS per gradient ratio is exactly
  1.0000.
- **Detector accuracy on the 96 lotka defaults chains:** 2 true positives,
  0 false negatives, 0 false positives, 94 true negatives. The lowest
  healthy step ratio was 0.388 on lotka and 0.301 on the regression models,
  against a threshold of 0.1. The trapped chains were at 0.0023 and 0.025.

**Why this is weaker than it looks.**
- There were 2 trap events, both on declared targeted-replication seeds.
  The 12 fresh lotka seeds (L2) had no trap in either arm.
- The rule required at least 2 events, and that floor was met exactly.
- The regression arm tests specificity only. The restart never acted
  there, so its effect on a model with a genuine second mode is
  unmeasured. That includes `hmm_drive_0`, the WP36/WP60 mode-destruction
  concern, which kept no second-mode chain on these seeds.

**No default was changed.** The restart is a research-only opt-in
(`WarmupConfig::with_trapped_chain_restart`, library commit `8887a0f0`).

## Design (frozen at `c4522b8b` before the first cell)

- **Detector.** `s_c` is the step chain `c` used at transition 99, the last
  transition of the first slow window. Chain `c` is flagged iff
  `s_c < 0.1 x median(s)`. It is checked once, with the chains synchronised
  there and nowhere else.
- **Restart.** The flagged chain's 100 transitions are discarded; their
  target calls are still counted. The chain reruns the full 1,000 + 1,000
  schedule:
  - from the best of 16 fresh uniform(-2, 2) candidates, drawn from an
    independent seed stream;
  - with the initial metric and step, fresh dual averaging and a fresh RNG
    stream.

  Nothing is copied from another chain. This is the difference from the
  `restart_from_best` rescue removed in WP36, which copied state.
- **Arms.** `defaults` (`Adaptation::default()`) and `restart`
  (`Adaptation::Custom` of the same configuration plus the restart). 4 x
  1,000/1,000, 4 threads, `Init::best_of(16)` starts.
- **Blocks.**
  - L1: WP57 seeds 5701101–5701112, a targeted replication.
  - R: `eight_schools_centered`, `hmm_drive_0`, `arma11`, `garch11`,
    `gp_pois_regr` and `one_comp_mm_elim_abs`, seeds 6701301–6701303.
  - L2: fresh seeds 6701201–6701212.

  84 cells, strictly sequential, each run once. They ran 01:08–01:24 UTC on
  2026-10-26 with no errors or timeouts.
- **Machine.** Lane 4 of the shared c7a.4xlarge box, Ubuntu 24.04, under
  `taskset -c 12-15` with three other lanes active. **Walls are pinned,
  co-tenanted.** Gradients, ESS per gradient, hashes and passes are the
  evidence.
- **Build.** BridgeStan 2.9.0 libraries built in the lane, gcc 13.3.0, no
  `STAN_THREADS` (`artifacts/models.json`). posteriordb `28f8d3d` was read
  directly. ArviZ 0.23.4.
- **Gates.** These are CmdStan-free: rank R-hat <= 1.01, bulk and tail ESS
  >= 400, 0 divergences, finite draws. Lotka cells also need max |z| <= 4.
- **Trapped chain.** A chain more than 3 reference SD off on some parameter.

## Results

### Lotka

| block | defaults trapped | restart trapped | defaults passes | restart passes | defaults gradients | restart gradients |
|---|---|---|---|---|---|---|
| L1 (WP57 seeds) | 2/48 | 0/48 | 10/12 | 12/12 | 5,800,999 | 3,674,895 |
| L2 (fresh) | 0/48 | 0/48 | 11/12 | 11/12 | 3,403,075 | 3,403,075 |

L2's one gate failure is seed 6701212, R-hat 1.012 in both arms; the arms
are bit-identical there.

The two firing cells:

| seed | arm | wall (s) | gradients | per-chain gradients | flagged chain shift (ref SD) | min bulk ESS | R-hat |
|---|---|---|---|---|---|---|---|
| 5701103 | defaults | 350.1 | 2,083,742 | 74k / 72k / 70k / **1,867k** | 169.4 | 7 | 1.592 |
| 5701103 | restart | 37.0 | 452,827 | 74k / 72k / 70k / 70k (+167k abandoned, +20 start evals) | 0.06 | 861 | 1.003 |
| 5701106 | defaults | 87.4 | 846,873 | 76k / 72k / **630k** / 69k | 162.2 | 7 | 1.595 |
| 5701106 | restart | 14.8 | 351,684 | 76k / 72k / 74k (+61k abandoned, +20) / 69k | 0.07 | 963 | 1.004 |

- **5701103.** The flagged chain's step at transition 99 was 3.8e-5,
  against a median of 0.0165 (ratio 0.0023). At that point it sat at log
  density -481; its replacement start was at -292.
- **5701106.** Step 3.6e-4 against 0.0143 (ratio 0.025), log density -499;
  replacement start at -454.
- **Warnings.** `chain_warnings` named the trapped chain in both defaults
  cells. It was silent in both restart cells.
- **Cost.** The wait at the boundary is the trapped chain's first 100
  transitions: 167k and 61k gradients.

### Regression arm

Passes are 12/12 out of 18, and both arms are bit-identical on every cell.

| model | passes | note |
|---|---|---|
| `eight_schools_centered` | 0/3 | R-hat 1.03–1.13, the known centred funnel |
| `hmm_drive_0` | 3/3 | |
| `arma11` | 3/3 | |
| `garch11` | 3/3 | |
| `gp_pois_regr` | 2/3 | R-hat 1.0106 on 6701302 |
| `one_comp_mm_elim_abs` | 1/3 | |

- **The one wrong-chain cell.** `one_comp` 6701303: chain 2 is 8.3
  reference SD off, R-hat 1.042, min bulk ESS 88. The step rule does not see
  it: that chain's transition-99 ratio is 0.736. `chain_warnings` is also
  silent there.
- **What this shows.** The step rule detects a collapsed-step trap. It does
  not detect every wrong chain.

### Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | L1 defaults 1–3 trapped of 48 | 2 (the WP57 chains) | yes |
| P2 | L1 restart <= 1 trapped | 0 | yes |
| P3 | sensitivity 1, <= 1 false flag | 2 TP, 0 FN, 0 FP, 94 TN | yes |
| P4 | fingerprint on every pair | 42/42 | yes |
| P5 | 0 of 18 regression cells fire | 0/18; ratio 1.0000 | yes |
| P6 | fewer gradients pooled when a restart occurs | 7,077,970 vs 9,204,074 | yes |
| P7 | <= 1 restarted chain trapped again | 0 of 2 | yes |

My preregistered worry was too few events. With 2 trapped defaults chains
pooled, the efficacy clause E passed exactly at its event floor.

## Decision (frozen rule) and recommendation

| clause | condition | observed | holds |
|---|---|---|---|
| E | defaults >= 2 trapped pooled; restart <= floor(defaults/2) | 2 vs 0 | yes |
| F | P4 on every pair | 42/42 | yes |
| G | lotka passes restart >= defaults | 23 vs 21 | yes |
| R1 | regression passes restart >= defaults | 12 vs 12 | yes |
| R2 | geomean ESS/gradient ratio >= 0.95 | 1.0000 | yes |
| R3 | wrong-chain regression cells restart <= defaults | 1 vs 1 | yes |

**SUPPORTED → recommend a default-flip confirmation study, not a flip.**
That study should:
- run fresh seeds at a scale that yields more than two trap events (lotka
  traps about 1 in 24 chains: 2/48 on L1, 0/48 on L2);
- run a broad posteriordb panel, so that specificity is measured on more
  than 18 cells;
- include a forced second-mode case (`hmm_drive_0` many seeds, or the WP52
  two-mode target). There the restart *acts* on a chain that may be in a
  genuine mode, which this study never observed;
- report the wall cost of the boundary synchronisation;
- follow the house rule that any default flip needs a v7-style validation
  afterwards.

## Files

- `PREREGISTRATION.md`, `protocol.json`: frozen at `c4522b8b`.
- `src/bin/trap_cell.rs` (from WP57), `src/bin/pdb_cell.rs` (from v7),
  `run_study.py`, `analyze.py`, `prepare_models.py`. Every harness change is
  listed in the preregistration.
- `artifacts/cells/*.json`: 84 cells.
- `artifacts/summary.json`, `artifacts/results-table.md`.
- `artifacts/run-log.txt`, `artifacts/analyze-log.txt`,
  `artifacts/measured_on.json` (affinity 12–15), `artifacts/models.json`,
  `artifacts/smoke/`.
- `artifacts/wp67-cargo-test*.log`: library tests, default and `research`
  features.
- `artifacts/telemetry/`: the four firing-pair files are committed; the
  other 44 lotka files are hashed in `CHECKSUMS.sha256` but kept out of git.
  Draws are out of git.

## Reproduce (on the box, lane 4)

```
taskset -c 12-15 ~/venv/bin/python prepare_models.py <bridgestan-2.9.0-src>
taskset -c 12-15 cargo build --release -j4
taskset -c 12-15 ~/venv/bin/python run_study.py smoke
taskset -c 12-15 ~/venv/bin/python run_study.py run      # resumable; never reruns a written cell
taskset -c 12-15 ~/venv/bin/python run_study.py analyze
python checksums.py
```
