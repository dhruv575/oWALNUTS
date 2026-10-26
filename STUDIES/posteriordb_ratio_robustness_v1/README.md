# posteriordb ratio robustness (WP72): over 18 seeds the per-gradient headline is about 0.83x CmdStan under every statistic; WP64's 1.21 was six unlucky CmdStan seeds

## Verdict

**The headline is 0.83x CmdStan per gradient, with interval [0.79, 0.94].**
That is statistic (c), the median of paired per-seed ratios, over 18 Linux
seeds. It was proposed before any cell and selected by the frozen rule.

**WP64's 1.206 was mostly seed noise in CmdStan's failures.** On the 12 new
seeds, CmdStan's `hmm_drive_0` has a stuck chain on **1 of 12** seeds; on
WP64's six it was 4 of 6. Over all 18 seeds that is **5/18**, against 1/18
for oWALNUTS. With 18 seeds, the four preregistered statistics agree to
within 0.05:

| statistic (Linux, 18 seeds, 16 models) | value | 95 % seed-bootstrap interval | models | leave-one-model-out max \|ln\| influence |
|---|---:|---|---:|---|
| (a) v7 pooled geomean | 0.822 | [0.776, 0.892] | 16 | 0.063 (`one_comp`; 0.772 without) |
| (b) joint-pass cells only | 0.870 | [0.833, 0.891] | 12 | 0.017 (`sblrc`; 0.885 without) |
| **(c) median of paired ratios** (headline) | **0.826** | **[0.789, 0.935]** | 16 | 0.055 (`one_comp`; 0.782 without) |
| (d) (a) without `hmm_drive_0` | 0.824 | [0.775, 0.880] | 15 | 0.067 (`one_comp`; 0.771 without) |

| prediction | registered | observed | held |
|---|---|---|---|
| Q1 | (b) in [0.80, 0.95] | 0.870 | **yes** |
| Q2 | (c) in [0.80, 0.95] | 0.826 | **yes** |
| Q3 | (a) > 1.0 only because of `hmm_drive_0` ((a) > 1, (d) <= 1) | (a) 0.822, (d) 0.824 | **no**: with 18 seeds, (a) does not exceed 1 at all |
| Q4 | the frozen rule selects (c) | (c), influence 0.055 vs (a) 0.063 | **yes** |

**Why (c).** It meets the criterion: it is the less sensitive of the two
eligible statistics to one model, and it still counts oWALNUTS's own
failures.

- **(b) is narrowest but is not eligible.** It drops 4 of the 16 models
  (centered Eight Schools, `gp_pois_regr`, `one_comp`, `accel_gp`), and it
  drops every cell where oWALNUTS fails. It answers a different question:
  efficiency when both samplers work, 0.87x.
- **(c) keeps oWALNUTS's failures in.** Its two worst models are oWALNUTS's
  own failures, at their measured ratios: `accel_gp` (0.48) and centered
  Eight Schools (0.39).
- **The largest single-model influence is now a competitor failure, not
  `hmm_drive_0`.** It is `one_comp`, where CmdStan fails all 18 cells and
  the ratio is about 1.9–2.1. Dropping `one_comp` moves (c) to 0.78.

## Comparison with the earlier pools

| pool | (a) | (b) | (c) | (d) |
|---|---|---|---|---|
| Linux, 18 seeds (primary) | 0.822 [0.776, 0.892] | 0.870 [0.833, 0.891] | **0.826 [0.789, 0.935]** | 0.824 [0.775, 0.880] |
| Linux, 12 new seeds | 0.813 [0.756, 0.864] | 0.866 [0.818, 0.889] | 0.808 [0.766, 0.869] | 0.813 [0.755, 0.869] |
| Linux, WP64's 6 seeds | 1.206 [0.921, 1.468] | 0.896 [0.845, 0.909] | 1.189 [0.958, 1.552] | 0.862 [0.772, 1.474] |
| Windows, WP56 + WP62's 6 seeds | 0.761 [0.712, 1.431] | 0.853 [0.773, 0.944] | 0.773 [0.740, 1.642] | 0.749 [0.707, 1.242] |

- **Six seeds are not enough for either median statistic.** The six-seed
  intervals of (a) and (c) span 0.7–1.6 on both platforms.
