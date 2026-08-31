# sspd-11 refreshed path block (WP16)

Preregistered evaluation of the new boundary-refreshed structured-metric
driver (`sample_chains_structured_refresh`,
`STRUCTURED_REFRESH_REVISION = walnutpie-structured-metric-refresh-v1`,
kernel v10) against WP12's arms on the T=1000 canonical-v2 fixture
`sspd-11`, a=1 coordinates, fresh seeds 94001–94003, 4×500/2,000 and
4×500/4,000. Protocol/gates are WP12's; see `PREREGISTRATION.md`,
`protocol.json`, `artifacts/RESULTS.md`, and `CHECKSUMS.sha256`.
Facade sources at commit `b413c88`; runner binaries were built from that
exact source (the runner's `kernel_commit` label reads `d8617a8-dirty-wp16`
because the feature commit landed while the runs were queued — `git diff
b413c88 -- src` of the build tree is empty).

## Headline results

| draws | arm | pass | worst gated R-hat range | min bulk ESS | ESS/retained call vs I |
|---|---|---|---|---|---|
| 2,000 | I identity + adapted diagonal | **3/3** | 1.0012–1.0082 | 805 | 1.00× |
| 2,000 | P one-shot path block (WP12) | 2/3 (94003: 1.0170) | 1.0063–1.0170 | 600 | 2.2–2.8× |
| 2,000 | R boundary-refreshed block | 2/3 (94001: cap 1.38%, R-hat 1.0198) | 1.0023–1.0198 | 395 | 0.9–1.1× |
| 4,000 | I | **3/3** | 1.0005–1.0016 | 1,856 | 1.00× |
| 4,000 | P | **3/3 — confirmed** | 1.0030–1.0070 | 1,142 | 2.2–2.3× |
| 4,000 | R | 2/3 (94001: cap 1.26%) | 1.0011–1.0050 | 591 | 0.6–1.1× |

Zero divergences, invalid evaluations, and refinement exhaustions in every
cell; agreement with arm I (same seed) and the WP4b NumPyro reference held in
every arm/seed (max |z| 2.33). Sanity `sspd-05` (seed 94001, report-only):
both I and R healthy, zero caps.

## Predictions (preregistered → outcome)

1. R installs with zero refresh failures — **held** (16/16 installs per
   run, zero `RefreshFailed`/`DimensionMismatch`).
2. Primary: R confirmed 3/3 at 4,000 — **failed** (2/3; seed 94001 cap
   1.26%).
3. R worst R-hat ≤ P at 2,000 on ≥2 seeds — **failed** (1/3).
4. R ESS/call within [0.8, 1.6]× P and ≥2× I — **failed** (R/P
   0.25–0.52, R/I 0.58–1.11).
5. P confirmed 3/3 at 4,000 — **held** (WP12's run-length hypothesis:
   its single 0.0002 R-hat miss at 2,000 was run length, not pathology).

## Interpretation

**Positive (product-facing):** the fixed one-shot posterior-precision path
block (arm P) is now confirmed on three fresh seeds at 4×500/4,000 with
≈2.2× arm I's ESS per call and ≈2.6× less wall time — the confirmation WP12
said was required before any product claim. Note P still consumes arm I's
adapted globals diagonal; a production deployment would run I once (or use a
calibrated globals diagonal) before P.

**Negative (this study's own mechanism):** rebuilding the block at every
slow-window boundary from that window's Welford summary (arm R) is worse
than building it once, on every measure. Telemetry shows why: early windows
are sampled while the step is still small and the globals mix slowly, so the
window variance of a global can be badly underestimated — seed 94001 chain 2
installed a globals block with momentum-covariance (precision) entries up to
≈2,000 in windows 1–3, pinning that global; its boundary step searches then
oscillated (0.086 → 0.0069) and the chain kept a 5% depth-8 tail after the
freeze. The one-shot P avoids this because its globals diagonal comes from a
fully adapted arm-I run, and its path block built at data-informed start
globals is evidently close enough. The machinery (installation seam, RNG/
cache invariance, telemetry) behaved exactly as specified; the *policy* is
what failed.

## Next decision

Do not adopt per-window refresh as a default or product path. Candidate
follow-ups (not preregistered here): refresh only at the final slow-window
boundary (one rebuild from the longest window, keeping R self-contained);
or keep arm P with a calibrated globals diagonal. Machinery stays in the
facade as an opt-in driver — it is the right substrate for either policy.

## Reproduce

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --fixtures sspd-11 --arms I,P,R --retained 2000 --seeds 94001,94002,94003 --out artifacts/run-2000 --kernel-commit <sha>
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --fixtures sspd-11 --arms I,P,R --retained 4000 --seeds 94001,94002,94003 --out artifacts/run-4000 --kernel-commit <sha>
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --fixtures sspd-05 --arms I,R --retained 2000 --seeds 94001 --out artifacts/sanity --kernel-commit <sha>
python analyze.py
python checksums.py
```

`artifacts/smoke/` is a labelled non-evidence smoke (seed 9999, 150 draws).
Raw draw files (`draws/*.f64`) are hashed in `CHECKSUMS.sha256` and not
committed. No wall cap was hit; the only deviation from the preregistration
is the kernel-commit label noted above.
