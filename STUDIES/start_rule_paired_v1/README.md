# start_rule_paired_v1 (WP60): best-of-16 starts are not the cause of the v6 -> v7 per-gradient drop

## Verdict

**H0 is supported, and the frozen decision is KEEP.** Over the six models,
`Init::best_of(16)` reaches **1.061x** the ESS per gradient of
`Init::uniform()`, paired by seed. Only 2 of the 6 model ratios are below
1.0. So the start rule does not explain the drop from 0.848 to 0.708x CmdStan
between v6 and v7. Fresh seeds and the WP36 removal of chain rescue remain
the candidates. This study cannot separate those two.

**The rule did not price one cost: gates.** best_of_16 passes **15/30**
cells; uniform passes **18/30**. The deficit comes from `hmm_drive_0` (3/5 vs
5/5) and `one_comp` (1/5 vs 3/5), partly offset by `accel_gp` (1/5 vs 0/5).

On `hmm_drive_0`, two of the five best_of_16 seeds (600602 and 600605) each
have one chain held in a second mode. Its last-warmup-window median log
density is about 62 nats below the other chains', its per-chain ESS is 7 to
14, and the cell ratio is 0.04. `Summary::chain_warnings` named the chain in
both cells. This is the hidden-mode mechanism WP52 reported, now seen on 2 of
5 fresh seeds. Uniform shows the same low-density chain once (600605), and
that cell still passed.

Nothing was flipped.

## Design

The study was frozen at `76a569a3` before the first cell (see
`PREREGISTRATION.md` and `protocol.json`). It ran at `f097391c`, with the
library source checked by the driver. Both arms are `Sampler::new()` defaults
and differ only in the start rule.

- Models: `accel_gp`, `one_comp` and `hmm_drive_0`, plus the three
  lowest-ratio models from WP52 not already named (`earnings`, centered
  Eight Schools, `kidiq`).
- Runs: 4 x 1,000/1,000, 4 threads, seeds 600601–600605 paired by seed,
  strictly sequential.
- 60 cells ran 07:35–08:09 local, with no error, no timeout and no rerun.
  Walls are contended.

## Results

Ratios are best_of_16 / uniform min-bulk-ESS per gradient. In the passes
column, "u" is uniform and "b" is best_of_16.

| model | ratio (geomean of 5 pairs) | per-seed ratios | passes u / b | start log density median u / b |
|---|---:|---|---|---|
| accel_gp | **3.03** | 1.79, 2.32, 33.7, 0.46, 3.96 | 0/5 / 1/5 | -36,612 / -2,651 |
| one_comp | **0.89** | 0.64, 1.45, 0.59, 3.21, 0.31 | 3/5 / 1/5 | -89 / -59 |
| hmm_drive_0 | **0.32** | 1.96, 0.04, 1.16, 0.94, 0.04 | 5/5 / 3/5 | -22,747 / -3,627 |
| earnings | **1.11** | 0.87, 1.22, 1.19, 1.05, 1.24 | 5/5 / 5/5 | -2.5e6 / -6.2e4 |
| eight_schools_centered | **1.39** | 6.85, 2.01, 12.0, 0.39, 0.08 | 0/5 / 0/5 | -57 / -49 |
| kidiq | **1.08** | 1.17, 1.11, 1.11, 0.89, 1.14 | 5/5 / 5/5 | -2.4e6 / -2.5e4 |
| **geomean** | **1.061** (2/6 below 1) | pooled over 30 pairs: 1.061 | 18 / 15 | |

Mechanism, from per-chain telemetry (`artifacts/results-table.md` and
`artifacts/cells/`):

- On `accel_gp`, uniform's two worst seeds (600603 and 600605: R-hat 1.24 and
  1.09, ESS 13 and 34) were slow-mixing chains. best_of_16 started those
  chains about 30,000 nats higher and avoided it.
- On centered Eight Schools, the ratios swing from 0.08 to 12, as expected on
  a funnel where every cell fails.
- On `one_comp`, both arms fail on tail ESS. Its 0.89 sits inside the seed
  spread (0.31 to 3.21).
- Uniform `one_comp` 600601 **passes with max |z| 5.53**. This is a passing
  cell beyond the house |z| <= 4 check, in the arm that is not the default.

The prediction thresholds were H1 below 0.9 and H0 at or above 0.95. The
observed 1.061 supports H0. The decision rule says KEEP. Most of the
geomean's movement comes from `accel_gp` (3.0) against `hmm_drive_0` (0.32);
without those two the geomean of the other four is 1.11.

## Recommendation

- Keep `Init::best_of(16)`, as the frozen rule says.
- Document that best-of-16 raises the risk that a chain starts in a
  second-mode basin on multimodal posteriors: 2/5 `hmm_drive_0` seeds here,
  and the WP52 two-mode cases. `chain_warnings` flags that chain, so the
  warning should be surfaced in the docs next to the default.
- Investigate the v6 -> v7 drop by separating fresh seeds from rescue
  removal, for example with a rescue-on / rescue-off pair on `accel_gp` and
  `one_comp`. Do not change the start rule for it.

Raw draws are uncommitted and checksummed in `CHECKSUMS.sha256`.
