# posteriordb v7 seed extension (WP62): the per-gradient headline is 0.76x CmdStan over six seeds, with a seed interval of about +/-0.04

## Verdict

**v7's 0.708 was a low draw.** On three new seeds, the fixed-16 oWALNUTS /
CmdStan min-bulk-ESS-per-gradient geomean is **0.810**. Pooled over v7's
seeds and these, it is **0.761**. Dropping one seed at a time gives a seed
interval of **[0.740, 0.822]** (width 0.082).

The pooled figure clears the v6/v7 threshold of 0.75. Its interval does not:
it straddles 0.75. A 3-seed headline can therefore land on either side of
that gate with no change in the sampler.

All four preregistered predictions held. Gates: **oWALNUTS 40/48 on the new
seeds and 80/96 pooled; CmdStan 30/48 and 62/96.** No passing oWALNUTS cell
has |z| > 4 (largest new: 3.19). Nothing is flipped.

| statistic | value | models |
|---|---:|---:|
| geomean, 3 new seeds (620601–620603) | **0.810** | 15 |
| geomean, v7's 3 seeds (recomputed) | 0.708 | 15 |
| geomean, all 6 seeds | **0.761** | 15 |
| leave-one-seed-out interval | **[0.740, 0.822]** | 15–16 |
| jackknife SE of the 6-seed geomean | 0.071 | — |
| recommended seeds for a +/-0.05 gate (primary rule) | **49** | — |

| prediction | registered | observed | held |
|---|---|---|---|
| Q1 | 3-new-seed geomean in [0.65, 0.95] | 0.810 | yes |
| Q2 | 6-seed geomean in [0.72, 0.85] | 0.761 | yes |
| Q3 | leave-one-seed-out range wider than 0.08 | 0.082 | yes (barely) |
| Q4 | oWALNUTS >= 40/48 on the new seeds | 40 | yes (at the threshold) |

## Design

The study was frozen at `6216078a` before the first cell (see
`PREREGISTRATION.md` and `protocol.json`). It ran at main **`c5c60122`**,
whose default sampler is that of v7's `f097391c`.

- **Arms.** `owalnuts` (the v7 harness and cell code, unchanged) and CmdStan
  2.39.0 at defaults.
- **Models.** The fixed 16.
- **Runs.** 4 x 1,000/1,000 with 4 threads, seeds 620601–620603, run 08:49
  to 09:34 local in model / arm / seed order. 96 cells, no reruns.
- **Pooled analysis.** v7's 96 fixed-16 cells are read unchanged.
- **Walls.** Contended, though the machine was quieter than during v7.

## Per model (oWALNUTS / CmdStan ESS per gradient, seed medians)

| model | new 3 | v7 3 | pooled 6 | new gates oWALNUTS / CmdStan |
|---|---:|---:|---:|---|
| eight_schools_noncentered | 0.883 | 1.025 | 0.891 | 3/3 / 0/3 |
| eight_schools_centered | 0.486 | 0.182 | 0.304 | 0/3 / 0/3 |
| diamonds | 0.846 | 0.882 | 0.870 | 3/3 / 3/3 |
| earnings | 0.747 | 0.775 | 0.761 | 3/3 / 3/3 |
| mesquite | 0.884 | 0.957 | 0.939 | 3/3 / 3/3 |
| kidiq | 0.901 | 0.884 | 0.901 | 3/3 / 3/3 |
| sblrc | 0.839 | 0.809 | 0.824 | 3/3 / 3/3 |
| nes2000 | 0.849 | 0.870 | 0.867 | 3/3 / 3/3 |
| arK | 0.845 | 0.845 | 0.845 | 3/3 / 3/3 |
| garch11 | 0.898 | 0.957 | 0.908 | 3/3 / 3/3 |
| gp_pois_regr | 0.750 | 0.820 | 0.788 | 3/3 / 0/3 |
| hmm_example | 0.871 | 0.965 | 0.919 | 3/3 / 3/3 |
| hmm_drive_0 | 0.984 | 0.661 | 0.952 | 3/3 / 2/3 |
| one_comp | **1.630** | 0.504 | 0.843 | 1/3 / 0/3 |
| lotka_volterra | — | — | — | 3/3 / 1/3 (+1 error) |
| accel_gp | 0.345 | 0.347 | 0.346 | 0/3 / 0/3 |

Twelve models move by less than 0.1 between seed sets. Three account for the
v7-to-new swing: `one_comp` (0.50 -> 1.63), `hmm_drive_0` (0.66 -> 0.98) and
centered Eight Schools (0.18 -> 0.49). These are the models whose CmdStan or
oWALNUTS cells contain a stuck or slow chain on some seeds. `accel_gp` sits at
0.35 on both seed sets, so it is a stable per-gradient gap, not seed noise.

`lotka_volterra` is out of every 3-seed and 6-seed geomean. CmdStan errored
there again (seed 620602, a NaN ODE state). With one error in each seed set,
CmdStan has only 4 of 6 ok cells.

## The seed interval, read carefully

- The leave-one-seed-out values are 0.800, 0.822, 0.817, 0.750, 0.769 and
  0.740, dropping 560561 through 620603 in order. Dropping either of the two
  CmdStan `lotka_volterra` error seeds lets `lotka_volterra` (ratio about 2)
  back in at 4 of 5 ok cells. That composition change lifts those two values.
- Post hoc, holding the model set at the 15, the interval is [0.720, 0.817]
  (width 0.097). This was computed after seeing the results, is
  descriptive, and does not count.
- **Seed count (primary, frozen rule).** The jackknife SE of the 6-seed
  geomean is 0.071. The rule n = 6 (2 SE / 0.05)^2 gives **49 seeds** for a
  +/-0.05 interval around a 0.75 gate. A jackknife of medians is known to
  overstate SE, so 49 is an upper bound, not a target.
- **Seed count (reported only).** The single-seed SD method gives 154. One
  seed's median cannot absorb competitor stuck chains (single-seed geomeans
  range from 0.77 to 1.67), which is why it is not primary.

## Recommendation

- **Do not use a 3-seed per-gradient geomean as a hard release gate at 0.75.**
  Six seeds put the estimate at 0.76, with a leave-one-out spread of about
  +/-0.04, and the frozen rule says reaching +/-0.05 confidence needs on the
  order of tens of seeds.
- For future breadth headlines, report the per-gradient geomean with its
  leave-one-seed-out interval over at least 6 seeds. Gate on gates and z,
  which are stable: 40/48 on both seed sets.
- If a per-gradient gate is kept, use a seed-robust statistic, such as
  per-model medians over many seeds, or drop models whose competitor arm
  errors.
- No default change.

Raw draws and CmdStan output are uncommitted and checksummed in
`CHECKSUMS.sha256`.
