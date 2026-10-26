# posteriordb v7 on Linux (WP64): preregistration

Frozen before the first evidence cell. The machine-readable form is
`protocol.json`. The measurement constants are not restated there: the
drivers read them at run time from the two frozen protocols this study
reproduces, `STUDIES/posteriordb_bench_v7/protocol.json` (E26, WP56) and
`STUDIES/posteriordb_bench_v7_seed_extension/protocol.json` (E28, WP62).

## Question

Every posteriordb result in the record so far ran on one contended Windows
laptop. There, oWALNUTS reaches BridgeStan through the serialised owned worker,
so its walls measure that worker as much as the sampler. This study asks:

1. Do E26 and E28 reproduce on Linux with the same commits, seeds, models,
   gates and analysis?
2. What are the Linux timings, with oWALNUTS dispatching to four BridgeStan
   replicas and every arm pinned to four dedicated cores?

## What is reproduced, verbatim

- **E26 (posteriordb v7, WP56).** 22 posteriors (the 17 house models plus
  WP46's five), three arms (oWALNUTS defaults, CmdStan 2.39.0 and nutpie
  0.16.8 at defaults), seeds 560561–560563. 4 chains x 1,000 warmup / 1,000
  retained, four threads. ArviZ 0.23.4 gates: rank R-hat <= 1.01, bulk and
  tail ESS >= 400, zero retained divergences, finite draws, no error.
  Reference-mean z on the 18 reference posteriors. 2,700 s cell timeout. Then
  the funnel row (seeds 560571–560573, 4 x 2,000 / 20,000) and the
  descriptive `owalnuts-dense` arm on the six WP48 regressions. The commit is
  **`f097391c`**, v7's AMENDMENT-1 commit.
- **E28 (v7 seed extension, WP62).** The fixed 16 models, oWALNUTS and
  CmdStan only, seeds 620601–620603, the same gates. The commit is
  **`c5c60122`**, WP62's commit. Its pooled six-seed analysis, leave-one-seed-out
  interval, jackknife and Q1–Q4 are recomputed over this study's own Linux
  cells (Linux v7 seeds plus Linux extension seeds).
- **Order.** E26 Phase 1 (CmdStan, then nutpie, per model), E26 Phase 2
  (oWALNUTS, funnel, dense), then E28 (per model, oWALNUTS then CmdStan),
  then the analyses. Strictly sequential within the lane.
- **Code.** The harness crate (`Cargo.toml`, `Cargo.lock`, `src/main.rs`,
  `src/bin/funnel.rs`) is byte-identical to v7's. It is built once per
  commit from a clean git worktree of that commit. The drivers are v7's
  `run_posteriordb.py` and WP62's `run_extension.py`. Their measurement code
  (cell metrics, arms, gates, statistics, analysis) is unchanged. The
  portability changes are listed in `AMENDMENTS.md` (A-P1 to A-P9). None of
  them touches a computed number.

## Platform

AWS EC2 c7a.4xlarge (16 dedicated AMD EPYC Zen 4 cores, no SMT, 32 GB),
Ubuntu 24.04, Rust 1.88.0 `x86_64-unknown-linux-gnu`, and a lane venv on
Python 3.12 pinned to the Windows record's versions (cmdstanpy 1.3.0, nutpie
0.16.8, bridgestan 2.9.0, ArviZ 0.23.4, numpy 2.4.6, scipy 1.17.1, xarray
2026.9.0, posteriordb 0.2.0). CmdStan 2.39.0 and posteriordb `28f8d3d` come
from the box's shared read-only `~/infra`. All 66 binaries (22 oWALNUTS
BridgeStan libraries, 22 CmdStan executables, 22 nutpie libraries) are
compiled on the box from the same posteriordb sources, with the recipes that
built the Windows binaries. Nothing is copied from Windows.

**Co-tenancy, stated before running.** The box is shared by four
core-pinned lanes, one study each. This study is lane 1: every process,
builds included, runs under `taskset -c 0-3` with `RAYON_NUM_THREADS=4` and
`OMP_NUM_THREADS=1`. Three other lanes are active on cores 4–15 and share the
L3 cache and memory bandwidth. **Every wall-clock number in this study is
labelled "pinned, co-tenanted".** Pass counts and ESS per gradient are not
affected by co-tenancy. The Windows walls they are compared with are labelled
"contended" (up to seven agents on 16 hybrid cores).

## What could legitimately differ

The seeds are identical and every sampler is seed-deterministic. Even so,
bit-identical draws across platforms are not guaranteed:

- **libm.** Rust's `f64` transcendental functions and the Stan model code call
  the platform C math library: glibc on Linux, mingw-w64/msvcrt on Windows. A
  one-ulp difference in a single `exp`, `log` or `lgamma` changes one
  trajectory, and HMC trajectories then diverge chaotically. Draws at the same
  seed become a different realisation.
- **Compiler.** BridgeStan, CmdStan and nutpie model code is built by Linux
  g++, not mingw-w64 g++: a different version, with different inlining and
  instruction selection, at the same `-O3` and no `-march`.
