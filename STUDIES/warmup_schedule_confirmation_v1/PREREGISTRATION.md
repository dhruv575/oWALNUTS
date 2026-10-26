# WP77 preregistration: confirmation of the WP73 warmup schedules `half` and `init25`

Frozen before any cell. `protocol.json` is the machine-readable form and wins on any
discrepancy. Ledger id `WP77-WARMUP-SCHEDULE-CONFIRMATION-V1`. WP77 was assigned by the
coordinator (WP74–WP76 are taken).

## Question

Should either WP73 candidate become the sampler default? The candidates, unchanged from WP73,
are:

- **`half`:** warmup 500 instead of 1,000, under the same window rule;
- **`init25`:** an initial fast phase of 25 instead of 75.

The question is decided on fresh seeds by rules fixed here.

## What is already known

From WP73 (3 seeds; three candidates passed its rule, but only `half` passed robustly):

- **`half`:**
  - ESS per total gradient vs default: geomean 1.315, median model 1.245, leave-one-model-out
    minimum 1.209.
  - Total gradients 0.80x, warmup gradients 0.58x, min bulk ESS 1.03x.
  - Passes 40 vs 40: sblrc lost one cell and one_comp gained one.
  - No retained divergence.
  - One passing cell with max |z| 4.99 (one_comp 730731).
- **`init25`:**
  - Geomean 1.440, but median model 1.038 and leave-one-out minimum 1.093.
  - The geomean was carried by `hmm_drive_0` (118x), where the default had stuck chains on 2 of
    3 seeds.
- **`stablestop`** is **dropped, and I do not argue for it.** Its robust readings in WP73 were
  1.08 (median model, without eight_schools_centered, leave-one-out minimum), which is below
  this study's per-model-median threshold of 1.10. Its saving is also a subset of `half`'s: a
  chain it stops is exactly the `half` chain. So it cannot pass where `half` fails, and it raises
  no separate default question.

## Environment (disclosed)

- **Lane:** lane 2 of the shared c7a.4xlarge box, cores 4-7, `taskset -c 4-7` on every process,
  with other lanes active. Walls are pinned, co-tenanted and not used.
- **oWALNUTS:** BridgeStan 2.9.0 without `STAN_THREADS`, `ReplicatedStanTarget` with four
  replicas (WP65-qualified).
- **CmdStan:** 2.39.0 at defaults, descriptive only.
- **Binaries:** the 17 BridgeStan libraries and CmdStan executables were copied from this lane's
  WP73 build (same posteriordb sources and recipe). Their sha256 values were checked against
  WP73's build manifest.
- **Library:** local main `e7a30d00`. WP71's and WP73's research flags are off. This study
  changes no library code.

## Design

- **Seeds:** 6 fresh seeds (770771–770776) and 30 fresh funnel seeds (770801–770830), all
  grep-verified unused.
- **Run shape:** 4 chains, 1,000 retained draws, warmup per arm (default 1,000, `half` 500,
  `init25` 1,000).
- **Phase T:** `kernel_fingerprint` and `stable_metric_stop` tests at the frozen commit, as an
  integrity record.
- **Phase A:** the 17 house models x {default, `half`, `init25`, CmdStan} x 6 seeds, one child
  process per cell, strictly sequential.
- **Phase F:** the funnel, 30 seeds x {default, `half`, `init25`}, 4 chains x 2,000 draws with
  each arm's own warmup.

**Statistic.** This is WP72's headline form (c), the median of paired per-seed ratios:

1. Per model, compute candidate / default on each seed where both cells are ok.
2. Take the median over those seeds. A model enters with at least 5 of the 6 seeds.
3. The headline is the geometric mean over the models that enter.

The rule uses ESS per **total** gradient (warmup included). The same statistic per **sampling**
gradient is reported, so that the benchmark comparison is visible. So are both quantities against
CmdStan, for the default and for each candidate. A 10,000-resample seed bootstrap interval of the
headline is reported, not gated.

## Rule for proposing a default (all must hold on the 6 seeds)

