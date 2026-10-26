# Diagonal metric shrinkage (WP81)

## Verdict

**Not supported. Keep `DiagonalMetricRegularization::Stan`.** No default
was flipped.

Neither research regularisation meets the frozen rule:

| candidate | headline (c) | median over models | LOMO min |
|---|---:|---:|---:|
| `StanLowAnchor` | 1.025 [0.997, 1.378] | 1.000 | 0.994 |
| `StanCoordinateCap` | 1.017 [0.990, 1.422] | 1.000 | 0.982 |

Both fail R2 (headline >= 1.10), R3 (median >= 1.05) and R4 (LOMO >= 1.00).
Both pass R1 (gates 41 vs 40), R5 (no new divergences), R6 (funnel) and R7
(fingerprints).

**Stan's 1e-3 anchor explains the step gap only where it binds:** sblrc,
where five coordinates are installed at 9.8–12.2x, and one diamonds
coordinate (4.3x). Elsewhere oWALNUTS installs 0.9–1.1x the posterior
variance, yet nutpie's raw step is still 1.3–19x larger on every one of the
17 models.

## Part 1: installed inverse mass / posterior variance (house 17, seeds 810101–3)

The ratio uses each cell's own retained draws, with each coordinate taken
as the median over chains, then over seeds. The full table, including
ratios against the posteriordb reference (15 models), is in
`artifacts/results-table.md`.

| model | oWALNUTS min..max (outside [0.5, 2]) | nutpie min..max (outside) | step o / n |
|---|---|---|---|
| sblrc | 1.00..**12.21** (5) | 0.45..0.98 (3) | 0.106 / 0.660 |
| diamonds | 0.93..**4.32** (1) | 0.01..1.00 (7) | 0.0033 / 0.062 |
| eight_schools_centered | 0.76..1.07 (0) | 0.25..0.52 (8) | 0.18 / 0.43 |
| hmm_drive_0 | 0.21..1.04 (1; reference 0.94..1.13) | 0.68..0.99 (0) | 0.61 / 0.79 |
| accel_gp | 0.67..1.13 (0) | 0.02..0.39 (66 of 66) | 0.0082 / 0.047 |
| other 12 | 0.89..1.08 (0) | down to 0.03 | nutpie 1.3–8.6x larger |

**nutpie's metric is not near 1.** Its gradient-informed diagonal installs
**below** the posterior variance on most models, as low as 0.01–0.03x. It
nonetheless takes larger steps.

- **D1 (coordinator) failed.** nutpie is outside the band on sblrc,
  eight_schools_centered and diamonds.
- **D1b failed** on one sub-claim. hmm_drive_0 has one coordinate at 0.21
  against its own draws, a stuck-chain artefact: against the reference it
  is 0.94–1.13.

So the step gap (WP80 B1) is not, in general, an over-stated metric. The
regularisation explains sblrc and part of diamonds. The rest lies in the
step adaptation and the metric's scale, not in coordinate-wise shrinkage.

## Part 2: the candidates against the frozen rule

| criterion | `lowanchor` | `coordcap` |
|---|---|---|
| R1 gates /51 (default 40) | 41, held | 41, held |
| R2 headline >= 1.10 | 1.025, **failed** | 1.017, **failed** |
| R3 per-model median >= 1.05 | 1.000, **failed** | 1.000, **failed** |
| R4 LOMO min >= 1.00 | 0.994, **failed** | 0.982, **failed** |
| R5 no new divergences | held | held |
| R6 funnel mean within 1 s.e. of 0.0478 | 0.0502 ± 0.0043, held | 0.0499 ± 0.0043, held |
| R7 fingerprint, flags off | held | held |

- **Where they differ from the default.** Each candidate is bit-identical
  to the default on 27 of 51 cells. It gains on sblrc (1.67x / 1.79x) and
  on diamonds (1.16x for `lowanchor`, 0.92x for `coordcap`).
- **Where they lose.** Both lose on earnings (0.73x / 0.88x).
- **Funnel.** The funnel divergences are the same in all three arms; the
  default funnel mean is 0.0502.
- **Predictions.** C1–C5 held.

## Caveats

- Three seeds.
- `owalnuts-*` ratios on multimodal hmm_drive_0 depend on stuck chains.
- Walls are "pinned, co-tenanted" and are not used.
- Amendment A-1 cached cell reads in the analysis (performance only).

The library change (`f52537a1`) adds research-only variants and leaves the
default bit-identical. See `PREREGISTRATION.md`, `protocol.json` and
`AMENDMENTS.md`.
