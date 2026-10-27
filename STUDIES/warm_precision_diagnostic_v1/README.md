# Fixed K=400 plus analytic scale quantiles is a candidate for further study

On one fresh sampler seed using the existing WP96 synthetic windows, analytic
scale-CDF quantiles at **K=400** are within the descriptive 2% P50 / 5% P95 bands
on 40/40 pre-shift and 39/40 post-shift ticks, and 40/40 ticks in both control
halves. Median sampler time is about **255 ms**; analytic quantile arithmetic
adds about **0.9 ms** in a separate measurement. This supports testing the
configuration further. **It is not a qualification result:** the data and
references were reused after their failures were seen, and only one new seed
was run. No library default or deployment decision changes.

## What ran

The [fixed plan](PLAN.md) and [protocol](protocol.json) were committed at
`42214fce` before launch. Six cells used the unchanged WP96 binary/source
(`9210c947`, before the WP90 trap-guard default), frozen tuning, K=200/400/800,
the two original 250-return windows and fresh diagnostic seed 99271021.
K increases within each stream's lane. The seeds pair initialization; later
states differ, so comparisons are not nested continuations at every tick.

Sampling ran from **2026-10-27 16:54:21.953907 to 17:23:55.720541 UTC**, a total
of 29 minutes 34 seconds, on cores 0–3 (shift) and 4–7 (control). WP97 references
shared the host on cores 8–15; no isolated-performance claim follows. All six
cells exited zero, with all **12,000 updates** and **480 scored rows** present.
No cell was rerun; neither the 60-minute deadline nor 1 GB output cap was hit.

## Descriptive accuracy

Counts are within both relative-error bands with no stuck chain, out of the
40 scored ticks in each half. “Noise” compares the original predictive-noise
estimator with its original-noise reference. “CDF” analytically integrates
future innovation on both the arm and the same finite reference draws.

| Stream | K | Noise half 1 | Noise half 2 | CDF half 1 | CDF half 2 |
|---|---:|---:|---:|---:|---:|
| Shift | 200 | 34/40 | 31/40 | 37/40 | 36/40 |
| Shift | 400 | 40/40 | 34/40 | 40/40 | 39/40 |
| Shift | 800 | 40/40 | 39/40 | 40/40 | 40/40 |
| Control | 200 | 35/40 | 34/40 | 38/40 | 38/40 |
| Control | 400 | 40/40 | 39/40 | 40/40 | 40/40 |
| Control | 800 | 40/40 | 40/40 | 40/40 | 40/40 |

Across the whole fixed diagnostic, original noise versus original reference is
446/480; original noise versus analytic reference is also 446/480 (not
necessarily the same passing rows); analytic versus analytic is 468/480.
All three comparisons, signed errors, error bands and own-MCSE summaries are
preserved in [the full results](analysis/results.json). There is no multi-seed
“all halves qualify” shortcut: these are descriptive counts on one seed.

The sole K=400 analytic failure is shifted tick 1,725: P50 error −2.78%, P95
error −2.43%. Thus the remaining miss is not eliminated by smoothing future
innovation. On the shifted second half:

| K | Noise median own-MCSE P50 / P95 | CDF median own-MCSE P50 / P95 | CDF signed mean error P50 / P95 |
|---|---:|---:|---:|
| 200 | 1.70% / 3.67% | 1.17% / 2.29% | +0.09% / +0.31% |
| 400 | 1.20% / 2.44% | 0.85% / 1.62% | −0.13% / −0.32% |
| 800 | 0.88% / 1.89% | 0.61% / 1.19% | +0.06% / +0.05% |

These are asymptotic, chain-aware uncertainty diagnostics, not stopping
guarantees. The separate Gaussian-chain diagnostic showed that such intervals
can under-cover for short, highly correlated chains. No adaptive draw budget
was selected here.

## Cost

Sampler statistics cover all 2,000 updates per cell, excluding the separately
recorded initial fit. CDF arithmetic is measured on the 80 saved scored ticks.