- **BLAS.** numpy's bundled OpenBLAS differs by platform. It is not on the
  path of the gate statistics.
- **CmdStan and nutpie builds.** Different toolchains and TBB builds. Their
  RNG streams are seed-determined, so the libm caveat applies to them too.
- **Execution backend.** On Linux, oWALNUTS uses `ReplicatedConcurrent` with
  four replicas instead of `OwnedSerialised`. WP50C found that dispatch does
  not change draws.
- **Python 3.12 vs 3.11, and pandas.** Neither is on the numerical path.

The comparison script classifies each cell as bit-identical or not. Two
cells count as bit-identical when all of the following agree:
`gradients_total`, every final step size, every gate-parameter mean (relative
tolerance 1e-12), and, for oWALNUTS, the start log densities and the chosen
start candidates.

## Predictions (fixed before execution)

| | prediction | reference |
|---|---|---|
| **L1** | oWALNUTS pass counts reproduce **exactly**: **43/51** house and **6/15** new-five on the v7 seeds, **40/48** on the extension seeds | E26, E28 |
| **L2** | CmdStan and nutpie pass counts are each **within 3** of Windows: CmdStan 34/51, 7/15, 30/48; nutpie 26/51, 3/15 | E26, E28 |
| **L3** | Linux six-seed pooled fixed-16 oWALNUTS / CmdStan min-bulk-ESS per gradient lies in **[0.740, 0.822]** (WP62's statistic and inclusion rule) | E28 interval; Windows 0.761 |
| **L4** | Linux fixed-16 wall per gradient vs CmdStan **<= 1.0** (v7's P4) | Windows 1.849, serialised |

L1 is unevaluable unless all 114 oWALNUTS cells are recorded. L4 follows v7's
rule: it is unevaluable if a fixed-16 model is incomplete on either arm, and
then the value over the complete models is reported.

**Reported (R1), with our expectation stated before running.** We report the
number of bit-identical oWALNUTS cells and funnel seeds. Bit-identity is the
main risk to L1. We expect the funnel, which is pure Rust with few
transcendental calls per gradient, and some low-dimensional models to be
bit-identical. We expect some cells not to be, especially the ODE and HMM
models. A non-identical cell's pass or fail is a fresh draw from the same
sampler at the same seed. So L1 can fail without any defect, and the
interpretation rule below says how such a failure is read.

Also reported, not predicted: v7's P1–P8 and both release rules on Linux;
WP62's Q1–Q4, single-seed geomeans, leave-one-seed-out interval and jackknife
SE on Linux; per-arm Linux/Windows wall-per-gradient ratios; ESS per second
against CmdStan and nutpie; and the dense table.

## Interpretation rule (fixed)

- **If L1 fails,** every differing cell is classified by its bit-identity
  indicators.
  - A difference on a non-identical cell is attributed to platform floating
    point: it is a different realisation at the same seed. It is read
    against E28's seed variation (oWALNUTS 40/48 on both Windows seed sets).
  - A difference on a bit-identical cell would be an analysis-stack defect,
    and is reported as one.
- **Walls.** Linux walls ("pinned, co-tenanted") and Windows walls
  ("contended") drive no sampler conclusion. L4 tests only v7's
  preregistered explanation of its P4 failure, the Windows owned-worker
  serialisation.
- **No defaults.** This study changes no default and rewrites neither E26's
  nor E28's verdict. It adds a Linux row to each.

## Execution rules

- `PREREGISTRATION.md` and `protocol.json` are committed before the first
  cell. The drivers refuse every cell otherwise. They also refuse oWALNUTS
  cells unless the harness source tree is a clean checkout of the commit.
- Compilation and a smoke test (non-evidence seed 11, scratch output, not
  committed) are infrastructure. They may precede the freeze.
  - **What ran before this freeze.** Both harnesses were built. The binaries
    were being compiled at freeze time. One smoke test ran at seed 11 on
    `eight_schools_noncentered` only: three arms through `run_posteriordb.py`,
    one oWALNUTS cell through `run_extension.py`, and the funnel binary
    called directly at seed 11. It was **not** run through `checks`, which
    takes v7's evidence funnel seeds from the protocol, as v7's pre-freeze
    deviation did. The smoke test confirmed `ReplicatedConcurrent` with four
    replicas, affinity {0,1,2,3}, the `best_of(16)` start rule, and identical
    output from the two harnesses at seed 11. No evidence seed has been
    touched.
  - **Box.** Ubuntu 24.04, kernel 7.0.0-1014-aws, glibc 2.39, g++ 13, AMD
    EPYC 9R14.
- Cells run sequentially. Failures and timeouts are results. There are no
  reruns and no tuning after results.
  - A driver crash may be relaunched.
  - Only an interrupted cell without a completed artifact may be rerun from
    scratch with the same seed. The deviation is recorded in `AMENDMENTS.md`.
- Raw draws and CmdStan output are checksummed and not committed. Cell
  metrics, summaries, tables, logs and manifests are committed.
