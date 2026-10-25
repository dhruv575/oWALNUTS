# rescue_removal_paired_v1 (WP61): removing chain rescue does not explain the v6 -> v7 per-gradient drop

## Verdict

**H0 supported: rescue removal is not the cause.** With
`restart_from_best()` reinstalled, the paired rescue_on / rescue_off ESS per
gradient is **1.023** over the five models. H1 needed >= 1.15; H0 needed
< 1.05. Gates are identical, 12/25 in each arm.

The rescue acted on only 7 of 25 seeds: two on `accel_gp` and three on
`hmm_drive_0`, all by the log-density criterion. The other 18 pairs are
bit-identical. With WP60 (start rule: 1.061), neither default change since
v6 accounts for the drop from 0.848 to 0.708x CmdStan. Seed variation does.
Under one fixed configuration, the five rescue_off seeds here span the v6 and
v7 values on four of the five models.

As preregistered, this is attribution only. Nothing is flipped, and restoring
rescue is not recommended. WP36's mode-hiding objection stands, and here
every restart was a log-density restart, the kind WP36 objected to.

## Design

The study was frozen at `17258586` before the first cell (see
`PREREGISTRATION.md` and `protocol.json`, which also summarise what WP36
found). It ran at main **`c8b4bb2d`**, whose sampler is that of `f097391c`.

The arms are `Sampler::new()` defaults with best-of-16 starts:

- **`rescue_off`**: the current default, with no rescue.
- **`rescue_on`**: `Adaptation::Custom(WarmupConfig::new(0.8)` plus the
  default exhaustion rule and Stan regularisation, plus
  `with_chain_rescue(restart_from_best()))`. This is what v6's default
  built, and how WP36's `current` arm was built.

Runs are 4 x 1,000/1,000 with 4 threads, on seeds 610601–610605 paired by
seed. 50 cells ran 08:14–08:38 local, with no errors and no reruns.

## Results

| model | ratio on/off (geomean of 5 pairs) | per-seed | restarts per seed (on) | passes off / on |
|---|---:|---|---|---|
| accel_gp | **1.012** | 1.00, 1.00, 0.90, 1.18, 1.00 | 0, 0, 1, 1, 0 (LogDensity) | 0/5 / 0/5 |
| one_comp | **1.000** | identical | none | 2/5 / 2/5 |
| hmm_drive_0 | **1.109** | 1.31, 1.00, 1.17, 1.00, 1.09 | 1, 0, 1, 0, 2 (LogDensity) | 5/5 / 5/5 |
| eight_schools_centered | **1.000** | identical | none | 0/5 / 0/5 |
| nes2000 | **1.000** | identical | none | 5/5 / 5/5 |
| **geomean** | **1.023** (0 below 1, 2 above) | | 7 cells | 12 / 12 |

On `hmm_drive_0` 610601, rescue_off has a chain whose end-of-warmup step is
0.135x the median, and the cell still passes. Rescue restarts that chain and
the cell gains 1.31x per gradient. This is the "late or second-mode chain"
case WP36 flagged; here it is an efficiency gain, not a gate change.

Seed noise, from rescue_off min-bulk-ESS per gradient x1e3: the median and
range over this study's five seeds, against the v6 and v7 seed medians.

| model | v6 | v7 | WP61 off median (range) |
|---|---:|---:|---|
| accel_gp | 0.232 | 0.098 | 0.019 (0.004–0.216) |
| one_comp | 13.58 | 9.64 | 9.61 (9.20–15.50) |
| hmm_drive_0 | 42.05 | 28.94 | 40.32 (30.64–54.95) |
| eight_schools_centered | 0.281 | 0.167 | 0.421 (0.103–0.656) |
| nes2000 | 4.53 | 4.11 | 4.50 (3.38–4.95) |

## Recommendation

- No change. Report the v7 per-gradient figure as seed-dependent: the
  3-seed fixed-16 geomean against CmdStan moves by about 0.1 between seed
  sets with no code change behind it.
- A future breadth headline should use more seeds, or report a seed interval,
  before a per-gradient threshold such as 0.75 is used as a release gate.

Raw draws are uncommitted and checksummed in `CHECKSUMS.sha256`.
