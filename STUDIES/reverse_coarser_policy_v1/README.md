# reverse_coarser_policy_v1 (WP39) — continuing the orbit past a failed reverse check does not pay under the shipped adaptation

Preregistered in `PREREGISTRATION.md` / `protocol.json`, frozen before the
first cell (commit `877ca26`; a harness build fix followed in the next
commit without touching the protocol). Seeds 91101–91103, 17 posteriordb
posteriors, 2 arms, 4 chains x 1,000/1,000, `posteriordb_bench_v5` protocol;
CmdStan cited from v5. 102 cells and 6 funnel rows, all present, no reruns.

## Question

WP34 found that the four posteriordb models where oWALNUTS is furthest
behind CmdStan per gradient are those where the reverse-coarsening check
ends the most transitions (10–54 %), while the check's own gradient cost is
negligible. The kernel's research-only `ReverseCoarserPolicy::ZeroWeightBeyond`
(commit `e5a6617`) keeps a failed leaf's endpoint and everything beyond it
at zero weight and lets the orbit run on to its U-turn, which is exact
(`tests/reverse_coarser_policy.rs`). Does it pay per gradient, and is it
exact on the funnel?

## Answer: exact, but not faster — **no default change**

| statistic (`beyond` / `stop`, seed medians of min bulk ESS per gradient) | value | rule |
|---|---:|---|
| geomean over 17 models | **0.981** | C1 >= 1.10 fails |
| geomean over the 4 target models | **0.904** | C5 >= 1.15 fails |
| geomean over the 13 controls | 1.005 | |
| geomean over the 14 CmdStan-healthy models | 1.030 | |
| worst model | 0.612 (`accel_gp`) | C2 >= 0.90 fails |
| gates passed of 51, stop / beyond | 41 / 42 | C3 passes |
| funnel \|z\| <= 2 on every seed, beyond | yes (+1.25, −0.82, −0.57) | C4 passes |
| vs CmdStan on the healthy models, stop / beyond | 0.783 / 0.807 | |

Per model (full table in `artifacts/results-table.md`):

- **Wins where the stop was frequent and orbits short**: noncentered eight
  schools 1.30x (stop fraction 11 %), `lotka_volterra` 1.30x (5.5 %),
  `gp_pois_regr` 1.14x (18 %), `earnings` 1.10x, `kidiq` 1.10x.
- **Losses**: `accel_gp` **0.61x** (stop fraction 58 %), centered eight
  schools 0.74x (26 %), `nes2000` 0.79x, `sblrc` 0.81x, `garch11` 0.91x,
  `mesquite` 0.92x.

## Why: the policy moved the step, and the zero-weight tail is paid for in gradients

**P1 was falsified.** The adapted step rose under `beyond` on 16 of 17
models, by 3–30 % (geomean 1.13x; `accel_gp` 1.30x, `diamonds` 1.24x,
`nes2000` 1.24x, `mesquite` 1.21x, `earnings` 1.20x). The mechanism is in
the shipped dual-averaging statistic: `CurrentCoarseEndpoint` averages
`exp(-|dH|)` of every built leaf's coarsest attempt over the transition,
and a zero-weight leaf is a built leaf. Under `StopOrbit` a failed leaf is
the last leaf of a short orbit and its low value carries weight; under
`ZeroWeightBeyond` the orbit continues past it and dilutes it with ordinary
leaves. Dual averaging sees a higher statistic at the same `h` and installs
a larger `h`. The larger step then makes more leaves refine (the refined
fraction rose 2–25x, e.g. `gp_pois_regr` 0.16 % → 3.5 %, `accel_gp` 0.36 %
→ 7.3 %) and more of them fail the check (continued leaves are 1.3–26x the
`stop` arm's rejections), which under `beyond` are then paid for as
zero-weight leaves: 4–19 % of built leaves on most models and **57 % on
`accel_gp`**, where leaves per orbit went from 321 to 507 and mean depth
from 7.6 to 9.0.

So the experiment did not measure "the same orbits, not truncated"; it
measured "a larger step whose extra failures are carried at zero weight".
Where the stop fraction was moderate and orbits short (the noncentered
eight schools, `lotka_volterra`, `gp_pois_regr`) the untruncated orbit won
anyway; where the failure region is large (`accel_gp`, centered eight
schools) the zero-weight tail cost more gradients than the truncation had.

**Exactness held.** Funnel `|z| <= 2` on every seed for both arms; `beyond`
passed one more gate than `stop` (42/51 vs 41/51); max rank R-hat and `|z|`
against the reference are in the same range for both arms on the healthy
models.

## What this settles and what it does not

- `ZeroWeightBeyond` stays research-only; `StopOrbit` stays the default.
- The truncation hypothesis from WP34 is neither confirmed nor refuted:
  the paired comparison was confounded by the adaptation statistic. The
  clean follow-up is a preregistered arm in which the dual-averaging mean is
  taken over positive-weight leaves only (the failed leaf included, as under
  `StopOrbit`), so that both arms adapt to the same `h`, or a fixed-step
  paired design at the `stop` arm's adapted `h`. WP34's `delta = 2` result
  (1.07x with `accel_gp` at 0.68x) and this study's `accel_gp` 0.61x both
  say that model's difficulty is not a truncation artefact.

## Layout

- `PREREGISTRATION.md`, `protocol.json`: the frozen design, predictions and rule.
- `src/main.rs`, `src/arms.rs`: the cell harness (v5 protocol + policy accounting); `src/bin/funnel.rs`: the funnel row.
- `run_study.py`: driver (`run`, `cell`, `checks`, `analyze`); BridgeStan libraries and the posteriordb checkout reused from `posteriordb_bench_v6` in the `wt/posteriordb-v6` worktree.
- `artifacts/cells/` (102 cells, metrics without draws), `artifacts/funnel/` (6 rows), `artifacts/summary.json`, `artifacts/results-table.md`, run logs, `measured_on.json`. `artifacts/draws/` (constrained draws, raw harness output) is ignored and hashed in `CHECKSUMS.sha256`.
- Run note: the driver was killed once by the host after 93 cells (system memory pressure, not a sampler error) and resumed; the resumable driver skips existing cells, so no cell ran twice. The `lotka_volterra` `stop` 91101 wall (985 s against ~30 s for its siblings) is that pressure and is excluded from nothing: the per-gradient statistic does not use walls.
