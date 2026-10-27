# Resident full predictive summaries: host development result

2026-10-27. Four-update synthetic implementation/cost smoke, not qualification.
All four planned N250/K400 updates completed with checked full-return summaries.
Conservative GH64/128 integration dominates complete refresh cost: approximately
2.45seconds per update, of which native sampling is approximately0.24seconds.
This exceeds the inherited0.4second research benchmark. An economic latency
requirement has not been established, so this is not proof that an AMM is
impractical or unprofitable.

| Update | Complete tick (s) | Native refresh (s) | Summaries and transport bookkeeping (s) |
|---|---:|---:|---:|
|1|2.44015|0.23812|2.20162|
|2|2.45286|0.24030|2.21205|
|3|2.45256|0.24136|2.21070|
|4|2.46284|0.24246|2.21988|

Preparation/window remap cost0.41?0.51ms. Complete tick is measured directly;
JSON/disk persistence is outside that timer and reported separately. Summary time
includes compact-value copy and record assembly as well as scale/return arithmetic.
Imports/tests/JIT/initial fit are excluded from tick latency but included in the
14.799second externally supervised envelope. Initial fit took2.148seconds;
target/functional compilation took0.536seconds. Six focused tests passed first.

All64/128 cross-order CDF discrepancies were <=1.446e-13; normalized return endpoint
discrepancies were <=9.584e-17. These observations do not validate a globally lower
quadrature order. No GH reduction or further cells were run. Retained refresh
transitions had zero divergences among6400transitions; this is not posterior
accuracy evidence. There was no independent posterior reference fit.

Actual Python process peakRSS was244,850,688bytes (Linux getrusage). It includes
imports/JIT/initial fit and the workload; it is not a per-tick memory increment.
The native build and smoke used cores0?3 of the existing CPU c7a.4xlarge. WP97's
official timing had ended17:36:42UTC; its remaining untimed audit/archive could
overlap. These are four descriptive timings, not a latency distribution.

## Exact scope and provenance

N250, four chains, K400, depth10, refinement cap8, zero appended innovation/mass1,
stationary-boundary remap, frozen adaptation, joint(mu,log_sigma,beta,h_last) outputs.
Synthetic change enters update2; the three early post-change outputs are preserved.
The255th generated observation is an unused saved next-return label. This is not
the long-horizon drift experiment. New development initialization, data/seeds,
public session seed schedule, current native build and explicit trap guard differ
from WP96. No old study verdict changes and no forecast/market calibration claim.

Root native source:4c9320f2a11186a8c86eaf5b0827220677439617,74-file immutable archive
82caa37b1a670a7cf6c0972250e6fc5fd64a580a7c81fedc735ca2574407ffe8.
Rust/cargo1.88.0,maturin1.15.0; release/locked/no Python default features,
root research enabled, candidate-levels10 and Stan disabled. Build completed in
226.672seconds at17:42:02UTC. Native extension SHA256:
`db2c445a7a94da67d55d22d3b367c44544630655f07c88068e5456a2c7d93863`.
Wheel SHA256:`b64b1f2aed4bd58e585a9679a67e5840fba971ccf9985cdd85054544e60a1211`.
Dependencies, toolchain, feature tree, native identity and source manifest are in
`build/`. The original downloaded prep archive including wheel remains in the
own-worktree `target/resident-build-prep/prep-evidence.tar.gz`; binary wheel is not
duplicated in this tracked packet.

Attempt01 at17:43:41UTC failed before tests/sampling: resolving the venv interpreter
symlink selected systemPython without NumPy. All four updates never started; the
0.165second failed envelope is preserved in `attempt01/`. Parent explicitly
authorized one infrastructure-corrected retry with identical data/seeds/settings.
Only supervisor interpreter-path normalization changed: frozen corrected source
2a6d1cc6; archive6da06a250756b2e2ee58a778d651022b61668a9dec2184a104ebed4a6a45528a.
A subprocess preflight verifies exact venv executable/prefix and native hash.
Attempt02 started17:45:23UTC and completed17:45:38UTC, all four rows ok, no missing
or interrupted updates. Both supervisors verify owned process groups drained.

`attempt02/run/outputs/` contains unmodified result, inputdata and four compact
NumPy arrays. Raw compact hashes agree with their exact run records. The initial
per-chain diagnostic-array field is null because that key was absent from the
sample-result dictionary; initial parameter summaries/configuration/metadata are
preserved, and all retained refresh diagnostics/work counters are present. Do not
interpret missing initialization diagnostics as a clean diagnostic result.

Downloaded archive SHA256 values:

- Prep:fb2baa3a28b90a9a84d0a12d5019e98abcc442aa2c473307870377748daf6707
- Attempt01:81a647a823225cde703c94cbd93f9ae26adeab1fb1b00f6faab0bd4379bd871c
- Attempt02:201440175f52a80b6edb4e201fcb69bc1d1932cf13b4ff84c03c5c93881a1991

All original outputs are byte-preserved. CHECKSUMS.sha256 covers this packet except
itself. No additional compute or changed candidate settings follow from this result.
