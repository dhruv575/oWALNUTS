# posteriordb v7 on Linux (WP64): the gates reproduce to within one cell, the draws do not, and the per-gradient headline is hostage to CmdStan's stuck chains

## Verdict

**The pass counts reproduce within one cell, but none of the draws are
bit-identical, so L1 (exact reproduction) fails.** The same commits, seeds,
models, gates and analysis that produced E26 and E28 on Windows were run on a
core-pinned Linux box. oWALNUTS passes:

- **44/51** house cells (Windows 43);
- **7/15** on the five hard posteriors (Windows 6);
- **41/48** on the extension seeds (Windows 40).

Not one of the 114 oWALNUTS cells, 3 funnel seeds or 175 comparable
competitor cells is bit-identical to Windows. In every oWALNUTS cell the 16-candidate start
search does match Windows to 1e-12 (114/114). The warmup step-size traces then
part company by warmup iteration 50 in 131 of 132 oWALNUTS cells (114 plus
18 dense), and by iteration 100 in the last one. Each
Linux cell is therefore a different realisation at the same seed. The
oWALNUTS cells that flip are `gp_pois_regr`, `one_comp` (four cells across the
two seed sets), `accel_gp` and `seeds_centered`. Each is a model where the
sampler sits close to a gate on Windows.

**CmdStan stays well behind oWALNUTS, and nutpie stays furthest behind.**
L2 held: every competitor count is within 3 of Windows.

- CmdStan: 33/51, 5/15 and 31/48 (Windows 34, 7, 30).
- nutpie: 27/51 and 5/15 (Windows 26, 3).

So the ordering in the record stands on a second platform.

**L3 fails, and its failure says more about CmdStan than about oWALNUTS.** The
six-seed pooled fixed-16 oWALNUTS/CmdStan ESS per gradient is **1.206** on
Linux. The Windows figure is 0.761, and the preregistered interval was
[0.740, 0.822]. One model drives the gap:

- On `hmm_drive_0`, CmdStan has a chain stuck in a second mode on **4 of 6**
  Linux seeds (min bulk ESS 7–20, R-hat 1.13–1.60). On Windows it had one on
  2 of 6.
- With 2 of 3 bad seeds in a set, the seed median is a stuck cell. The
  per-model ratio becomes 133, against 0.95 on Windows.
- Post hoc, without `hmm_drive_0` the Linux geomean is 0.862, against 0.749
  on Windows for the same 14 models.
- Also dropping `one_comp`, where CmdStan fails every cell on both platforms,
  gives 0.793 against 0.743.

This is the fragility WP62 warned about (a seed median cannot absorb
competitor stuck chains), now seen across platforms. **The 0.76x per-gradient
figure in the record should be cited as platform-and-seed-dependent, not as a
property of oWALNUTS.**

**On Linux, oWALNUTS's wall per gradient is below CmdStan's.** L4 is
unevaluable under v7's rule, because CmdStan `lotka_volterra` 560562 errored
again with the same ODE error as on Windows. Its value over the 15 complete
models is **0.942** (threshold 1.0; Windows 1.849). ESS per second against
CmdStan is 1.215 (Windows 0.398) and against nutpie 1.454 (Windows 1.226).
These walls are "pinned, co-tenanted" (see Platform).

| arm | house /51 Linux (Windows) | new five /15 | extension seeds /48 | bit-identical cells |
|---|---:|---:|---:|---:|
| **oWALNUTS** | **44 (43)** | **7 (6)** | **41 (40)** | 0 / 114 |
| CmdStan 2.39.0 | 33 (34) | 5 (7) | 31 (30) | 0 / 112 comparable |
| nutpie 0.16.8 | 27 (26) | 5 (3) | — | 0 / 63 comparable |

| prediction | registered | observed | held |
|---|---|---|---|
| L1 | oWALNUTS exactly 43 / 6 / 40 | 44 / 7 / 41 | **no** (every differing cell is non-identical; see the interpretation rule) |
| L2 | competitors within 3 of Windows | CmdStan -1, -2, +1; nutpie +1, +2 | **yes** |
| L3 | six-seed pooled ESS/gradient in [0.740, 0.822] | **1.206** (15 models) | **no** (CmdStan `hmm_drive_0` stuck chains) |
| L4 | fixed-16 wall/gradient vs CmdStan <= 1.0 | 0.942 on 15/16 | **unevaluable** (CmdStan `lotka_volterra` error); value below 1.0 |
| R1 | bit-identity (reported) | 0/114 oWALNUTS, 0/3 funnel | expectation partly wrong: we expected the funnel and some small models to be identical |

**Reading L1 under the frozen interpretation rule.** Every one of the 7
differing oWALNUTS cells is non-identical, so each difference is attributed to
platform floating point, not to a reproducibility defect. No bit-identical
cell changed its gate, because there are none. Read against E28's seed
variation (40/48 on both Windows seed sets), the Linux counts 44/51, 7/15 and
41/48 are one draw from the same sampler. They add one cell to each count.
The analysis stack is not implicated.

