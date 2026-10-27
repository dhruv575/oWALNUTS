# WP96: no tested re-adaptation policy qualifies at K = 200

The frozen warm path does **not** meet the predefined 2% P50 / 5% P95 quote-error
rule over this 2,000-tick, fixed-window experiment. Neither re-adaptation every
100 ticks, every 500 ticks, nor the cost/unchanged-position trigger qualifies.
Every policy fails the aggregate rule in both halves of both streams. There is
no library change or recommended re-adaptation default from this study.

The experiment completed before the original agent lost API access. All 18
cells and 32,000 warm updates were recovered and verified on 2026-10-27; no cell
was rerun. The original results table reproduces exactly on a local analysis
environment with the same NumPy and ArviZ versions.

## Design and evidence

The frozen [protocol](protocol.json) and [preregistration](PREREGISTRATION.md)
use the WP84/WP88 price-only Student-t stochastic-volatility model on a sliding
250-return window (253 dimensions), four chains and 200 retained transitions
per chain per update. The two synthetic streams share innovations. The shift
stream changes the volatility mean and innovation scale beginning at return
1,250, which first enters the window at tick 1,001; the control does not change.
Seeds are 960101 and 960102. Policies are frozen tuning, re-adaptation every
100 or 500 ticks, and a trailing-cost / unchanged-position trigger.

The reference is a fresh 4 x 2,000/20,000 fit every 25 ticks, with the frozen
warning-based chain selection and predictive R-hat gate. A scored tick passes
when absolute relative P50 error is at most 2%, P95 error at most 5%, and no
chain meets the predefined stuck-chain condition. Each half requires at least
76/80 passing seed-ticks and at least 36/40 for each seed. Latency and the
0.5-percentage-point drift flag are reported separately, not qualification gates.

## Frozen decision

Each entry below is the percentage of the 80 scored seed-ticks passing both
quantile tolerances. **All 16 entries fail the frozen half-level rule.**

| Policy | Shift half 1 | Shift half 2 | Control half 1 | Control half 2 |
|---|---:|---:|---:|---:|
| Frozen | 83.75% | 66.25% | 86.25% | 91.25% |
| Every 100 | 87.50% | 71.25% | 88.75% | 82.50% |
| Every 500 | 88.75% | 60.00% | 88.75% | 86.25% |
| Triggered | 86.25% | 62.50% | 87.50% | 90.00% |

The largest pass shares by stream/half are 88.75%, 71.25%, 88.75% and 91.25%,
respectively. These are descriptive maxima, not a selected qualified policy.
The [full table](artifacts/results-table.md) reports both seeds, signed and
absolute errors, diagnostics, cost, initialization and adaptation events.

| Policy | Shift median / P99 | Control median / P99 | Re-adaptations per seed, each stream |
|---|---:|---:|---|
| Frozen | 129 / 157 ms | 128 / 171 ms | 0, 0 |
| Every 100 | 306 / 585 ms | 285 / 556 ms | 20, 20 |
| Every 500 | 263 / 534 ms | 273 / 528 ms | 4, 4 |
| Triggered | 303 / 533 ms | 317 / 529 ms | 0, 1 |

These are pinned, shared-host measurements: group median is the median of the
two cell medians; group P99 is the larger cell P99, following `analyze.py`.
The triggered group combines a seed that never re-adapts and one whose
re-adaptation increases later cost. The table does not imply every triggered
cell has the same latency. Initialization is excluded. Re-adaptation ticks are
included; their maxima reach 1.15 seconds for the every-100 policy. There is no
new isolated timing or latency qualification from the recovery analysis.

## What failed, and what did not

The following descriptions are post-hoc diagnostics of the same evidence, not
new qualification tests. [Machine-readable decomposition](artifacts/recovery/failure-diagnostics.json)
includes error bands and P50/P95 own-MCSE distributions by policy, stream and
period; [the script](diagnose_existing.py) reproduces it.

- Failure begins **before** the regime change and occurs on the control stream.
  It cannot be attributed solely to post-shock metric drift. For the frozen
  shifted stream, 13/80 pre-shock scored ticks fail (11 P50, two P95, no overlap).
  After the shift, 27/80 fail (21 P50, nine P95, three overlap).
- Frozen shifted-half-2 median own relative MCSE is **1.69% for P50 and 3.59%
  for P95**, versus 1.03% and 2.24% before the shift. Mean signed errors are only
  +0.26% and +0.25% after the shift. Re-adaptation leaves similar precision:
  across the four policies, shifted-half-2 pooled median own MCSE is
  1.62–1.74% for P50 and 3.37–3.86% for P95. These pooled medians differ slightly
  from the original table's median-of-seed-medians. The pattern is consistent
  with finite Monte Carlo precision being a material limitation; it does not
  prove that more draws or any particular estimator will qualify.
- Errors continue after the window contains only regime-2 returns. On the
  shifted stream, passing counts during ticks 1,025–1,250 / 1,275–2,000 are
  frozen 13/20 / 40/60; every-100 17/20 / 40/60; every-500 12/20 / 36/60; triggered
  14/20 / 36/60. Thus the accuracy loss is not confined to the transition window.
