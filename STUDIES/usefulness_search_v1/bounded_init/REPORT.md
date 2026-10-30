# Bounded gradient initialization: screen fails

All 78 cells completed once in 491.56 seconds; source hashes unchanged and process
groups drained. Nine targeted library tests and the exact-control/clipping preflight
passed. The candidate uses the existing research feature with masses clipped to
[0.1,1000], keeps the shipped restart guard, and changes no sampler source/default.

| Model | Default passes | Unbounded passes | Bounded passes | Median bounded/default ESS per target call |
|---|---:|---:|---:|---:|
| HMM drive | 4/4 | 4/4 | 4/4 | 1.690 |
| Lotka--Volterra | 4/4 | 3/4 | 3/4 | 0.965 |
| Acceleration GP | 0/4 | 1/4 | 0/4 | 0.788 |
| Radon | 0/4 | 1/4 | 2/4 | 1.466 |

The frozen four-model efficiency statistic is 1.172, and SV median warmup calls
fall to 0.852 of defaults. These do not rescue the quality failure: Lotka loses a
pass, and GP falls below the 0.90 efficiency floor. Ratios include failed cells
as preregistered and must not be advertised as qualified performance gains.
SV has zero frozen-census traps in 32 chains per arm. Candidate funnel tail z
scores are -0.972 and +1.369 (the two-seed check passes but has limited power).
Overall frozen verdict FAIL; no promotion or broader default-flip study.

The Lotka failure (seed 939100003, chain 1) is substantive: R-hat 1.350, minimum
bulk ESS 9.19, minimum tail ESS 21.62, no divergences. Its last-warmup median log
density is -176.80, versus roughly -137 for the other chains, but it moves with
coordinate SDs 0.28--0.47 and a final step 0.143. Its step at transition 99 is
0.126, above the ensemble median 0.050; the step-ratio guard correctly does not
classify it as a frozen chain. No new zero-movement guard is justified here.

A subsequent exact parity audit proves all four chains' bounded and unbounded
samples, starting masses, starts and total target calls are identical in this
cell. Clipping never activates. Extreme starting masses therefore do not explain
this failure. The parity audit is a Git-recorded sidecar whose two input hashes
refer to immutable raw files in the main archive; it was computed after the
archive's file inventory was frozen. Basin density alone does not establish basin
probability, so blindly restarting the low-density chain would not prove accuracy.

Analysis uses the historical WP94 parameter tiers: reference parameter sets when
available, otherwise the full parameter block (radon has no posteriordb reference).
Reference discrepancies are descriptive, not a substitute for qualification. The
first analysis incorrectly assumed every model had a reference and stopped on
None.json.zip; analyze_v2.py corrects this without rerunning inference. Setup and
preflight-indexing mistakes are also retained, as documented in README.md.

The complete evidence archive preserves source, three binaries, data/model source,
reference inputs, all cell results/telemetry, supervision, preflight and failed
analysis. Exact-version S3 restore and per-member verification are recorded in
archive/S3-VERIFICATION.json. Original EC2 files remain; goal remains active.

Next reviewed direction is a sequential ensemble independence-MH move that can
propose other basins with the full proposal correction. Its derivation and
required known-target/independent-ensemble tests are in ../ensemble_moves/DESIGN.md.
This is established MCMC methodology, not a claimed novel result or a shortcut
around this failed screen. No further bound sweep is justified by this evidence.
