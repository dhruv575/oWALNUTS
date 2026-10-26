# WP69: confirmation of the trapped-chain restart (`trapped_chain_restart_confirmation_v1`)

## Verdict

**DO NOT PROPOSE the default.** The frozen rule fails on (a) and (b); (c),
(d) and the fingerprint hold. The restart stays a research-only opt-in, and
`ALGORITHM_REVISION` is not bumped.

- **(a) Efficacy: fails.** Over 60 fresh `lotka_volterra` seeds x 4
  chains, **0 of 240 chains were trapped at the defaults**, and 0 with the
  restart, so there was nothing to remove. The detector fired twice
  (6901025 chain 0 and 6901036 chain 1), with step ratios 0.024 and 0.027.
  Both chains were at log density about -330 and -500 at transition 99, but
  at the defaults both escaped later and ended on the reference (shifts 0.10
  and 0.07 SD). **By the frozen definition both flags are false positives.**
  The restarts were not harmful: both cells passed in both arms, at 0.83x
  and 0.85x of the defaults' gradients.
- **(b) Breadth: fails on its false-positive clause.**
  - Over 17 models x 3 seeds, passes were 42 = 42 of 51 and the geomean
    ESS/gradient ratio was 1.0007 (>= 0.99). All 50 unflagged cells are
    bit-identical.
  - **One flag fell on a cell that passes at the defaults:** `earnings`
    6902001 chain 1, step ratio 0.031, shift 0.04 SD. It is a healthy chain
    with a transiently small step. The rule tolerates zero.
  - **The detector also missed a real trap:** `lotka_volterra` 6902003
    chain 2 is 88 SD off (R-hat 1.149) with a step ratio of **0.111**, just
    above the 0.1 threshold.
- **(c) Genuine second modes: holds (0 firings in 24 cells).**
  - **`hmm_drive_0`:** the targeted seeds 952202, 600602 and 600605 did not
    reproduce their second mode on this build. Fresh seed 6903102 did
    (chain 2, R-hat 1.022); the step rule stayed silent (min ratio 0.919)
    and `chain_warnings` named the chain.
  - **The two-mode target:** 5 of 6 cells had chains ending in both modes
    (R-hat 1.50–1.73). None fired.
  - **The warning half of the prediction failed, as I expected:**
    `chain_warnings` was non-empty on only 2 of the 5 mixed cells (the
    1-chain-minority splits) and silent on the three 2-2 splits. R-hat
    reported all 12 second-mode cells.
- **(d) Synchronisation cost: holds.** Median overhead was +0.10 % at 1
  chain (the path is not entered there), **+1.15 % at 4 chains** and
  **+1.86 % at 16 chains** (repeats ranged up to +5.1 %), against the 2 %
  limit. The cost is real and consistent at 4 chains. On the 50 non-firing
  breadth cells the median wall ratio was 1.018 (pinned, co-tenanted).
- **Fingerprint: 123/123 pairs, and 15/15 sync cells identical.**

**Reading.** At the end of S1 the step rule separates "currently slow"
from "healthy", not "trapped" from "healthy":
- WP67's two hits were true traps, and here 2 of 2 lotka flags were chains
  that would have recovered on their own;
- the one true trap in this study sat at 0.111 and was missed.

The restart is cheap and did no harm here: no gate was lost, the
ESS/gradient ratio was 1.0007, and no flag fired on a genuine mode. But
under a zero-false-positive rule it is not a default candidate. The lotka
trap rate at the defaults is also lower than WP57/WP67 suggested:
- 1 trapped chain in 252 on fresh seeds across this study (0 of 240 in A,
  plus the one in B);
- against 2 of 48 on the targeted WP57 seeds.

## Design (frozen at `38ae95df` before the first cell)

- **Unchanged from WP67** (library `8887a0f0`, nothing re-tuned):
  - **Detector:** flag chain c iff its step at transition 99 is below
    0.1 x the median over chains.
  - **Restart:** from transition 0, from the best of 16 fresh independent
    candidates, with a fresh RNG stream.
- **Arms:** `defaults` and `restart`. Starts are `Init::best_of(16)`; runs
  are 4 x 1,000/1,000 on 4 threads.
- **Blocks:**
  - **C:** `hmm_drive_0` on 952202, 600602 and 600605 (targeted), plus
    6903101–6903103.
  - **M:** the WP52 two-mode target on 6903201–6903206.
  - **D:** a 100-D Gaussian at 1, 4 and 16 chains, 5 repeats each. Each
    repeat runs 7 interleaved pairs; its ratio is the median restart wall
    over the median defaults wall.
  - **A:** `lotka_volterra` on 6901001–6901060.
  - **B:** the 17 house models x 6902001–6902003.
- **Scale and timing:** 261 cells, each run once, 01:43–02:16 UTC
  2026-10-26, with no errors or timeouts.
- **Machine:** lane 4 of the shared box, under `taskset -c 12-15` with
  other lanes active, so walls are pinned and co-tenanted. Arm D is read
  only as a ratio.
- **Gates:** v7 (rank R-hat <= 1.01, bulk and tail ESS >= 400, 0
  divergences); arm A also needs |z| <= 4.
- **Definitions:** trapped / second-mode chain = more than 3 reference SD
  off; false positive = a flag on a chain that is not trapped at the
  defaults (A), or any flag on a cell passing at the defaults (B).

## Results

