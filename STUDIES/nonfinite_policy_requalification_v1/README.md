# WP54 — nonfinite-position policy default-flip confirmation (`nonfinite_policy_requalification_v1`)

## Verdict

**Supported: the frozen rule passes and `RejectLeaf` is now the
`sampler::Tuning` default.** On all 73 cells that `Abort` completed,
`RejectLeaf` gave bit-identical draws and per-chain target-call counts. It
completed 75 of 79 runs; `Abort` completed 73. The two extra runs are the
known WP50 fatal case (sblrc, seed 50801734), run with the house library and
again with the exact WP50D/E static library. In both, one chain's
warmup overflow killed the whole 4-chain run under `Abort`. Under
`RejectLeaf` it became one rejected leaf, and the run passed every gate
(max |z| 1.63, R-hat 1.0035, bulk ESS 760). The funnel check passes under both
arms with identical draws.

The number that matters: **73/73 bit-identical; 75 versus 73 runs completed.**

The evidence for a benefit is narrow, and it is fair to say so. Both rescues
are one seed that was not fresh (a declared targeted replication). On 26
fresh-seed stress pairs and 51 fresh house pairs the event never happened:
zero nonfinite rejections, so the two policies were bit-identical. The flip
costs nothing on any run measured and saves the run in the case where the
event happens.

Preregistration `PREREGISTRATION.md` and `protocol.json` were committed at
`a840bb9f` before the first evidence cell. All 158 cells ran once, in
manifest order, and none were rerun. Evidence commit: `22b869d5`.

## Why `RejectLeaf` was research-only

WP38 (`STUDIES/nonfinite_position_policy_v1`) tested `RejectLeaf` only as an
opt-in, and its frozen decision was `NOT_QUALIFIED`. The policy passed
identity (12/12), completion (24/24) and bit-identity (22/22). It failed the
health gate 0/24: 400 ESS and R-hat 1.01 on nine coordinates of the
polyscope-canonical-v2 state space in 1,000 draws. On 22 of 24 seeds the draws
were identical to `Abort`'s, so that gate measured the target's mixing, not
the policy. The ledger kept `Abort` as the default and asked for a renewed
qualification with a gate that tests the policy. This study is that renewed
qualification.

## Design

There are two arms: `abort` = `Tuning::default()`, and `reject_leaf`, which is
the same with `.nonfinite_position(RejectLeaf)`. Everything else is the shipped
sampler default, run through the reused WP48 harness:
- diagonal metric, default adaptation;
- `Init::uniform()` at the shipped radius;
- 4 chains x 1,000/1,000, 4 threads;
- `ReplicatedStanTarget` with construct seed 1.

The 17 compiled house models were copied from
`owalnuts-wt/dense-metric/STUDIES/dense_metric_posteriordb_v1/models`, built
from the same posteriordb sources. The WP50 static sblrc library and its
`tbb.dll` were copied from
`owalnuts-wt/windows-native-root-cause/.../bridgestan_windows_root_cause_v3/build/static`.
Their SHA-256 values match the WP50E protocol. Reference draws come from
posteriordb `28f8d3d`.

| block | pairs | seeds | result (abort / reject_leaf) |
|---|---:|---|---|
| S1 sblrc, house library | 1 | 50801734 (targeted) | **aborted** (chain 2, transition 9) / **ok, all gates**, 1 rejection |
| S1 sblrc, WP50 static library | 1 | 50801734 (targeted) | **aborted** / **ok, all gates**, same draw hash `5d7e4a62b998da28` as WP50E |
| S2 lotka_volterra, WP48 seeds | 3 | 148101–148103 (targeted) | 148101 timeout / timeout; 148102, 148103 ok, identical |
| S3 sblrc fresh | 10 | 5402101–5402110 | 10/10 ok, all gates, identical, 0 rejections |
| S4 lotka_volterra fresh | 10 | 5403101–5403110 | 7 ok (5 pass gates), 3 timeouts in **both** arms, identical |
| F funnel 4 x 2,000/20,000 | 3 | 5404101–5404103 | z +0.14, +0.59, -0.02 in both, identical |
| H house 17 models | 51 | 5401101–5401103 | 51/51 ok in both; 41/51 gates in both; identical |

The full per-pair table is `artifacts/results-table.md`. Per-cell JSON is in
`artifacts/cells/`, and `artifacts/summary.json` has the decision and the
predictions.

