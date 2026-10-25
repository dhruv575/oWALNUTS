# WP54 preregistration: should `RejectLeaf` become the default nonfinite-position policy?

Frozen before the first evidence cell together with `protocol.json`, the
harness (`src/main.rs`, `src/bin/funnel.rs`, `run_study.py`) and `Cargo.lock`.
Default-flip confirmation study (the coordinator's task says so); baseline
`3924b090` (`wt/rejectleaf`).

## Why `RejectLeaf` is research-only today (history)

- `STUDIES/sspd_target_fatal_diag_v1` found that the WP37B state-space stop
  was partly a kernel nonfinite-position abort (an integrator overflow in the
  first warmup transitions at initial step 0.5). `NonfinitePositionPolicy`
  was added with `Abort` (the frozen `v10` behaviour) as the default and
  `RejectLeaf` behind the crate's `research` feature (CHANGELOG, "Research-only
  `NonfinitePositionPolicy`").
- WP38 (`STUDIES/nonfinite_position_policy_v1`, 2026-09-04) asked only whether
  `RejectLeaf` qualified as an explicit opt-in. Frozen decision
  **`NOT_QUALIFIED`**: G1 identity 12/12, G2 completion 24/24, G3 (abort fails
  >= 1) 2/24, G5 confinement and G6 bit-identity 22/22 all passed, but the
  **G4 health gate failed 0/24** (R-hat <= 1.01, bulk/tail ESS >= 400 on nine
  coordinates of the repaired polyscope-canonical-v2 state space in 1,000
  draws). The README and ledger say G4 measured the target's own mixing, not
  the policy: draws were bit-identical to `Abort` on the 22 seeds where both
  completed, and the two rescued cells lay inside the same range. The ledger's
  next decision: "`Abort` stays the default everywhere; `RejectLeaf` remains
  research-only and undocumented as supported. A renewed qualification needs a
  fresh preregistration with a paired health gate ... fresh seeds, and no
  other change." `wiki/decisions.md` records it as "not qualified — health gate
  measured the target, not the policy"; `wiki/findings/kernel-correctness.md`
  lists `Abort` as the default and `RejectLeaf` as research-only.

So the policy was never rejected on evidence against it; it was left
research-only because one preregistered gate was unpassable on that target.
This study is the renewed qualification, on the house screen, with a rule
that tests what the policy can change.

## New evidence since WP38

- WP50D (`bridgestan_windows_root_cause_v4`): 1/1,000 static-runtime sblrc
  children failed with `Numerical` "kernel attempted a nonfinite target
  position (chain 2, transition 9)", seed 50801734.
- WP50E (`_v5`): that error is deterministic (9/9 replays); chain 2 starts
  at log density -701,443, the initial fast window drives the step to 2.66,
  and at transition 9 the last coordinate overflows to -inf. Under `Abort`
  one chain's warmup overflow kills the whole 4-chain run; under `RejectLeaf`
  both dispatches complete with bit-identical draws and one rejection.
- WP48 (`dense_metric_posteriordb_v1`), lotka_volterra: the default-diagonal
  arm lost seed 148101 to the 2,700 s timeout (stalled starts, in every arm);
  the literal `Metric::dense()` arm lost 148101–148103 to `ErrorKind::Target`
  "current position is not evaluable: stan exception ... lognormal_lpdf:
  Location parameter[17] is nan" at transition 0. **Neither is the
  nonfinite-position path** (`walnutpie.rs` raises that as a separate
  `Target` error). This study's default-config harness cannot reproduce the
  literal-dense error, so S2 re-runs the three seeds under the house default;
  I expect `RejectLeaf` to change nothing there (see P1b below).

## Design (details in `protocol.json`)

Arms: `abort` = `Tuning::default()`; `reject_leaf` =
`Tuning::default().nonfinite_position(NonfinitePositionPolicy::RejectLeaf)`.
Everything else is the shipped sampler default exactly as the WP48 `diag`
arm (the WP48 harness, reused): `Metric::diagonal()`, `Adaptation::default()`,
`Init::uniform()` at its shipped radius via `uniform_starts`,
`Limits::admit_worst_case()`, 4 chains x 1,000/1,000, 4 threads,
`ReplicatedStanTarget` (construct seed 1, default preload). The harness
crate enables `owalnuts/research` only to reach the setter; it changes no
default. Within each pair `abort` runs first, then `reject_leaf`, same seed.

Strictly sequential manifest (79 pairs, 158 cells):

| block | cells | seeds | fresh? | timeout |
|---|---|---|---|---|
| S1-replication-house | sblrc x 2 arms | 50801734 | no (declared targeted replication) | 900 s |
| S1-replication-wp50 | sblrc x 2 arms, the exact WP50D/E static library + its tbb.dll + construct seed 50801734 | 50801734 | no (declared) | 900 s |
| S2-lotka-wp48 | lotka_volterra x 3 seeds x 2 | 148101–148103 | no (declared, the WP48 seeds) | 900 s |
| S3-sblrc-fresh | sblrc x 10 x 2 | 5402101–5402110 | yes | 900 s |
| S4-lotka-fresh | lotka_volterra x 10 x 2 | 5403101–5403110 | yes | 900 s |
| F-funnel | Neal 10-D funnel x 3 x 2, 4 x 2,000/20,000 | 5404101–5404103 | yes | 1,800 s |
| H-house | 17 posteriordb models x 3 x 2 | 5401101–5401103 | yes | 2,700 s (WP48's) |

The stress timeout (900 s) is about 18x the longest completed WP48 lotka
cell (51 s) and is the same for both arms; a timeout is a recorded
not-completed run. Fresh seeds were checked with `git grep` over `main` and
every `owalnuts-wt` worktree for `\b540(1|2|3|4|9)\d{3}\b`: only
decimal-fraction substrings, no seed use. Non-evidence smoke seed 5409901
(sblrc and funnel, both arms, house and WP50 libraries) was run once before
freezing to check the harness; it is not evidence (`artifacts/smoke/`).

Per cell: completed / aborted (`Numerical` nonfinite position) / error /
timeout; nonfinite-leaf count (`WorkTotals::nonfinite_position_rejections`,
by phase); retained and warmup divergences; gates (rank R-hat <= 1.01, bulk
and tail ESS >= 400 on every posteriordb reference parameter, zero retained
divergences, finite draws); max |z| against the posteriordb reference draws
(z = (mean - ref mean) / sqrt(MCSE^2 + ref MCSE^2), as WP48); an FNV-1a-64
hash over the IEEE bits of every retained draw and the per-chain target-call
counts. The house statistic is the geomean over the 17 models of the
seed-median min bulk ESS per gradient, ratio reject_leaf / abort.

## Predictions (written before any evidence cell)

- **P1** `reject_leaf` completes every run `abort` completes, **P1b** plus
  every stress case `abort` loses. My own expectation, recorded here: P1b
  holds for kernel-nonfinite aborts (S1) but will **fail** for any cell lost
  to a timeout or a non-nonfinite error (lotka 148101 stalled in WP48), since
  the policy cannot touch those.
- **P2** draws and per-chain target calls bit-identical on 100 % of cells
  where `abort` completed.
- **P3** `reject_leaf` stress-set gate passes >= `abort`'s.
- **P4** on every rescued cell (abort did not complete, reject_leaf did),
  max |z| <= 3.
- **P5** every rescued run shows >= 1 retained divergence. My expectation:
  this may **fail** — WP38's three rejections and WP50E's one were all in
  the initial fast warmup window, and the policy maps the point to a
  zero-density leaf (refined like a recoverable failure), not to a retained
  divergence.
- **P6** the funnel |z| <= 2 on every seed under both arms.

## Decision rule (frozen)

Flip iff all of:

- **D1** bit-identical (draw hash and per-chain target calls, zero
  rejections) on 100 % of completed-`abort` cells, over every block;
- **D2** `reject_leaf` completes strictly more runs than `abort` over the
  whole manifest;
- **D3** no rescued posterior run has max |z| > 4 on a reference parameter
  while passing all other gates (a silently wrong rescue is disqualifying);
- **D4** the funnel check (|z| <= 2 on every seed) passes under `reject_leaf`;
- and every manifest cell is recorded.

**If the rule passes**, the flip is implemented as follows (fixed now):
`sampler::Tuning::default()` — the user-facing default behind `Sampler`, the
Python bindings and BridgeStan — becomes `RejectLeaf`;
`Tuning::nonfinite_position` and `NonfinitePositionPolicy` leave the
`research` gate so a user can request `Abort`. `walnutpie::KernelTuning::default()`,
the frozen `v10` replay tuning that `tests/kernel_fingerprint.rs` and
`RunConfig` pin, stays `Abort`, following the existing precedent that
`sampler::Tuning` already differs from it (depth 10 vs 3, 8 vs 2 levels,
U-turn rule). Since D1 means no run that produced draws under `v10` produces
different draws, `ALGORITHM_REVISION` is not bumped and the fingerprint test
is updated only if a fingerprint changes (it should not). CHANGELOG entry
naming this study; `cargo test`.

**If it fails**: document why; `Abort` stays the default.

Rules: failures are results; no cell is rerun or tuned after results;
amendments only for not-yet-run cells, committed before them.