| Stream | K | Sampler median / P95 / P99 (ms) | CDF arithmetic median (ms) | Sampler + separate CDF median on saved ticks (ms) |
|---|---:|---:|---:|---:|
| Shift | 200 | 128 / 136 / 143 | 0.56 | 128.58 |
| Shift | 400 | 255 / 264 / 272 | 0.91 | 256.17 |
| Shift | 800 | 504 / 522 / 531 | 1.61 | 504.72 |
| Control | 200 | 128 / 138 / 144 | 0.58 | 127.93 |
| Control | 400 | 255 / 268 / 275 | 0.95 | 255.48 |
| Control | 800 | 502 / 519 / 531 | 1.67 | 504.03 |

The summed column is a sum of components measured at different times, **not a
fused resident online benchmark**. It excludes serialization and transport.
The original binary's timer covers target construction, remapping, warm
sampling and state extraction; writing compact draws is outside it. Both
estimators' MCSE work is recorded separately, about 1.1–1.5 ms median on the
shifted second half; it is not included in the arithmetic column.

The original-noise arithmetic reproduces the exact WP96 convention by
regenerating a 4x20,000 noise matrix even for smaller K. Its reported timing
is exact-replay implementation cost, not an optimized random-estimator lower
bound. CDF arithmetic includes transformation, bracketing and both root solves.

After confirming the supervisor and all six process groups had exited,
arithmetic analysis ran on cores 0–3 from **17:24:29.616757 to
17:24:45.905198 UTC** (16.29 seconds process wall), while remaining WP97
references continued. It did not overlap WP97's official pooling analysis.
The hard five-minute process cap was not approached.

## Integrity and limits

- All six initial fits kept all four chains. There were no stuck scored ticks
  and zero retained divergences over all 12,000 updates.
- The [recovery audit](artifacts/recovery-audit.json) finds no missing,
  duplicate, failed or malformed records. All **123 paired pre-shock compact
  files** (tick 0 through 1,000, for each K) are byte-identical across the two
  streams, as their shared data and seed imply.
- Reused reference bytes are pinned to the completed WP96 audit by
  [REFERENCE-MANIFEST.json](REFERENCE-MANIFEST.json). Reference selection and
  original-chain noise identities are retained. Every input hash is checked
  before/after use and again after analysis. All 160 scored references and
  480 warm rows are available; missing rows would remain in the denominator.
- Maximum analytic reference own relative MCSE is 0.177% P50 / 0.355% P95.
  These are finite same-sampler references, not exact or independent posterior
  ground truth. The maximum CDF root residual is 2.51e-12.
- Six local fixtures pass, including analytic Gaussian inversion, chain-index
  replay, invalid-reference fail-closed behavior and missing-row handling.
  An archived WP96 original-noise score was independently reproduced to
  less than 1e-12. Executed source snapshots are under
  [artifacts/execution](artifacts/execution/).
- The downloaded archive is 10,322,273 bytes, SHA256
  `154cd1703845d0ec605b8197e6a6f8caeb604f2b4a3cd4cd640d1b5deb87ad4f`.
  Its hash and executed source bytes were verified locally. Raw f32 draws stay
  uncommitted on local disk and the box; `CHECKSUMS.sha256` pins them.

This evidence supports **a candidate fixed K=400 plus analytic scale-CDF path**
for a fresh multi-seed study and a resident end-to-end implementation check.
It does not establish every-update accuracy, behavior during the first 24
post-shock updates, full-history posterior equivalence, real-market predictive
calibration or profitability. The quantity remains next-period latent scale,
not a return quantile, executable bid/ask or inventory-aware decision.

## Reproduction

`run.py` is the executed, single-use supervisor; the immutable execution
snapshot and hashes are also retained. Do not rerun existing output paths.
`run_analysis.py` records and caps the coordinated analysis invocation.
For read-only local verification with the raw cells present:

```text
python test_analysis.py
python checksums.py
```

`audit.py` refuses to overwrite its existing report. Reanalysis likewise needs
a fresh output path and the original WP96 reference tree; laptop arithmetic
timings must not replace the recorded box measurements.
