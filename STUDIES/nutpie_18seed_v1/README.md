# nutpie 18-seed (WP76): oWALNUTS passes the most gates by a wide margin, but nutpie gets 1.43x its ESS per gradient, and per second the two are close (0.93x)

## Verdict

**oWALNUTS is the most reliable of the three samplers.** It passes the most
gates over the fixed 16 x 18 Linux seeds: **239/288**, against CmdStan's 198
and nutpie's 163.

**It is not the most efficient when the others work.** Per gradient,
statistic (c) puts it at **0.70x nutpie** and 0.83x CmdStan. Per second
(pinned, co-tenanted) it is **0.93x nutpie** and 0.89x CmdStan, and both
per-second intervals reach 1.

Same seeds, same lane, v7 gates. The oWALNUTS and CmdStan cells are WP64's
and WP72's, reused unchanged. nutpie was run here on all 18 seeds.

| sampler | gates /288 | oWALNUTS / sampler, ESS per gradient (c) | oWALNUTS / sampler, ESS per second (c) |
|---|---:|---|---|
| **oWALNUTS** (defaults, `c5c60122` / `f097391c`) | **239** | — | — |
| CmdStan 2.39.0 | 198 | 0.826 [0.789, 0.931] (16 models) | 0.886 [0.846, 1.000] (16) |
| nutpie 0.16.8 | 163 | **0.699 [0.650, 0.962]** (15) | **0.932 [0.865, 1.275]** (15) |

Intervals are 95 % seed-bootstrap intervals (10,000 resamples, rng seed 76).
The oWALNUTS/CmdStan per-gradient interval differs slightly from WP72's
[0.789, 0.935] because the bootstrap rng seed differs; the point value is
identical. Also reported: nutpie / CmdStan is 1.174 [1.094, 1.287] per
gradient and 0.949 [0.887, 1.050] per second.

| prediction | registered | observed | held |
|---|---|---|---|
| N1 | per-gradient (c) oWALNUTS / nutpie in [1.0, 1.4] (coordinator) | 0.699 | **no**, as we expected before running |
| N1b | the same in [0.55, 0.95] (this study) | 0.699 | **yes** |
| N2 | per-second (c) oWALNUTS / nutpie in [1.2, 1.8] | 0.932 | **no** |
| N3 | nutpie gates < 239 | 163 | **yes** |

- **N1, either way round.** The alternative reading of N1 (nutpie /
  oWALNUTS in [1.0, 1.4], i.e. oWALNUTS / nutpie in [0.714, 1.0]) also
  misses, narrowly: 0.699.
- **Why N1 was always unlikely.** WP58 found nutpie ahead per gradient
  (1.70x on three PyMC models). Here the lead is 1.43x (1 / 0.699) on
  posteriordb.
- **N2 failed.** The 1.45 it was based on was WP64's three-seed v7 statistic
  (a). That statistic includes models where nutpie fails, and three seeds
  is too few. The same-seed median over 18 seeds is 0.93.

## Where nutpie fails and where it leads

| posterior | oWALNUTS | CmdStan | nutpie | (c) per gradient | (c) per second |
|---|---:|---:|---:|---:|---:|
| eight_schools_noncentered | 18 | 10 | **2** | 0.76 | 1.49 |
| eight_schools_centered | 0 | 0 | 0 | 0.61 | 0.82 |
| diamonds | 18 | 18 | **2** | 1.04 | 1.02 |
| earnings | 18 | 18 | 16 | 0.69 | 0.84 |
| mesquite | 18 | 18 | 18 | 0.84 | 1.19 |
| kidiq | 18 | 18 | 17 | 0.73 | 0.96 |
| sblrc | 17 | 18 | 18 | **0.34** | 0.66 |
| nes2000 | 18 | 18 | 18 | 0.73 | 1.05 |
| arK | 18 | 18 | 18 | 0.73 | 1.17 |
| garch11 | 18 | 18 | 18 | 0.75 | 1.17 |
| gp_pois_regr | **14** | 0 | 0 | 0.74 | 0.78 |
| hmm_example | 18 | 18 | 18 | 0.63 | 0.78 |
| hmm_drive_0 | 17 | 13 | **11** | 0.48 | 0.58 |
| one_comp | **10** | 0 | 0 | 1.21 | 1.25 |
| lotka_volterra | 17 | 13 | **7** (7 crashes) | — (11/18 ok) | — |
| accel_gp | 2 | 0 | 0 | 0.61 | 0.70 |

