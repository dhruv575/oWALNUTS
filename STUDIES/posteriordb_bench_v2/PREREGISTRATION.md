# posteriordb benchmark v2 — preregistration

Frozen before execution on 2026-09-02 (see `protocol.json`; its SHA-256 is the
first line of `CHECKSUMS.sha256`). Nothing in this file or in `protocol.json`
is edited after the first evidence cell starts; deviations are appended under
"Deviations" with a timestamp.

## Question

`STUDIES/posteriordb_bench_v1` (seeds 77101–77103) recorded, at default
settings, owalnuts-da 26/51 cells passing against CmdStan 34/51 and nutpie
29/51, 0.32x CmdStan's bulk ESS per gradient and 0.11x per second, the
Appendix C warmup freezing on nine models, twelve oWALNUTS cells lost to
fatal NaN/inf evaluations or unevaluable starts, and depth-8 caps on the
correlated regressions. Since then `main` merged: a non-`STAN_THREADS`
BridgeStan build with `ReplicatedStanTarget` (the whole of the ~10x wall
gap, `posteriordb_bench_v1/artifacts/wall-gap/`), recoverable NaN/inf
evaluations in `StanTarget`, `sampler::Init::uniform()` start retries,
`sampler::Tuning::default()` at depth 10 (`adaptation_parity_v1`), the v4
robust `PaperAdaptationConfig::default()` (`paper_adaptation_robust_v1`),
and the opt-in `WarmupConfig::stan_style` preset. **With every one of those
in place and everything else identical, where does oWALNUTS stand against
CmdStan and nutpie on the same 17 posteriors, and which v1 failures are
gone?** This is the release gate named in the v1 ledger entry for any breadth
claim.

## Model set

The v1 set, unchanged (17 posteriors from posteriordb `28f8d3d`, listed in
`protocol.json`; a fresh shallow clone of the same commit).

## Arms (all at their defaults; nothing tuned per model)

* **owalnuts-da** — `owalnuts::sampler::Sampler` with `Tuning::default()`
  (`h0 = 0.5`, depth 10, 1 micro-step, 4 refinement levels, `delta = 1`,
  divergence threshold 1000), `Metric::diagonal()` (adapted from identity),
  `Adaptation::default()` (dual averaging toward acceptance 0.8),
  `Limits::admit_worst_case()`, four chains on four threads, starts by
  `Init::uniform()` (uniform(-2, 2) unconstrained, redrawn up to 100 times
  until the density and gradient are finite; drawn through
  `sampler::uniform_starts` with the sampler seed so the run is bit-identical
  to `run_with_init`). Target: `ReplicatedStanTarget` with four replicas of a
  BridgeStan 2.9.0 / Stan 2.39.0 library compiled **without** `STAN_THREADS`
  for this study (no v1 library is reused; the v1 environment no longer
  exists).
* **owalnuts-paper** — identical, `Adaptation::Paper(PaperAdaptationConfig::default())`
  (v4: exhausted transitions counted as zero, step bound 1e6).
* **owalnuts-stan-style** — identical, `Adaptation::Custom(WarmupConfig::stan_style(0.8))`
  (mean-trajectory acceptance, Stan initial step search, Stan metric
  regularisation, Stan restart reference, `delta` = divergence threshold for
  the initial 75-transition phase). In `adaptation_parity_v1` this preset
  (`all+ramp`, at `h0 = 0.1`) was 0.68x CmdStan geomean but failed R-hat on
  kidiq and earnings.
* **cmdstan** — CmdStan 2.39.0 via cmdstanpy 1.3.0 defaults, exactly as v1.
* **nutpie** — nutpie 0.16.8, BridgeStan backend, defaults, exactly as v1.

Every arm: 4 chains, 1,000 warmup, 1,000 retained, seeds **78101, 78102,
78103** (grep of `wiki/`, `STUDIES/`, `src/`, `integrations/` before
freezing: no occurrence). Run order: models in table order; arms in the order
above; seeds ascending; strictly sequential; 45-minute cell timeout. Each
model is compiled once per toolchain before its cells; compile time is
excluded from every wall.

Differences from v1 other than the fixes under test: `h0 = 0.5` instead of
0.1 (the `sampler` default; the parity study found `h0` immaterial under
dual averaging with the initial-step search off, and the stan-style preset
searches its own initial step); the oWALNUTS wall excludes the start search
(at most a few hundred evaluations, versus 10^5 per run); gradient counts
include it, as v1 included its single initialisation call.

## Metrics, gates, estimators

Identical to v1 (`protocol.json`): ArviZ 0.23.4 rank R-hat, bulk/tail ESS on
the posteriordb reference parameter columns (oWALNUTS draws constrained by
BridgeStan), min over parameters; gradients warmup + sampling; wall around
the single sampler call; ESS/s, ESS/gradient, wall per gradient; agreement
z against the reference mean. Gates: rank R-hat <= 1.01, bulk and tail ESS
>= 400, zero sampling divergences, finite draws, no sampler error. New
reported quantity: a chain is *frozen* when more than 500 of its 1,000
retained transitions end in refinement exhaustion (the v1 freeze signature
was 1,000/1,000).

## Preregistered analysis

1. Per-model table and head-to-head as in v1, now for three oWALNUTS arms:
   geometric mean over models complete on both sides of seed-median ratios
   of min bulk ESS/gradient, min bulk ESS/s and wall per gradient against
   CmdStan and against nutpie; wins per model; "outright win" = at least as
   many gate passes and higher seed-median ESS/gradient *and* ESS/s.
2. v1-vs-v2 table: per model and arm (da, paper, cmdstan, nutpie), seed-median
   v2/v1 ratio of ESS/gradient and ESS/s, and the four-number headline
   (cells passing; geomean ESS/grad and ESS/s vs CmdStan and vs nutpie) side
   by side with v1's. The v1 arms ran at depth 8, `h0 = 0.1` and the
   `STAN_THREADS` build, so the DA ratio measures the sum of the fixes, not
   the kernel.
3. Predictions (`protocol.json`): **P1** owalnuts-da passes >= 33/51 cells;
   **P2** owalnuts-da geomean bulk ESS/gradient vs CmdStan >= 0.45; **P3**
   owalnuts-da geomean wall per gradient <= 1.5x CmdStan's; **P4** the paper
   arm has no frozen cell; **P5** zero oWALNUTS cells (any arm) lost to a
   fatal NaN/inf evaluation or an unevaluable start. Also expected but not
   gated: the stan-style arm above the DA arm on geomean ESS/gradient with
   R-hat misses on one or two regressions; centered eight schools, `accel_gp`
   and `one_comp` still fail for every arm.

No decision rule changes a default from this study; it is a measurement and
the release gate for a breadth claim (a claim is licensed only if P1–P3 and
P5 hold).

## Reporting

`artifacts/summary.json` (every cell and metric, the v1 comparison and the
prediction outcomes), `artifacts/results-table.md`, `README.md` (verdict),
`LEDGER-ENTRY.md`, `CHECKSUMS.sha256` (raw draws hashed, not committed;
CmdStan CSVs neither hashed nor committed). Failures are results; no cell is
rerun; nothing is tuned after seeing results. A driver crash is relaunched
and the interrupted cell re-run from scratch (seeded), logged below.

Before freezing, the pipeline was smoke-tested once on the noncentered eight
schools with seed 1 (all three oWALNUTS arms; output deleted, not a study
seed).

## Load caveat

Shared 16-thread machine (Intel Core Ultra 7 255H, Windows 11); other agents
may run during execution. Walls are upper bounds; ESS per gradient is the
machine-independent primary figure.

## Deviations

(none at freeze)