- Frozen cost per transition does not show the predicted post-shock rise: for
  seed 960101, the four late 250-tick blocks are 0.87, 0.94, 0.94 and 0.91 times
  the initial baseline. Its half-1 and half-2 median latency stays near 129 ms.
  The cheap 200-warmup re-adaptation generally increases cost instead of
  resolving the quote-error failures.
- The trigger **never fires after the shift** on either seed. Seed 960101 has
  no firing. Seed 960102 fires at tick 913, identically in both streams, because
  its trailing unchanged-position fraction reaches 0.0501875; the cost ratio
  is only 0.790807. Cost or unchanged-position monitoring is therefore not an
  adequate detector of the observed quote-precision degradation in this study.
- There are no stuck chains at any scored warm tick and no retained divergence
  in any of the 32,000 warm updates. All 16 initial fits are clean and accurate;
  all re-adaptations complete without flagged-chain fallback or error. The
  remap was checked before the freeze to preserve the carried latent path.
  These facts do not establish equilibrium after every finite refresh.
- Only 17/32 seed/stream/policy/half drift statistics lie within the reported
  0.5-pp bound. The largest positive changes are +3.16 and +1.35 pp for the
  every-500 policy after the shift. There is no single common drift pattern
  across policies. Warm-draw occupancy of reference 90% intervals is
  89.64–90.29%; this is posterior agreement, not forecast calibration.
  Actual synthetic next-latent coverage ranges from 77.5% to 90% over the small,
  dependent 40-tick halves and does not justify a blanket calibration claim.

## Reference and recovery audit

All 162 planned reference ticks pass the original gate. Eleven selected ticks
drop one flagged chain (five shift, six control); one control tick needs the
predefined second attempt. No tick fails both attempts. Reference P50 relative
MCSE is at most 0.228%, and P95 at most 0.522%, below the corresponding quote
tolerances but not zero uncertainty.

The separate [supplemental audit](artifacts/recovery/audit.json) checks the
saved `mu`, `log_sigma` and `h_last` coordinates **before** independent predictive
innovation is added. Across all 162 selected reference attempts, maximum rank
R-hat is 1.000580, minimum bulk ESS 14,561 and minimum tail ESS 25,971, with zero
retained divergences among kept chains. No supplemental reference-coordinate
flag is raised. This reduces concern about the predictive-only gate masking
poor mixing in these saved coordinates; it cannot validate unrecorded beta or
the whole latent path, or supply an independent-algorithm reference.

The recovered archive SHA256 is
`c1557f20369bb90b1a7b4a96f15b506a5048a29a3b900d033d5063b01cd0cf9c`.
The remote tracked sources were clean at frozen commit
`9210c9471b2eacc1e1528455720239863bae76f0`; protocol, harness and analysis hashes
match the local Git blobs. The integrity audit verifies all planned ticks and
saved draw sizes and inventories 1,658 cell files totaling 185,183,822 bytes.
Raw compact draws remain on disk and are SHA256-pinned rather than committed.
Archive, source and environment provenance and original lane logs are under
[`artifacts/recovery`](artifacts/recovery/).

Both lanes started around 00:06 UTC on 2026-10-27 and finished at 01:52:52 and
02:02:31 UTC. Analysis already existed on the box before recovery. Reanalysis
with NumPy 2.5.4 and ArviZ 0.23.4 reproduces the original table and all decision
fields. Summary numeric differences are at most 2.22e-16. Four reported warm
R-hat values differ across Python/platform environments by at most 7.08e-5,
without crossing 1.01; the original artifacts are retained unchanged and the
comparison is recorded. No data were replaced or cells relaunched.

## Predictions and next decision

P1 is only partly supported: the shifted second half fails, but frozen tuning
also fails before the shift and on the control, and the predicted cost increase
does not occur. P2 (every-100 qualifies) is rejected. P3 correctly anticipates
every-500 failure after the shift but incorrectly predicts other halves pass.
P4's post-shock trigger prediction is rejected. P5 correctly predicts no final
reference failure but understates flagged chains. P6's 26/32 drift target is
missed (17/32). P7 holds: all 16 initial fits are clean and accurate.

The next research step is a **diagnostic** of quote-functional Monte Carlo
precision, finite-refresh equilibration and the benefit of integrating
predictive innovation analytically, at fixed targets and unchanged error
tolerances. Compare against the recovered references before choosing a fresh
qualification protocol. Neither a re-adaptation default nor a passing long-run
configuration is available to carry forward from WP96.

This study concerns a 250-return window on two simulated streams, with accuracy
observed every 25th tick. That cadence includes every periodic adaptation tick
and misses the first 24 post-shock updates; it does not establish every-update
accuracy or full-history posterior equivalence. Its code predates the WP90
trap-guard default. It establishes neither market calibration, executable AMM
quotes nor profitability, and does not motivate deployment.

## Reproduction

With the raw `artifacts/cells` tree present and the recorded package versions:

```text
python analyze.py artifacts/cells --out <fresh-analysis-directory>
python audit_recovery.py artifacts/cells <fresh-audit.json>
python diagnose_existing.py artifacts <fresh-failure-diagnostics.json>
python test_audit_recovery.py
python checksums.py
```

Use a new output directory for reanalysis. `RECOVERY-AUDIT.md` preserves the
audit plan written before evidence recovery; it records what was known then.