| arm | rule | observed | holds |
|---|---|---|---|
| (a) | restart trapped < defaults trapped, 0 false positives | 0 vs 0 of 240; 2 false positives | **no** |
| (b) | passes r >= d, geomean >= 0.99, unflagged bit-identical, 0 FP on passing cells | 42 = 42; 1.0007; 50/50; **1 FP** | **no** |
| (c) | 0 firings (24 cells) | 0 | yes |
| (d) | overhead < 2 % at 4 and 16 chains | +1.15 %, +1.86 % | yes |
| — | fingerprint everywhere | 123/123 pairs, 15/15 sync cells | yes |

### Arm A: lotka, 60 fresh seeds

| seed | flagged chain (ratio) | chain log density at t = 99 | defaults chain gradients | restart: new run + abandoned | cell gradients d / r | wall d / r (s) | passed d / r |
|---|---|---|---|---|---|---|---|
| 6901025 | 0 (0.024) | -332 | 170,669 (others 63k–70k) | 65,114 + abandoned | 371,842 / 310,062 | 14.6 / 8.9 | yes / yes |
| 6901036 | 1 (0.027) | -498 | 268,609 (others 69k–85k) | 73,427 + abandoned | 493,733 / 418,977 | 37.1 / 25.2 | yes / yes |

- Gates passed on 55 = 55 of 60 cells. The 5 failures are R-hat
  1.010–1.063, identical in both arms.
- Totals: 17.36M vs 17.22M gradients, and 422 vs 414 s of wall.

### Arm B: 17 house models

- **Detector.** It fired on 1 of 204 chains. The lowest unflagged ratios
  were 0.111 (the missed `lotka_volterra` trap), 0.119 and 0.140
  (`earnings`), and 0.143 (`accel_gp`).
- **`earnings` sits near the threshold** on all three seeds (0.031, 0.119,
  0.140): its transient warmup step dips are what the S1 rule sees.
- The per-model ESS/gradient ratio is 1.0000 everywhere except `earnings`
  (1.0128).

### Arm C: second modes

`chain_warnings` reported the second mode on:
- the `hmm_drive_0` second-mode cell, in both arms: 1/1;
- two-mode cells with a single minority chain (1-3 split): 2/2;
- two-mode cells split two-and-two: **0/3**.

R-hat > 1.01 reported 12 of 12 second-mode cells.

### Arm D: synchronisation point, 100-D Gaussian

| chains | repeat ratios | median overhead |
|---|---|---|
| 1 | 0.9995, 1.0016, 1.0025, 1.0009, 1.0010 | +0.10 % |
| 4 | 1.0106, 1.0118, 1.0115, 1.0149, 1.0048 | +1.15 % |
| 16 | 1.0186, 1.0237, 1.0049, 1.0509, 1.0042 | +1.86 % |

A 4-chain run takes about 38 ms, so the overhead is a fixed per-run cost
of about 0.4 ms. It is smaller as a fraction on real models.

### Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | A: defaults 4–16 trapped of 240, restart <= 1 | 0 and 0 | no |
| P2 | A: sensitivity 1, 0 false positives | no traps; 2 FP | no |
| P3 | B: fires only on lotka, 0 FP, ratio >= 1.00 | fired on `earnings`; missed a lotka trap | no |
| P4 | C: 0 firings; warning reports every second mode | 0 firings; warning 6/12 cell-arms (3/6 distinct cells) | no (warning half; my recorded expectation held) |
| P5 | D: < 2 % at 4 and 16 | +1.15 %, +1.86 % | yes |
| P6 | fingerprint | 123/123, 15/15 | yes |

## What follows

- **The restart stays research-only.** The S1 step rule is not specific
  enough for a zero-false-positive default:
  - 3 of 5 flags across WP67 + WP69 fell on chains that would have
    recovered or were healthy;
  - it misses traps whose step ratio is just above 0.1 (0.111 here, 0.114
    for WP44's lotka chain).
- **Don't fix this by moving the threshold** without a new preregistration.
  The miss at 0.111 and the false flags at 0.024–0.031 overlap with any
  single cut.
- **Untested idea:** a two-signal rule. Combine the step ratio with a
  later-window confirmation, e.g. the chain is still slow and low-density
  at the end of S2. That trades WP36's two-hit lesson against latency.
- The lotka trap rate on fresh seeds is about 0.4 % of chains, not WP57's
  4 %.

## Files

- `PREREGISTRATION.md` and `protocol.json` were frozen at `38ae95df`.
- Code: `src/bin/{trap_cell,pdb_cell,two_mode,sync_cost}.rs`, `run_study.py`,
  `analyze.py`, `prepare_models.py`.
- Results: `artifacts/cells/` (261 cells), `artifacts/summary.json`,
  `artifacts/results-table.md`.
- Logs and provenance: `artifacts/run-log.txt`, `artifacts/analyze-log.txt`,
  `artifacts/measured_on.json`, `artifacts/models.json`, `artifacts/smoke/`.
- Telemetry: the two firing lotka pairs are committed in
  `artifacts/telemetry/`. The other files there are hashed in
  `CHECKSUMS.sha256` and kept out of git.
- Draws are out of git.

## Reproduce (on the box, lane 4)

```
taskset -c 12-15 ~/venv/bin/python prepare_models.py <bridgestan-2.9.0-src>
taskset -c 12-15 cargo build --release -j4
taskset -c 12-15 ~/venv/bin/python run_study.py run
taskset -c 12-15 ~/venv/bin/python run_study.py analyze
python checksums.py
```
