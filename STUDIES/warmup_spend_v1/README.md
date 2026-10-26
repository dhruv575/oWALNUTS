# WP73: warmup gradient spend against CmdStan and nutpie, and three research schedules

## Verdict

**The spend gap is small, but warmup is still oversized.**

- **The gap.** On the 17 house models, oWALNUTS spends a median 52.4 % of its gradients before
  the first retained draw. CmdStan spends 50.8 % and nutpie 52.3 %. That is +0.031 above
  CmdStan and +0.007 above nutpie, against WP58's 0.23 above nutpie on `hier`.
- **The lever.** Halving the warmup (`half`, 500 transitions) cuts warmup gradients to 0.58x
  and total gradients to 0.80x. The median min bulk ESS stays at 1.03x.

**All three candidates pass the frozen rule (R1–R4) as preregistered**, contrary to the
prediction that none would. Post-hoc robustness checks show that only `half` clears 1.10x
without relying on one or two models:

- **`init25`'s** 1.44x depends on `hmm_drive_0` (118x, because the default had stuck chains on
  2 of 3 seeds). Without that model the leave-one-out geomean is 1.09.
- **`stablestop`'s** 1.12x depends on `eight_schools_centered`, which fails the gates in every
  arm. Without it the geomean is 1.08.

These are research flags only; no default changed. The run used fresh seeds 730731–730733,
4 x 1,000/1,000, v7 gates and metrics. oWALNUTS ran on the WP65-qualified replicated BridgeStan
dispatch, against CmdStan 2.39.0 and nutpie 0.16.8 at v7's settings. Everything ran pinned to
lane 2 (cores 4-7) with three other lanes active, so walls are not used.

| candidate | R1 passes vs default (40/51) | R2 geomean ESS / total gradient | R3 funnel P5 ± s.e. (exact 0.0478) | R4 fingerprint | rule | robust readings (post hoc) |
|---|---:|---:|---:|---|---|---|
| `init25` (initial fast 25, not 75) | 43 | **1.440** | 0.0463 ± 0.0017 | pass | **qualifies** | median 1.04; without hmm_drive_0 + eight_centered 1.04; leave-one-out min 1.09 |
| `half` (warmup 500, last window closes at 450) | 40 | **1.315** | 0.0499 ± 0.0032 | pass | **qualifies** | median 1.25; without the two 1.26; on the 11 models both pass 3/3, 1.20; leave-one-out min 1.21 |
| `stablestop` (new `StableMetricStop`, 68 of 204 chains stopped at 500) | 40 | **1.124** | 0.0477 ± 0.0015 | pass | **qualifies** | median 1.08; without the two 1.08; leave-one-out min 1.08 |

Default funnel (descriptive): 0.0477 ± 0.0015.

## Descriptive arm (phase A, `artifacts/results-table.md`)

| prediction | registered | observed | held |
|---|---|---|---|
| P1 | median (oWALNUTS − CmdStan warmup share) in [0.00, 0.05] | **+0.031**; range −0.360 (eight_schools_centered) to +0.069 (accel_gp) | yes |
| P2 | each of eight_nc, gp_pois_regr, lotka_volterra in [0.00, 0.05] | +0.003, **+0.064**, +0.039 (against nutpie −0.008, +0.007, +0.017) | **no** (gp_pois_regr) |
| P3 | initial-fast gradients per transition, oWALNUTS / CmdStan >= 1.5 | **1.24** (median; sblrc 7.1, arma11 4.1, arK 2.6, diamonds 2.6, hmm_drive_0 2.4) | **no** |
| P4 | slow windows in [1.0, 1.3] | 1.01 (windows 0.98 / 1.06 / 1.00 / 1.00 / 1.07; terminal 0.98; sampling 1.04) | yes |

How the three samplers spend their warmup:

- **oWALNUTS's spend per transition matches CmdStan's** everywhere except the first 75
  transitions. There, on five models, WP40's initial-phase pathology still costs 2–7x
  CmdStan's: dual averaging climbs to large steps while every leaf is fully refined.
  - The best-of-16 start search is 0.02 % of all gradients.
  - accel_gp is the exception the other way: 0.4–0.6x CmdStan in every phase, its
    reverse-check truncation (WP70).
- **nutpie's share barely moves** (0.47–0.54), because it spends warmup at sampling cost. Its
  stored mass matrix last changed at draw **849 of 1,000** on every chain, so the final 15 %
  is step-only. Its per-transition cost is similar before and after that point (within 30 %).
