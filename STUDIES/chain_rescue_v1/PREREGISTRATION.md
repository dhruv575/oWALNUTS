# chain_rescue_v1 — preregistration (WP33)

Frozen 2026-09-03 before any candidate was run on any model; the protocol
is `protocol.json` (hashed in `CHECKSUMS.sha256` after the run). Committed
before the implementation is complete so that the rules below cannot be
tuned on evidence. The implementation commit that follows may change the
mechanism only to make the rules below hold as written.

## The problem being addressed

After the post-WP31 default change (`STUDIES/posteriordb_bench_v5`, WP32:
42/51 gates against CmdStan's 36 and nutpie's 28) nearly every remaining
oWALNUTS gate failure outside the two fail-everywhere models is **one bad
chain out of four, caused by the start draw**:

* `hmm_drive_0`: one chain in a second HMM mode (v5 87102: R-hat 1.35, min
  bulk ESS 10, that chain's step 0.37 against 0.58–0.65 on the others).
* the 10-D funnel at the sampler defaults: one chain per seed adapting to
  `h` 0.001–0.02 (v5 87103: `h` 0.0013, 933 depth caps, `omega` bulk ESS 274).
* `arma11`: seeds where one chain escapes the overflow pin then crawls
  (`STUDIES/step_collapse_v1`); CmdStan cannot leave that start either.
* `sblrc` / `earnings` historically one chain at 10x the others' step;
  `lotka_volterra` one chain on the `rk45` failure boundary (WP31 86103,
  26–44 minutes per cell).

CmdStan and nutpie run their chains independently and have no remedy.

## Candidates (fixed before measurement)

All candidates act **only during warmup**, at the end of slow metric
windows, on the multi-chain diagonal-metric driver; retained draws are
produced by the unchanged per-chain kernel from whatever state warmup
leaves, so the retained-phase kernel and its fingerprints are untouched.
They are opt-in through `WarmupConfig::with_chain_rescue(ChainRescueConfig)`;
the `sampler` default is unchanged unless the decision rule below is met.
Every candidate is deterministic given the seed; each chain keeps its own
RNG stream; a rescued chain consumes exactly one extra draw from its own
stream to pick the source position; telemetry is
`RunTelemetry::chain_rescues()` (one `ChainRescueUpdate` per chain per
boundary, with the scores, the decision and the criterion).

### A. `restart` — restart-from-best at slow-window boundaries

At the end of every slow window (after that window's metric update and
dual-averaging restart, which every chain still does on its own), the
chains are scored on the window just completed:

* `step` = the chain's step after the boundary restart;
* `median_log_density` and `log_density_iqr` = median and interquartile
  range of the selected state's log density over the window's transitions.

A chain is an **outlier** when either

* (step rule) `step < 0.1 x median over chains of step`, or
* (density rule) `reference - median_log_density > 3 x spread`, where
  `reference` is the median over chains of `median_log_density` and
  `spread` is the median over chains of `log_density_iqr` (the density
  rule is one-sided: a chain with unusually *high* density, e.g. one stuck
  in the funnel neck, is caught by the step rule and never used as a
  source).

A boundary with fewer than 10 transitions in the window, or fewer than two
chains, scores nothing. The **source** is the non-outlier chain with the
largest step (ties: the higher `median_log_density`). Each outlier chain is
re-seeded from the source: its position becomes one of the source's
window positions, chosen uniformly with the outlier chain's own RNG; its
cached evaluation is cleared (the next transition evaluates the position:
one target call); it adopts the source's installed metric, step, dual
averaging state, stream and search steps. Nothing else changes. If no
chain is an outlier nothing happens and the run is bit-identical to the
no-rescue run (tested).

Fixed constants: step ratio 0.1, density factor 3 IQRs, minimum window
10 transitions, every slow window.

### B. `pool` — cross-chain metric and step pooling at boundaries

At the end of every slow window the chains' Welford window statistics are
combined (exact parallel-variance merge), regularised with the configured
rule at the pooled count, and installed on **every** chain; the step
becomes the median over chains of the post-boundary steps and dual
averaging is restarted from it on every chain (at a boundary that ends
warmup, the metric is pooled and the step is the median of the final
steps, no restart). Positions are untouched. This is the milder variant:
no chain is moved, but a chain that measured the wrong geometry is
outvoted.

### C. start-quality retry — **deferred, not run**

Drawing `k` starts per chain and keeping the best after a short burst is a
`sampler::Init` change, not a warmup change; it is listed here so that the
candidate set is on record, and it is not implemented or measured in this
study.

## Protocol

`STUDIES/posteriordb_bench_v5` harness and protocol (4 chains, 1,000 /
1,000, `Init::uniform()` starts, gates rank R-hat <= 1.01, bulk and tail
ESS >= 400 on every reference parameter, zero sampling divergences, ArviZ
0.23.4 estimators, cell timeout 2,700 s, strictly sequential) on the eight
posteriordb models below, three arms, seeds **88101–88103** (verified
unused as seeds: the only textual matches are digit substrings inside
trace values), plus the 10-D funnel at the sampler defaults (4 x 2,000 /
20,000, `omega` starts {-3, -1, 1, 3}, the `funnel_defaults_v1` MCSE z of
`P(omega < -5)` against 0.0478) per arm and seed:

| arm | configuration |
|---|---|
| `da` | the shipped defaults, nothing overridden (the v5 `owalnuts-da` arm on fresh seeds) |
| `restart` | `da` + `Adaptation::Custom(the default warmup config).with_chain_rescue(ChainRescueConfig::restart_from_best())` |
| `pool` | `da` + `.with_chain_rescue(ChainRescueConfig::pool_at_boundaries())` |

Models: `bball_drive_event_0-hmm_drive_0`, `arma-arma11`, `sblrc-blr`,
`earnings-logearn_interaction`, `hudson_lynx_hare-lotka_volterra` (the
failure class), `kidiq-kidscore_momhsiq`, `mesquite-logmesquite_logvash`,
`nes2000-nes` (controls), plus the funnel. Compiled BridgeStan libraries
are byte copies of the `wt/posteriordb-v4` worktree's (not modified
there); the venv and posteriordb checkout of that worktree are used read
only.