House statistic: the geomean of min bulk ESS per gradient is 3.525e-3 in
both arms, a ratio of exactly 1.000. The gate failures are the same in both
arms, because the draws are identical:
- `eight_schools_centered` 0/3;
- `accel_gp` 0/3;
- `one_comp` 1/3;
- `gp_pois_regr` 2/3;
- `lotka_volterra` 2/3 (seed 5401101 R-hat 1.51).

## Decision rule (frozen) and outcome

| criterion | outcome |
|---|---|
| D1 bit-identical on 100 % of completed-abort cells | **pass** 73/73 (draw hash, per-chain calls, 0 rejections) |
| D2 reject_leaf completes strictly more runs | **pass** 75 vs 73 |
| D3 no rescued run with max abs z > 4 that passes every other gate | **pass**: 2 rescues, max abs z 1.63, all gates pass |
| D4 funnel passes under reject_leaf | **pass** (abs z <= 0.59) |
| every cell recorded | 158/158 |

**Flip: yes.**

## Predictions

- **P1 held.** `reject_leaf` completed every run `abort` completed.
- **P1b failed, as I predicted it would.** `reject_leaf` rescued both
  nonfinite-position aborts but none of the four lotka_volterra timeouts
  (148101, 5403104, 5403107, 5403110). Those are stalls that the policy cannot
  touch; they timed out in both arms.
- **P2 held** (73/73).
- **P3 held.** Stress gates: reject_leaf 19, abort 17.
- **P4 held.** Max |z| on the rescued runs was 1.63.
- **P5 failed, as predicted.** The rescued runs have **0** retained
  divergences. Their single rejection is at warmup transition 9, in the
  initial fast window, so a user is not warned through the divergence count.
  The event is visible only in `WorkTotals::nonfinite_position_rejections`
  (warmup partition).
- **P6 held.**

## Side findings (not part of the rule)

- Under the default diagonal path, lotka_volterra stalls on 4 of 13 seeds
  (the WP48 seed 148101 and 3 of 10 fresh seeds) past 900 s. The completed
  cells take 35–70 s. Two more fresh seeds and one house seed complete with
  R-hat 1.04–1.59. That is a frozen-chain or stall defect at the defaults,
  independent of this policy, and it is the dominant lotka_volterra failure
  mode.
- The WP48 literal-dense lotka losses were `ErrorKind::Target` "current
  position is not evaluable", not the nonfinite-position path. This policy
  does not address them.
- The house-built and WP50 static sblrc libraries give bit-identical draws.
  This holds both on the smoke seed and on 50801734.

## Implementation (after the rule passed, as preregistered)

- `sampler::Tuning::default()` uses `NonfinitePositionPolicy::RejectLeaf`.
  `Tuning::nonfinite_position`, `KernelTuning::with_nonfinite_position` and
  the `sampler::NonfinitePositionPolicy` re-export are no longer behind the
  `research` feature, so `Abort` can be requested.
- `walnutpie::KernelTuning::default()`, the frozen `v10` replay tuning pinned
  by `tests/kernel_fingerprint.rs`, keeps `Abort`.
  - `ALGORITHM_REVISION` is unchanged, because no run that produced draws
    produces different draws (D1).
  - The fingerprints are unchanged, and `tests/kernel_fingerprint.rs` was not
    edited.
- `tests/nonfinite_position_policy.rs` is now ungated. It checks the new
  defaults and adds a default-tuning completion test.
- The `tests/sampler_api.rs` helper that mirrors `Tuning::default()` as a
  `KernelTuning` now sets `RejectLeaf`. `ChainOutput` equality includes the
  tuning, and the draws were already equal.
- `cargo test`: 254 passed (`artifacts/cargo-test.log`).
  `cargo test --features research`: 276 passed
  (`artifacts/cargo-test-research.log`).

## Anomalies and limits

- Wall-clock numbers are contended: up to six sibling agents shared the
  machine.
- The worktree is based on `3924b090`. It does not contain `main`'s
  `d8c3cef3`, which zeroes the gradient buffer on Windows direct replicas.
  WP50E showed that buffer is discarded for zero-density points, so it does
  not affect trajectories.
- The study ran about 3.3 h, mostly lotka_volterra timeouts (8 x 900 s).

## Reproduce

```
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release   # in this directory
uv venv --python 3.11 .venv && uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 numpy==2.4.6 posteriordb
.venv/Scripts/python.exe run_study.py analyze     # the single run already happened
python checksums.py
```