- **CmdStan's and oWALNUTS's shares** range from 0.25 to 0.68 with the model.
- **eight_schools_centered** is the outlier at 0.25 for oWALNUTS. Its retained transitions cost
  4.2x CmdStan's, so the share falls.

So at v7's defaults, warmup spend is not where oWALNUTS loses to CmdStan or nutpie on the house
models. WP58's 72 % vs 49 % on `hier` does not reproduce here. The lever is that every sampler
spends about half its budget on a warmup longer than these models need.

## The candidates (phase B, post hoc reading)

**`half`** (500 warmup: 75 / 25, 50, 100, 200 / 50):

- Warmup gradients are 0.58x and total gradients 0.80x the default's.
- Min bulk ESS is 1.03x (median model), and ESS per *sampling* gradient 1.06x.
- It gains on 14 of 17 models. It loses on earnings (0.88), sblrc (0.98) and hmm_drive_0
  (0.63, a stuck-chain realisation).
- Passes are 40 vs 40, but the composition changed: sblrc lost 730731 (bulk ESS 490, tail ESS
  397), and one_comp gained one.
- One passing cell has max |z| 4.99 (one_comp 730731, a model with known large z: WP64's largest
  passing value was 3.98). That is reported, not gated.
- On the funnel, at 1,000 / 20,000, it gives 0.0499 ± 0.0032.

**`init25`:**

- Its spend is unchanged: warmup 0.99x, total 1.00x, ESS 1.02x on the median model.
- Its pass comes from `hmm_drive_0`: 3/3 against the default's 1/3, with stuck chains at R-hat
  1.53 and 1.12 on 730732 and 730733.
- It also gains on nes2000 and arK (1.20–1.21).

One realisation per seed cannot separate a schedule effect from a different trajectory.

**`stablestop`:**

- It stopped 68 of 204 chains at 500 transitions: nes2000 10/12, arma11 8, kidiq and hmm 7.
  It never stopped on diamonds, accel_gp or sblrc.
- Its warmup gradients are 0.84x the default's.
- Every non-stopping chain is bit-identical to the default; for example, hmm_drive_0 730732 and
  730733 reproduce the default exactly.
- The funnel never stopped, and the funnel row is the default's.

## Recommendations (coordinator)

- **No default change from this study.**
  - `half` is the only candidate whose gain survives every robustness reading. The next step is
    a preregistered confirmation on fresh seeds, with a robust per-model statistic (see WP64)
    and the gates, of `warmup = 500` (or a 500-transition schedule) as a default.
  - That study should watch sblrc, one_comp and the hmm_drive_0 / lotka_volterra start
    pathologies.
- **Do not promote `init25` or `stablestop` on this evidence.** Each passes R2 on one or two
  models that the default gets wrong for unrelated reasons.
- **The frozen R2 statistic is fragile.** A geomean of seed-median ratios over models that fail
  their gates in every arm (eight_schools_centered), or that have stuck chains (hmm_drive_0),
  can carry a candidate. Future rules should restrict R2 to models the default passes, or use
  per-model medians over more seeds.
- **For the nutpie gap, look at the metric (WP71), not the spend.** Per transition, oWALNUTS's
  warmup equals CmdStan's, and its share equals nutpie's within 0.01.

## Reproduce

On the box, in `~/lanes/warmup_spend_v1/`:

- `setup.sh`, `clone.sh <bundle>`;
- `build_models.py 4` in the staging copy, models moved into the clone;
- `launch.sh`, which runs `run_all.sh`: build, `run_spend.py tests`, `run --phase=A/B/F`,
  `analyze`, `checksums.py`.

Everything ran under `taskset -c 4-7`.

The single run was 2026-10-26, 02:50–03:37 UTC, at study commit `fdafc5b8` (library `ed573c67`).

- All 306 posteriordb cells and 40 funnel cells were recorded. There were no reruns or
  amendments.
- One failure: nutpie `lotka_volterra` 730733 ended as `timeout_or_crash` (WP64 recorded the
  same crash). It counts against nutpie and leaves that model without a nutpie ratio.

Results are in:

- `artifacts/results-table.md` and `artifacts/summary.json`;
- `artifacts/tests.json` and the `test-*.log` files (R4: kernel_fingerprint 3/3 and
  stable_metric_stop 4/4 on Linux);
- `artifacts/funnel/`.

The library change is `WarmupConfig::with_stable_metric_stop` (research-only, off by default),
with `tests/stable_metric_stop.rs`. Raw draws (179 MB) and CmdStan CSVs stay on the box; the draws
are hashed in `CHECKSUMS.sha256`.