**Cells and gates.** 27 cells per arm: 24 posteriordb cells (8 models x 3
seeds) with the v5 gates, and 3 funnel cells whose gate is `|z| <= 2`
**and** `omega` bulk ESS >= 400 **and** `omega` rank R-hat <= 1.01 (v5's
87103 cell would fail this gate at ESS 274: the funnel one-chain collapse
is in the class this study is about, and the tail-mass z alone does not
see it).

**Metrics per cell.** Gates; min bulk ESS per gradient (target calls,
warmup included); rescues fired (chains re-seeded, or boundaries pooled)
per cell from the telemetry, with the criterion; posterior agreement with
the posteriordb reference (max |z| over reference parameters, the v5
statistic); on the funnel the tail-mass z, `omega` ESS and R-hat, final
steps per chain and depth caps.

## Decision rule (fixed before any run)

A candidate replaces the current default (applied by
`Adaptation::DualAveraging` and `Adaptation::Paper` through a new
`sampler::DEFAULT_CHAIN_RESCUE`, in a labelled final commit with
`tests/sampler_api.rs` updated) if and only if, on the 27 cells paired
with the `da` arm on the same seeds:

1. it passes **>= 3 more** of the 27 cells than `da`;
2. no model's seed-median min-bulk-ESS/gradient is below **0.9x** `da`'s;
3. no cell has reference-agreement **|z| > 3.5** where the `da` cell on the
   same seed has none;
4. the funnel tail mass has **|z| <= 2 on every seed**.

If both candidates meet the rule the one with more gates wins (ties: the
higher geomean ESS/gradient). Otherwise the defaults stay and the
candidates remain opt-in. The rule is the task's; note that with `da`
expected to pass 22–24 of its 24 posteriordb cells and 1–2 of 3 funnel
cells, criterion 1 is hard to meet by construction — this is recorded
here, not adjusted after the fact.

## Predictions

| | prediction |
|---|---|
| P1 | `restart` fires on at most one chain per cell on the three control models (kidiq, mesquite, nes2000), and on **no** chain at boundaries after the second slow window there |
| P2 | `restart` makes every funnel cell's final steps agree within 10x across chains and passes the funnel gate on every seed (`da`: 1–2 of 3) |
| P3 | wherever `da` draws a second-mode `hmm_drive_0` chain, `restart` fires the density rule on that chain at or before the third slow window and the cell passes the R-hat gate |
| P4 | neither candidate changes any model's seed-median max \|z\| by more than 1, i.e. no bias |
| P5 | `pool` is within 0.9–1.2x `da` per gradient on every model and gains no gate |
| P6 | the decision rule is **not** met by either candidate (criterion 1); the outcome is an opt-in with evidence, not a default flip |

## Rules

Report all cells; no reruns; failures are results; nothing is tuned after
seeing results; if the implementation must change after the first cell
(a bug), every cell is deleted and rerun and the deviation recorded.