- **nutpie's gate losses are on four models.** Divergences fail
  non-centered Eight Schools (2/18). `diamonds` fails at 2/18. On
  `lotka_volterra`, 7 cells crash and 4 more fail. On `hmm_drive_0`, 6 of
  18 cells have a stuck chain.
- **Per gradient, nutpie leads on 13 of the 15 models.** The two
  exceptions are `diamonds` (1.04) and `one_comp` (1.21), where nutpie fails
  nearly all or all of its cells. The largest lead is `sblrc`, at 2.9x. This
  is the WP58 mass-matrix and warmup advantage.
- **oWALNUTS's per-second deficit is smaller than its per-gradient one.**
  It wins per second on 7 of 15 models.
- **Stuck chains on `hmm_drive_0`** (WP72 rule, 5 reference sd): oWALNUTS
  1/18, CmdStan 5/18, **nutpie 6/18**. So all three samplers can fall into
  the second mode. oWALNUTS does so least often, and its one case is named by
  `chain_warnings`.
- **The `lotka_volterra` crash is per seed.** With one child process per
  seed (amendment N-2), nutpie crashes on 7 of 18 seeds ("Failed to
  constrain"), not on every seed after the first. WP64's 560562, which
  never ran there, passes here.

## Same-seed repeatability

nutpie at 560561–560563 repeats WP64's Linux cells bit-identically on all 45
cells that completed both times: equal gradients and equal means. The three
differences are all `lotka_volterra`. 560561 and 560563 crash again. 560562
runs here and passes, where WP64 recorded it as a crash without ever running
it. The same build on the same box is fully deterministic. The Windows/Linux
differences in WP64 are platform floating point.

## Design and deviations

Preregistered at `c7e39bb2` before the first cell.

- **Runs.** 288 nutpie cells: the fixed 16 x 18 seeds (560561–3, 620601–3,
  720701–12). nutpie ran at defaults, 4 x 1,000/1,000, with v7's nutpie cell
  code and gates.
- **Execution.** One child per (model, seed). Ran 03:37–04:27 UTC on lane 1
  (`taskset -c 0-3`), with no reruns.
- **Binaries.** nutpie libraries from WP64's Linux build, with their TBB
  runtime copied into the lane.
- **Reused cells.** oWALNUTS and CmdStan: WP64's six seeds and WP72's twelve.
- **Analysis.** Run on the box.
- **Smoke test.** Before the freeze, non-evidence seed 11 ran through the
  whole `run` loop in smoke mode, into scratch output. This was by mistake
  rather than design, and is recorded in `PREREGISTRATION.md`. No evidence
  seed was touched.
- **Per-second caveat.** The walls come from different runs on the same lane
  (WP64/WP72 for oWALNUTS and CmdStan, this study for nutpie). Each is
  pinned, co-tenanted. The oWALNUTS wall excludes its start search.
- **Raw data.** Raw draws are checksummed and not committed.

## Recommendation

- **The three-sampler headline:** oWALNUTS 239/288 gates, CmdStan 198,
  nutpie 163. Per gradient, oWALNUTS is 0.83x CmdStan and 0.70x nutpie. Per
  second (Linux, pinned) it is 0.89x CmdStan and 0.93x nutpie.
- **Claim reliability, not speed.** The per-gradient gap to nutpie is the
  WP58 mass-matrix and warmup gap, and the remaining efficiency target.
- No default change.
