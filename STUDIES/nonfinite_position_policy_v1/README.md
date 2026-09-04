# nonfinite_position_policy_v1 (WP38)

Status: **complete; frozen decision `NOT_QUALIFIED`; no default changed.**

Preregistered in [`PREREGISTRATION.md`](PREREGISTRATION.md) / `protocol.json`
(commit `ca1a5a5`), harness and manifest frozen at `2511a32`, evidence run
2026-09-04 in manifest order, one launch per cell, no reruns. Analysis in
`evidence/analysis.json`; the ledger paragraph is `LEDGER-ENTRY.md`.

## Question

Is the research-only `NonfinitePositionPolicy::RejectLeaf` (an overflowed
integrator position becomes a zero-density leaf instead of ending the run)
qualified as an explicit opt-in? Two arms differing only in the policy, on
the repaired state-space target at initial step 0.5 (24 fresh seeds) and on
two identity controls (funnel, 100-D Gaussian; 6 seeds each). 1,000 warmup,
1,000 retained, 4 chains.

## Result

| gate | registered rule | outcome |
|---|---|---|
| G1 identity (controls) | both arms complete, equal draw hash and call count, zero rejections; 12/12 | **pass** 12/12 |
| G2 completion | `reject` completes 24/24 | **pass** 24/24 |
| G3 informativeness | `abort` fails >= 1 cell with the nonfinite-position `Numerical` error | **pass** 2/24 (seeds 97216, 97224) |
| G4 health | every completed `reject` cell: R-hat <= 1.01, bulk ESS >= 400, tail ESS >= 400 on nine coordinates | **fail** 0/24 |
| G5 confinement | zero rejections in the retained phase | **pass** (3 rejections total, all in the initial fast warmup phase) |
| G6 consistency | where `abort` completed, `reject` is bit-identical with zero rejections | **pass** 22/22 |

Decision: `NOT_QUALIFIED` (G4 failed). Predictions P1, P2, P3, P5 held; P4
and P6 did not.

## Reading

G4 measured the target, not the policy. On the 22 seeds where both arms
completed the draws are bit-identical, so the `reject` arm's minimum bulk ESS
of 200–382 and maximum R-hat of 1.006–1.029 are exactly the `abort` arm's
numbers: the polyscope-canonical-v2 state space at T = 1000 does not reach
400 bulk ESS on its global coordinates in 1,000 draws under the sampler
defaults, with or without the policy. The two seeds that only `reject`
completed (min bulk ESS 343 and 257, max R-hat 1.023 and 1.012) sit inside
that same range. Nothing here distinguishes the policies on health, and
nothing here shows the policy harming health.

What the study does establish about the policy:

- the event is real on this target at the frozen initial step (2 of 24
  seeds; the diagnostic saw 2 of 13);
- `RejectLeaf` turns each such abort into a completed run, with one or two
  rejected leaves confined to the first 75 warmup transitions and none in the
  retained phase;
- when the event never occurs the policy is bit-identical to `Abort`, on 34
  of 34 such cells.

Under the frozen rule that is not a qualification. A renewed study must use
a *paired* health gate (the `reject` cell on an `abort`-failed seed must lie
within the distribution of the completed pairs), or a longer run on this
target, fixed before evidence, with fresh seeds.

Descriptive only: funnel `P(omega < -5)` pooled over the four chains was
0.005–0.060 per seed (exact 0.0478); at 1,000 retained draws per chain this
is not a tail-mass test and was not gated.

## Files

`PREREGISTRATION.md`, `protocol.json`, `manifest.json`, `Cargo.toml`,
`Cargo.lock`, `src/main.rs`, `run_study.py`, `evidence/{PROVENANCE.json,
process/,records/,logs/,analysis.json,RUN-COMPLETE.json}`, `LEDGER-ENTRY.md`,
`CHECKSUMS.sha256`. Build with
`RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release`.