## v7's own statistics on Linux

| v7 prediction | Linux | Windows |
|---|---|---|
| P1 oWALNUTS >= 42/51 | 44, held | 43, held |
| P2 no passing reference cell with \|z\| > 4 | held; largest passing 3.98 (`one_comp` 560562) | held; 3.82 |
| P3 fixed-16 ESS/grad vs CmdStan >= 0.75 | 1.154 on 15/16, unevaluable | 0.708 on 15/16, unevaluable |
| P4 fixed-16 wall/grad vs CmdStan <= 1.0 | 0.942 on 15/16, unevaluable | 1.849 on 15/16, unevaluable |
| P5 oWALNUTS >= 6/15 on the new five | 7, held | 6, held |
| P6 `seeds_centered` 0/3, zero divergences | **1/3**, failed (560562 passes at bulk 504 / tail 522) | 0/3, held |
| P7 CmdStan >= 8/15 on the new five | 5, failed | 7, failed |
| P8 funnel \|z\| <= 2 every seed | +0.29, -0.53, +0.55, held | +1.69, -0.59, +0.84, held |
| release rule, primary / secondary | not met / not met | not met / not met |

The descriptive dense arm passes 18/18 again. It reaches 12.2x the diagonal
default's ESS per gradient (Windows 13.4x), with `diamonds` at 75x (Windows
67.5x) and a largest |z| of 2.46.

WP62's statistics on Linux:

| WP62 statistic | Linux | Windows |
|---|---:|---:|
| fixed-16 geomean, extension seeds | 1.276 (15) | 0.810 |
| fixed-16 geomean, v7 seeds | 1.154 (15) | 0.708 |
| fixed-16 geomean, pooled six | 1.206 | 0.761 |
| leave-one-seed-out interval | [1.159, 1.265] | [0.740, 0.822] |
| jackknife SE / seeds recommended (primary rule) | 0.090 / 78 | 0.071 / 49 |

- Gates, pooled /96: oWALNUTS **82** (Windows 80), CmdStan 62 (62).
- WP62's Q1 and Q2 fail on Linux. Q3 and Q4 hold.
- No passing oWALNUTS cell has |z| > 4. The largest on the extension seeds
  is 3.34.

## Where the realisations differ (oWALNUTS)

| posterior | Linux v7 seeds | Windows | Linux ext seeds | Windows |
|---|---:|---:|---:|---:|
| gp_pois_regr | 2/3 | 3/3 | 3/3 | 3/3 |
| one_comp_mm_elim_abs | 2/3 | 1/3 | 2/3 | 1/3 |
| accel_gp | 1/3 | 0/3 | 0/3 | 0/3 |
| seeds_centered | 1/3 | 0/3 | — | — |
| every other posterior | unchanged | | unchanged | |

These are the near-gate cells v7 and WP62 already named. `one_comp` fails on
tail ESS just under 400, `accel_gp` on R-hat about 1.01 with tail ESS in the
hundreds, `gp_pois_regr` 560561 on a single gate, and `seeds_centered` on
`sigma`. Nothing new fails. Some things that failed on Windows pass on
Linux. The `seeds_centered` pass breaks v7's P6 "0/3" claim. That claim
described one realisation, not the posterior, and the silent-funnel reading
should be stated as "fails on most seeds".

Some failure events reproduce exactly although the draws do not. CmdStan
`lotka_volterra` errors on the same two seeds as on Windows, with the same
messages: 560562 (`integrate_ode_rk45` max_num_steps) and 620602 (NaN
location). The nutpie `lotka_volterra` child crashes on 560561 again, so all
three of its cells are `timeout_or_crash`. These failures occur at or near
the start, before the trajectories have separated.

## Timings (Linux "pinned, co-tenanted"; Windows "contended")

| arm | Linux / Windows wall per gradient (geomean over models, seed medians) |
|---|---:|
| oWALNUTS (`ReplicatedConcurrent`, 4 replicas, vs `OwnedSerialised`) | **0.20** (house), 0.22 (new five), 0.23 (ext) |
| CmdStan | 0.39 (house), 0.53 (new five), 0.75 (ext) |
| nutpie | 0.16 (house), 0.17 (new five) |

- Summed sampler wall on the v7 seeds was 1,231 s on Linux against 4,731 s
  on Windows for oWALNUTS, 896 s against 1,833 s for CmdStan, and 530 s
  against 4,266 s for nutpie.
- The whole study (198 v7 cells, the funnel, 18 dense cells and 96
  extension cells) ran in 74 minutes, 00:56–02:10 UTC.
- The fixed-16 wall per gradient against CmdStan halves, from 1.85 to 0.94.
  This study cannot separate the end of the Windows owned-worker
  serialisation from the laptop's contention, which affected the arms
  unequally: nutpie's wall per gradient fell about 6x, CmdStan's about
  2.5x.
