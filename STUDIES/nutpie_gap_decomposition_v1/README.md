# nutpie gap decomposition (WP80)

## Verdict

nutpie's per-gradient lead is a **sampling-phase cost per draw** (term B).
It is not warmup (C ≈ 0) and not ESS per draw (A < 0: oWALNUTS's draws are
*more* independent).

The cost splits into two mechanisms:

- **A smaller effective step (H1).** This is the one mechanism present on
  every model measured. It is **supported**: B1 is 0.35, 0.61 and 0.21 on
  sblrc, hmm_drive_0 and eight_schools_centered, and 2.62 on diamonds.
- **Refinement spend on eight_schools_centered (H4).** B4 is 1.38 there and
  about 0 on every other telemetry model, so H4 is **not supported** at
  2 of 3.

Under the preregistered rule (the mean over the three carrying models), B4
ranks first (0.46) and B1 second (0.39). The B4 mean comes from one model;
B1 is the consistent mechanism. P2 ("B1 first") therefore **failed** as
registered.

H3 (metric mismatch) is **not supported** at 2 of 3 (0.60, 0.33, −0.21). On
sblrc, however, oWALNUTS's 1/M is about 11x the posterior variance on the
betas against about 1x on sigma. That pattern is consistent with Stan-style
regularization flooring tiny variances, and on sblrc it explains the step
gap. H2 (distance per draw) and H5 (ESS per draw) are not supported.

## Part 1: 15 entering models, 18 seeds (cells on disk)

Logs are nutpie over oWALNUTS, a mean over paired ok seeds, with
G = A + B + C exactly. Over models: G 0.233 (×1.26), A −0.376, B **0.580**,
C 0.028.

| rank | model | WP76 (c) o/n | G | A | B | C |
|---:|---|---:|---:|---:|---:|---:|
| 1 | sblrc | 0.342 | 1.017 | 0.034 | 0.813 | 0.171 |
| 2 | eight_schools_centered | 0.607 | 0.656 | −0.210 | 1.139 | −0.273 |
| 3 | hmm_example | 0.634 | 0.458 | −0.268 | 0.551 | 0.175 |
| 13 | diamonds | 1.037 | −0.053 | −1.210 | 1.342 | −0.185 |
| 14 | one_comp | 1.207 | −0.162 | −0.597 | 0.410 | 0.025 |
| 15 | hmm_drive_0 | 0.484 | −0.932 | −1.734 | 0.552 | 0.250 |

The full table is in `artifacts/results-table.md`.

- **B is positive on 14 of 15 models.** oWALNUTS spends more sampling
  gradients per draw almost everywhere. accel_gp is the exception.
- **P1 failed** (predicted top three: sblrc, hmm_drive_0,
  eight_schools_centered). hmm_drive_0 drops to last because on 6 of 18
  seeds nutpie's min bulk ESS collapses (stuck chains). A mean of logs
  punishes that, while WP76's median does not. Its median G is +0.73.
- **The geomean on the mean-of-logs scale is ×1.26.** The ×1.43 figure is
  WP76's median-based (c).

## Part 3: telemetry, 24 cells, seeds 720701–3

Every cell is bit-identical to its WP72 / WP76 counterpart: 12/12
oWALNUTS and 12/12 nutpie.

| model | G | A | C | B4 | B1 | B2 | S_o − S_n |
|---|---:|---:|---:|---:|---:|---:|---:|
| sblrc | 0.968 | 0.014 | 0.141 | 0.005 | 0.349 | 0.460 | 0.598 |
| hmm_drive_0 | −0.502 | −1.476 | 0.197 | 0.010 | 0.608 | 0.160 | 0.329 |
| eight_schools_centered | 0.003 | −1.179 | −0.447 | 1.377 | 0.213 | 0.040 | −0.208 |
| diamonds | −0.165 | −1.301 | −0.188 | 0.000 | 2.621 | −1.298 | −1.508 |

The raw steps differ:

- **sblrc:** oWALNUTS 0.10 vs nutpie 0.66;
- **diamonds:** 0.0035 vs 0.062. oWALNUTS reaches depth 10 at about 970
  leaves per draw, against about 257 steps for nutpie.

Even so, oWALNUTS leads on diamonds through ESS per draw (A −1.30): nutpie
fails all 3 of its gates there.

**P3** (diamonds B1 < ln 1.25) **failed**.

## Ranked mechanisms

| rank | component | mean over carrying models | evidence |
|---:|---|---:|---|
| 1 | B4 refinement spend | 0.464 | eight_schools_centered only: about 4 gradients per leaf, and 30 % of transitions refined |
| 2 | B1 effective step | 0.390 | positive on all 4 models; H1 supported |
| 3 | B2 distance per draw | 0.220 | sblrc 0.46 only |
| 4 | C warmup | −0.036 | none (consistent with WP73) |
| 5 | A ESS per draw | −0.880 | favours oWALNUTS |

## Caveats

- Three seeds and four models.
- On hmm_drive_0 and eight_schools_centered nutpie's cells often fail their
  gates, so G there mixes efficiency with failure.
- Walls are "pinned, co-tenanted" and are not used here.

See `PREREGISTRATION.md`, `protocol.json` and `AMENDMENTS.md` (no
post-freeze amendments).
