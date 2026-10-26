# WP77: warmup schedule confirmation (`half`, `init25`)

**Verdict: neither candidate is proposed, and the default warmup (1,000, windows 75/25/50) stays.**

- **`half` (warmup 500)** fails two clauses:
  - G: 81 passes vs the default's 87;
  - H: the headline is 1.119, below 1.15.
- **`init25`** fails four clauses: H (1.016), M (0.988), L (0.980) and Z (5.85). It also misses F (t +1.03).
- WP73's `half` result did not replicate on fresh seeds. Its gain is warmup spend only: per sampling gradient `half` is 0.875x the default. On `hmm_drive_0` it costs badly, with a ratio of 0.356 and 3 of 6 passes against the default's 6.

The rule and design are in `PREREGISTRATION.md` and `protocol.json`, committed at `a1d3a738` before the first cell. Full tables are in `artifacts/results-table.md`, and machine-readable results in `artifacts/summary.json`.

## Rule outcomes (6 seeds 770771–770776, 17 models)

| clause | `half` | `init25` |
|---|---|---|
| G passes >= default (87/102) | **81, fails** | 87, holds |
| H headline ESS/total grad >= 1.15 | **1.119 [0.861, 1.224], fails** | **1.016 [0.914, 1.151], fails** |
| M per-model median >= 1.10 | 1.180, holds | **0.988, fails** |
| L leave-one-model-out min >= 1.05 | 1.098, holds | **0.980, fails** |
| D no new divergences | 0, holds | 0, holds |
| Z max passing \|z\| <= 4 | 3.38, holds | **5.85 (one_comp 770775), fails** |
| F funnel P5 within 1 s.e. of 0.0478 | 0.0487 ± 0.0048, holds | **0.0530 ± 0.0051, fails** |

- **Default:** max passing \|z\| was 5.39 (one_comp 770773), and its funnel P5 was 0.0513 ± 0.0060.
- **Default vs CmdStan:** 0.791 per total gradient and 0.829 per sampling gradient.
- **Per sampling gradient vs default:** `half` 0.875, `init25` 1.047.
- **vs CmdStan per total gradient:** `half` 0.889, `init25` 0.832.

## Predictions vs outcome

- **`half`:** I predicted it would fail on Z alone. It held Z and failed G and H.
- **`init25`:** I predicted it would fail H, M and L. It also failed Z and F.
- **Per sampling gradient:** I predicted `half` at 1.00–1.08. It came in at 0.875: the shorter warmup gives a worse-adapted retained kernel, not just a cheaper one.

## What did not change

No default change is proposed, so nothing changes in `src/sampler.rs`, the Python defaults, `ALGORITHM_REVISION` or the fingerprints.

## Run record

- **Where and when:** lane 2 (cores 4-7) of the shared box, co-tenanted, on 2026-10-26 from 03:59 to 05:03 UTC. Cells ran strictly sequentially, with no reruns or amendments.
- **Phase T:** both test suites passed (`artifacts/tests.json`).
- **Cells:** 408. All 306 oWALNUTS cells finished ok. One CmdStan cell errored (lotka_volterra 770773, a NaN in the ODE during sampling); CmdStan is descriptive only.
- **Checksums:** `CHECKSUMS.sha256` covers 923 files. Draws and cmdstan output are hashed but not committed, and stay on the box lane.
