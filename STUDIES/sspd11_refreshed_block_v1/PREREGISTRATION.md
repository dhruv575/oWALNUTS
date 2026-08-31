# Preregistered boundary-refreshed path-block study (WP16)

Frozen before execution on 2026-08-31, after implementing
`sample_chains_structured_refresh` (`STRUCTURED_REFRESH_REVISION =
walnutpie-structured-metric-refresh-v1`, kernel `ALGORITHM_REVISION` v10).
Follows `wiki/research-program-2026-08-31.md`; supersedes nothing.
WP12 context: arm P (one-shot posterior-precision path block at data-informed
start globals, globals diagonal borrowed from arm I) passed 2/3 seeds at
4×500/2,000 with one single-functional R-hat miss of 0.0002 and 2.7× arm I's
ESS per call. WP4b recommended refreshing the block from adapted globals at
slow-window boundaries.

## Design

Fixture `sspd-11` (SHA-256 `2fff97663b6e7946e64e465610ebf9dd4350d6615ecaa5aa513ff070b683baad`),
`polyscope-canonical-v2` in a=1 coordinates, WP12's starts rule and sampler
settings (4 chains, 4 threads, depth 8, refinement 3, max error 1.0, initial
step 0.02 unless `protocol.json` copied a different WP12 value — the protocol
file is authoritative and is generated from WP12's before any sampling),
dual-averaged step at target acceptance 0.8 with the default initial step
search.

Arms, each at 500/2,000 AND 500/4,000 retained draws:

- **I** — identity initial diagonal, diagonal mass adaptation
  (`sample_chains`); WP12's arm I.
- **P** — WP12's arm P verbatim: fixed `StructuredBlockMass([globals diag from
  arm I same seed/draw-count, BidiagonalCholesky path block at data-informed
  start globals])`, mass adaptation off (`sample_chains_structured`).
- **R** — boundary-refreshed: initial mass = identity globals block + the same
  data-informed path block; at every completed slow-window boundary the
  refresh rebuilds the globals block from the window's regularised precision
  and the path block from `path_precision(data, window-mean globals)`
  (`sample_chains_structured_refresh`, default `StructuredRefreshConfig`:
  minimum 2 samples, restart dual averaging on install). Self-contained: no
  arm-I input.

Sanity cell (report-only, no gate): fixture `sspd-05`, seed 94001, 500/2,000,
arms I and R.

## Seeds

Fresh: 94001, 94002, 94003 (verified absent from every ledger and study;
WP17 holds 95001–95003). No reserved seeds. Each arm × draw-count × seed runs
once. Zero-callback preflight before every arm; per-arm-seed wall cap 900 s.

## Gates (per run; WP12's, unchanged)

Rank-normalised folded split R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on the
eight functionals (mu, sigma_x, alpha, beta, gamma, nu, x_terminal,
x_path_mean); zero retained divergences / invalid evaluations / refinement
exhaustions; maximum-depth rate ≤ 1%. Agreement: arms P and R against arm I
(same seed and draw count) and against the WP4b NumPyro a=1 reference
(seed 86001 artifact, cited by hash in `protocol.json`) within 3 combined
MCSE on every functional. Confirmation rule per arm and draw count:
**all three seeds pass every gate**.

## Preregistered predictions

1. Arm R installs at least one metric per chain on every seed with zero
   `RefreshFailed` / `DimensionMismatch` outcomes.
2. **Primary:** arm R passes all gates 3/3 at 4×500/4,000.
3. At 4×500/2,000, arm R's worst gated R-hat ≤ arm P's on ≥ 2 of 3 seeds.
4. Efficiency: arm R min-bulk-ESS per retained target call within
   [0.8, 1.6] × arm P (same seed/draws) and ≥ 2 × arm I.
5. Arm P passes 3/3 at 4×500/4,000 (WP12's run-length hypothesis).

## Outcome classes

Confirmed (R 3/3 at 4,000 with predictions 1 and 4 holding), partial (R 3/3
at 4,000 but efficiency band missed), or negative (any gate failure pattern);
all three are reportable. Deviations (wall-cap trims, reruns) are recorded
here before any evidence claim.