- None of these walls is a sampler property. They are the first record of
  oWALNUTS on its intended non-Windows BridgeStan path.

## Design

Preregistered at `44546ec0` before the first cell (`PREREGISTRATION.md`,
`protocol.json`).

- **Constants.** The measurement constants are read at run time from v7's and
  WP62's frozen protocols.
- **Harness.** The harness crate is byte-identical to v7's. It was built from
  clean sparse worktrees of `f097391c` (E26 cells) and `c5c60122` (E28
  cells). The drivers checked the source tree before every oWALNUTS cell.
- **Drivers.** The drivers are v7's and WP62's. The portability changes are
  A-P1–A-P9 in `AMENDMENTS.md`, and none touches a computed number.
- **Binaries.** All 66 were compiled on the box with v7's recipes. Nothing was
  copied from Windows.
- **Software.** Lane venv on Python 3.12.3 with cmdstanpy 1.3.0, nutpie
  0.16.8, bridgestan 2.9.0, ArviZ 0.23.4, numpy 2.4.6, scipy 1.17.1 and
  xarray 2026.9.0 (pandas 3.1.0 unpinned). CmdStan 2.39.0; posteriordb
  `28f8d3d` (verified); Rust 1.88.0 `x86_64-unknown-linux-gnu`; glibc 2.39;
  g++ 13.
- **Run order.** v7 Phase 1 (CmdStan, nutpie), Phase 2 (oWALNUTS, funnel,
  dense), then the extension (oWALNUTS then CmdStan per model). Strictly
  sequential, no reruns and no amendments after the freeze.
- **Platform.** AWS c7a.4xlarge (AMD EPYC 9R14, 16 dedicated cores), Ubuntu
  24.04. The study is lane 1 of four core-pinned lanes: every process ran
  under `taskset -c 0-3` with `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`.
  Three other studies ran on cores 4–15 and shared the L3 cache and memory
  bandwidth, so every wall here is "pinned, co-tenanted". Pass counts and ESS
  per gradient are not affected by co-tenancy.

## Deviations and anomalies

- None of the preregistered execution rules was broken. No cell was rerun,
  and no amendment was needed after the freeze.
- **Smoke test.** One smoke test ran before the freeze at non-evidence seed
  11 on `eight_schools_noncentered`, into a scratch directory, and is not
  committed. Following v7's lesson, the funnel binary was called directly,
  not through `checks`.
- **Expectation R1 was wrong.** We expected the funnel (pure Rust) and some
  low-dimensional models to be bit-identical, and none were. Even Rust's own
  `f64` math reaches the platform libm through `std`, and the sampler's
  random-number transforms call it too.
- **Executable bits.** The committed `.sh` files lack the executable bit,
  because the commit was made from Windows. They were run with `bash`.
- **Raw data.** Raw draws and CmdStan output stay on the box and are not
  committed. Cell metrics, summaries, tables, logs and manifests are
  committed and checksummed.

## Recommendation

Change no default. For the record:

- Add a Linux row to E26 and E28: oWALNUTS 44/51 + 7/15 and 41/48, CmdStan
  33 + 5 and 31, nutpie 27 + 5.
- Say that cross-platform draws are not bit-identical, so a gate count is
  reproducible only to within seed-level noise, about +/-1 cell here.
- **Stop quoting a single per-gradient ratio against CmdStan** without its
  platform and the competitor stuck-chain caveat. The same seeds give 0.76 on
  Windows and 1.21 on Linux, because CmdStan's `hmm_drive_0` second-mode
  chains move between seeds with libm.
- A robust statistic should be preregistered before any further per-gradient
  claim: for example per-model medians over many seeds, or models where both
  arms pass.
- Soften v7's P6 / silent-funnel wording to "fails on most seeds".
- Quote oWALNUTS walls from Linux, where the BridgeStan path is not
  serialised.

## Reproduce (on the box, lane 1)

```
L=~/lanes/posteriordb_bench_v7_linux_v1; S=$L/work/STUDIES/posteriordb_bench_v7_linux_v1
python3 -m venv $L/venv && $L/venv/bin/pip install cmdstanpy==1.3.0 nutpie==0.16.8 bridgestan==2.9.0 arviz==0.23.4 numpy==2.4.6 scipy==1.17.1 xarray==2026.9.0 posteriordb==0.2.0 pandas
# BridgeStan 2.9.0 source unpacked at $L/bridgestan-2.9.0; CmdStan 2.39.0 and posteriordb 28f8d3d under ~/infra
taskset -c 0-3 bash build_harness.sh f097391cd956246e3fbd5a6593622bc424b65f9e v7
taskset -c 0-3 bash build_harness.sh c5c6012287fb99bea3ee73dd1abe01e7369c5d6f ext
bash run_lane.sh prepare      # 66 binaries
bash run_lane.sh all          # phases A-D (A: v7 competitors, B: v7 oWALNUTS + funnel + dense, C: extension, D: analyses)
python -I checksums.py
```
