# reverse_coarser_policy_v2 (WP39B) — the untruncated orbit does not pay, with or without the step confound

Preregistered in `PREREGISTRATION.md` / `protocol.json`, frozen before the
first cell (commit `9cb1c02`). Seeds 92101–92103, 17 posteriordb posteriors,
4 arms, 4 chains x 1,000/1,000, `posteriordb_bench_v5` protocol; CmdStan
cited from v5. 204 cells and 6 funnel rows, all present, run in protocol
order without interruption, no reruns.

## Question

WP39 (`reverse_coarser_policy_v1`) found `ZeroWeightBeyond` exact but not
faster, and traced the comparison's confound to the dual-averaging
statistic: zero-weight leaves diluted the failed leaf's low acceptance
value and the step rose 3–30 %. This study asks two things: (a) does
`ZeroWeightBeyondAdaptSelected` (kernel `cfb1e93`; the same orbits with the
zero-weight tail withheld from the step statistic) pay under the shipped
adaptation, and (b) at an identical fixed step, does not truncating the
orbit pay, as WP34's reading predicted?

## Answer: no on both counts — **no default change**, and the truncation hypothesis is not supported

| statistic (seed medians of min bulk ESS per gradient) | value | rule |
|---|---:|---|
| `beyond-adapt` / `stop`, geomean over 17 models | **0.878** | C1 >= 1.10 fails |
| `beyond-adapt` / `stop`, geomean over the 4 targets | **0.703** | C5 >= 1.15 fails |
| `beyond-adapt` / `stop`, geomean over the 13 controls | 0.940 | |
| `beyond-adapt` / `stop`, geomean over the 14 CmdStan-healthy models | 0.949 | |
| worst model | 0.347 (centered eight schools); `accel_gp` 0.659 | C2 >= 0.90 fails |
| gates passed of 51, stop / beyond-adapt | 44 / 44 | C3 passes |
| funnel \|z\| <= 2 on every seed, beyond-adapt | yes (−0.28, +1.25, +0.10) | C4 passes |
| adapted-step ratio adapt/stop, geomean (max \|log\|) | 1.011 (0.153) | |
| `beyond-fixed` / `stop-fixed`, geomean over the 4 targets | **0.908** | M1 >= 1.15 fails |
| `beyond-fixed` / `stop-fixed`, geomean over the 13 controls | 0.885 | M2 within 1.05 fails |
| `stop-fixed` / `stop`, geomean | **0.397** | P3 (~1) falsified |
| gates of 51, stop-fixed / beyond-fixed | 35 / 42 | |

Per model (full tables in `artifacts/results-table.md`):

- **Adapted step.** Wins: noncentered eight schools **1.19x** (1.30x in
  WP39), `earnings` 1.07x, `hmm_drive_0` 1.05x. Losses: centered eight
  schools 0.35x, `accel_gp` 0.66x, `sblrc` 0.75x, `kidiq` 0.83x, `arK`
  0.90x, `gp_pois_regr` 0.90x (1.14x in WP39). Everything else within
  0.91–1.00.
- **Fixed step, paired.** The same picture: noncentered eight schools
  **1.21x**, `accel_gp` 0.72x, centered eight schools 0.83x, `gp_pois_regr`
  0.95x. The controls scatter from 0.37x (`hmm_drive_0`) to 1.40x
  (`kidiq`), mostly with fewer than three gates on one side, so they carry
  little weight.

## What the two designs say

**The step confound is gone on average and the result did not change.**
`AdaptSelected` brought the geomean step ratio from WP39's 1.13 to 1.011,
but P1's per-model band (0.95–1.05) still failed on five models
(`diamonds` 1.08, `accel_gp` 1.10, centered eight schools 0.86, `one_comp`
and `lotka_volterra` 0.94): the withheld leaves change which orbits the
statistic sees, not only the tail. With the step matched, the result got
*worse* than WP39, not better (0.878 against 0.981; targets 0.703 against
0.904), because the untruncated orbit at the same step still builds the
zero-weight tail (`accel_gp`: leaves per orbit 357 → 526, 39 % of built
leaves at zero weight; centered eight schools 12.6 → 20.3) and now no
longer gains the larger step's longer moves elsewhere.

**At an identical fixed step, not truncating the orbit pays only where the
failure region is small.** The paired fixed comparison reproduces the
adapted one on the four targets (noncentered eight schools 1.21x, the other
three below 1). Two independent designs agree, so the WP34 hypothesis that
the truncation is what costs the target models per gradient is not
supported: on three of the four, carrying the orbit past the failed leaf
costs more gradients than the truncation had.

**The fixed-step arms are a poor design and are reported as such.** P3
(fixing the step at the adapted value costs nothing) was falsified by a
factor of 2.5: with step adaptation off, warmup starts at the final small
step on an identity metric and spends 2–8x the gradients before the mass
windows settle (warmup counts in the statistic), and on `arma11` the fixed
step (0.67) with no initial step search never built a retained leaf at
all — every transition ended in refinement exhaustion on both fixed arms.
The fixed pair is still paired (same step, same seed, same warmup schedule),
so its per-model ratios are meaningful where both arms pass their gates,
but its geomeans over the controls are not, and M1/M2 are reported as
failing without further interpretation. A future fixed-step design should
fix the step only after warmup's step search and first mass window.

**Exactness held.** Funnel `|z| <= 2` on every seed for both arms;
`beyond-adapt` passed the same 44 of 51 gates as `stop` (one more on
`accel_gp`, one fewer on `one_comp`).

## What this settles

- `StopOrbit` stays the default. `ZeroWeightBeyond` and
  `ZeroWeightBeyondAdaptSelected` stay research-only.
- The reverse-coarsening-as-truncation line (WP34 → WP39 → WP39B) is
  closed: the gap to CmdStan on `accel_gp`, the centered eight schools and
  `gp_pois_regr` is not a truncation artefact. The remaining per-gradient
  gap on smooth models (`sblrc`, `kidiq`, `arK`, where reverse-coarser stops
  end about 1 % of transitions) has a different cause and is the next
  question.

## Layout

- `PREREGISTRATION.md`, `protocol.json`: the frozen design, predictions and rules.
- `src/main.rs`, `src/arms.rs`: the cell harness (v5 protocol + policy accounting; fixed-step arms via `Adaptation::Custom` with step adaptation off); `src/bin/funnel.rs`: the funnel row.
- `run_study.py`: driver (`run`, `cell`, `checks`, `analyze`); the fixed arms read the `stop` cell's median adapted step for the same model and seed; BridgeStan libraries and the posteriordb checkout reused from `posteriordb_bench_v6` in the `wt/posteriordb-v6` worktree.
- `artifacts/cells/` (204 cells, metrics without draws), `artifacts/funnel/` (6 rows), `artifacts/summary.json`, `artifacts/results-table.md`, `measured_on.json`. `artifacts/draws/` (constrained draws, raw harness output) is ignored and hashed in `CHECKSUMS.sha256`.