| clause | condition |
|---|---|
| G | the candidate's gate passes over the 102 cells are >= the default's on the same seeds (v7 gates) |
| H | the headline ESS per total gradient vs default is >= 1.15 |
| M | the per-model median (the median over models of the per-model ratios) is >= 1.10 |
| L | the leave-one-model-out minimum of the headline is >= 1.05 |
| D | no new divergences: no (model, seed) where the candidate has a retained divergence and the default (status ok) has none |
| Z | max \|z\| on the candidate's passing reference cells is <= 4 |
| F | funnel, 30 seeds x 4 x 2,000 draws with the candidate's warmup: \|mean P(omega < -5) − 0.0478\| <= between-seed s.e. |

- An errored candidate cell fails its gates.
- If both candidates pass, the one with the larger headline is proposed. Their combination is
  untested.
- **F is evaluated as worded:** 2,000 retained draws per chain, with the arm's warmup at the
  study's nominal 1,000 (`half`: 500). That is a coarser bias test than WP73's 2,000/20,000.
  At 30 seeds it fails an unbiased sampler about 32 % of the time.

## What a default change would mean

- **`half`** would change an API default, not the kernel.
  - `Sampler::new()`'s default warmup (`src/sampler.rs`, `warmup: 1_000`) would become 500, and
    the Python package's `warmup: int = 1000` keyword defaults would follow.
  - Unchanged: the window rule, the `walnutpie::WarmupConfig` / `WarmupWindowConfig` defaults,
    the retained kernel, `ALGORITHM_REVISION` and `tests/kernel_fingerprint.rs` (which passes
    explicit warmup lengths).
  - Runs that set `.warmup(n)` stay bit-identical. Runs on the default warmup get different
    draws.
- **`init25`** would change the warmup schedule.
  - It would be proposed only as a sampler-facade default: a `DEFAULT_WARMUP_WINDOWS =
    WarmupWindowConfig::new(25, 25, 50)` installed by `Adaptation::warmup_config`, as
    `DEFAULT_METRIC_REGULARIZATION` is.
  - That leaves `walnutpie::WarmupWindowConfig::default()`, `RunConfig` runs, the kernel,
    `ALGORITHM_REVISION` and the kernel fingerprints (which build `WarmupConfig` directly)
    unchanged.
  - Every default-configured sampler run gets different draws; no draw is identical.
  - Changing `WarmupWindowConfig::default()` itself would change the pinned
    `eight_schools_adapted_four_chains_are_bit_exact` fingerprint on both platforms, and is not
    proposed.

## Predictions

| candidate | G | H | M | L | D | Z | F | overall |
|---|---|---|---|---|---|---|---|---|
| `half` | holds (±2 cells) | holds (1.20–1.30) | holds (>= 1.15) | holds (>= 1.10) | holds | **fails** (a passing one_comp cell above 4, as in WP73) | holds | not proposed, on Z alone |
| `init25` | holds | fails (1.00–1.08) | fails (about 1.04) | fails | holds | holds | holds | not proposed |

Per sampling gradient, I predict `half` at 1.00–1.08x the default and `init25` at 0.97–1.05x:
the gain is warmup spend, not the retained kernel.

## Changes to the copied code

- **`src/`:** WP73's `lib.rs`, `main.rs` and `bin/funnel.rs`, with only the crate name changed
  (`warmup_schedule_confirmation_v1`). The `stablestop` arm stays defined but is not run.
- **`run_confirm.py`:** WP73's `run_spend.py`, with these changes:
  - phase A runs four arms, and there is no nutpie and no phase B;
  - the funnel specification;
  - the `WP77_*` environment names and the lane path;
  - the schema strings;
  - a new analysis (the paired statistic, its seed bootstrap, and clauses G–F).

  The posteriordb, metric, gate, oWALNUTS, CmdStan and funnel functions are WP73's.
- **`build_models.py`:** WP73's, without the nutpie tree. It reproduces the copied binaries.

## Smoke run (disclosed)

Before the freeze, every arm was smoke-tested on the box at seed 1 on the **non-study**
`kidiq-kidscore_momiq`, and on the funnel at seed 1. Output went to the lane's `smoke/`, never to
`artifacts/`.

## Rules

PREREGISTRATION.md and protocol.json are committed before the first cell.

- **Execution:** phases T, A, F in order, one process at a time.
- **Reporting:** every cell is reported; failures and timeouts are results; no reruns and no
  tuning after seeing results.
- **Interruptions:** a cell with no artifact may be rerun once with the same seed, recorded as a
  deviation.
- **Amendments:** only for cells not yet run, committed before them.