- **More seeds settle both.** At 12 or 18 seeds, (a) and (c) narrow to
  about ±0.06 and agree.
- **(b) is stable from six seeds on.** It is 0.85–0.90 on every pool, and on
  both platforms.
- **The record's 0.76 (Windows) and 1.21 (Linux) are the same quantity.** Both
  are draws from this distribution, at the low and high end.

## `hmm_drive_0` stuck chains

A chain counts as stuck if a gate parameter's chain mean lies more than 5
reference sd from the posteriordb reference mean.

| seeds | CmdStan cells with a stuck chain | oWALNUTS cells with a stuck chain |
|---|---:|---:|
| WP64 (560561–560563, 620601–620603) | 4/6 (1, 2, 1, 1 chains on 560562, 560563, 620601, 620602) | 0/6 |
| new (720701–720712) | 1/12 (720702, 1 chain) | 1/12 (720707, 1 chain) |
| **all 18** | **5/18** | **1/18** |

- **The oWALNUTS case.** The stuck chain on 720707 fails the gates: R-hat
  1.229 and bulk ESS 13. `chain_warnings` named it: "last-warmup-window
  median log density 63.1 below the chains' median", and R-hat falls to
  1.001 without it. It enters (a) and (c) at its measured ratio.
- **The only other stuck chains in the study** are two CmdStan
  `lotka_volterra` cells. Every other model has zero stuck chains on both
  arms over 18 seeds.

## Gates

- **New seeds:** oWALNUTS 157/192, CmdStan 136/192.
- **All 18 seeds:** oWALNUTS 239/288 (83.0 %), CmdStan 198/288 (68.8 %).
  oWALNUTS's rate matches WP62's 40/48. CmdStan's is above WP62's 30/48.
- **Models CmdStan fails throughout the new seeds:** centered Eight Schools
  and `accel_gp` fail on both arms. `gp_pois_regr` (0/12 against oWALNUTS
  9/12) and `one_comp` (0/12 against 6/12) fail for CmdStan only.
- **Errors:** one CmdStan error on the new seeds, `lotka_volterra` 720706
  (`integrate_ode_rk45` max_num_steps). Over 18 seeds CmdStan has 3 errors
  on that model, so `lotka_volterra` enters (a) and (c) at exactly 15/18 ok.

## Design

Preregistered at `0e42b648` before the first cell (`PREREGISTRATION.md`,
`protocol.json`).

- **Runs.** 12 fresh seeds (720701–720712) on the fixed 16. Arms: oWALNUTS
  at `c5c60122` defaults and CmdStan 2.39.0. 4 x 1,000/1,000 with 4 threads,
  v7 / WP62 gates and cell code. The harness crate is byte-identical to
  v7's. The binaries were copied from WP64's Linux build.
- **Execution.** 384 cells, 02:25–03:25 UTC, strictly sequential, with no
  reruns and no amendments.
- **Pool.** WP64's six Linux seeds plus these 12. Seed bootstrap with 10,000
  resamples (rng seed 72).
- **Analysis.** Run on the box under the same pinning.
- **Platform.** AWS c7a.4xlarge, lane 1 (`taskset -c 0-3`), with other lanes
  active. Walls are "pinned, co-tenanted" and play no part in this study's
  statistics.

## Deviations

- None. One smoke test ran before the freeze, at non-evidence seed 11, into
  scratch output. It reproduced WP64's seed-11 smoke exactly.
- The analysis code was exercised before the freeze on the Windows cells,
  printing only the already-published Windows (a) value.
- The stuck-chain threshold was calibrated on WP64's six already-published
  `hmm_drive_0` cells.
- The raw draws and CmdStan output are checksummed and not committed.

## Recommendation

- **Use (c) as the v8 per-gradient headline,** with its seed-bootstrap
  interval and at least 12 seeds. Here that is **0.83x CmdStan [0.79,
  0.94], 18 Linux seeds, 16 models**.
- **Report (b) beside it,** as "0.87x when both samplers pass", with a
  footnote naming the competitor-only failures (`one_comp`, `gp_pois_regr`)
  that lift (a) and (c).
- **Retire both six-seed figures,** the 0.76 and the 1.21.
- No default change.
