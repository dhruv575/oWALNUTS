# Preregistration — nonfinite_position_policy_v1 (WP38)

Frozen 2026-09-04 before any study harness, build, or sampling. The source
baseline is commit `36dd4c6718ea9e037ba76a5cd2fd0bc04aed4dd5` (tree
`450b62e42a6b1fd371d2b19355c8599e139c311b`), which contains the research-only
`NonfinitePositionPolicy` implementation and its unit tests but no evidence.
`protocol.json` is the machine-readable protocol. This scaffold contains no
executable study code and no evidence.

## Question and scope

`STUDIES/sspd_target_fatal_diag_v1` found that, once the frozen state-space
target's error classification is repaired, 2 of 13 diagnostic seeds at initial
step 0.5 still end the whole run with `ErrorKind::Numerical` ("kernel
attempted a nonfinite target position"): the integrator overflowed and the
`v10` kernel refuses to continue. Stan treats the same event as a divergent
leaf and continues.

This study asks whether the research-only opt-in
`NonfinitePositionPolicy::RejectLeaf` (an overflowed position is a
zero-density leaf with a zero gradient, exactly like a recoverable target
failure, counted in `WorkTotals::nonfinite_position_rejections`) is
**qualified as an explicit opt-in** for deterministic finite-or-recoverable
targets. It is a qualification gate, not a default decision. **No outcome of
this study changes any default**: `Abort` remains the `walnutpie`, `sampler`
and Python behaviour, and the registered kernel fingerprints are unchanged
under either policy on every run in which the event never occurs. A default
flip, if ever proposed, needs a separate preregistration with posteriordb
evidence.

All targets are analytic, in-process Rust `Target` implementations.
BridgeStan, Stan, Python callbacks and posteriordb are out of scope. No
evidence cell or seed from any earlier study enters this study.

## Frozen arms

| arm      | frozen setting                                                   |
|----------|------------------------------------------------------------------|
| `abort`  | `Tuning` as below with `nonfinite_position(Abort)` made explicit  |
| `reject` | the same configuration with only `nonfinite_position(RejectLeaf)` |

Both arms use `Sampler::new()` with `Metric::diagonal()`,
`Adaptation::default()`, `Limits::new().admit_worst_case()`, 4 chains, 4
threads, and `Tuning::new().step_size(h0).max_depth(10).min_micro_steps(1)
.max_refinement_levels(8).max_error(1.0).divergence_threshold(1000.0)`; the
kernel options are the sampler defaults at the baseline (`MomentumSum`, Stan
metric regularisation, `AcceptUnlessDivergent` warmup exhaustion, no chain
rescue). `h0` is a target setting below. Warmup 1,000 and 1,000 retained
draws on every cell.

## Targets

| target                 | definition                                                                                     | `h0` | starts                                                    | seeds          |
|------------------------|------------------------------------------------------------------------------------------------|-----:|-----------------------------------------------------------|----------------|
| `sspd_repaired`        | polyscope-canonical-v2 state space, `a = 1`, T = 1000, the frozen `sspd11_confirmation_v1` source included by path, wrapped so that every fatal-classified target result is reclassified as `TargetError::recoverable` (the `repair` arm of the diagnostic) | 0.5  | the four `sspd11_confirmation_v1/primary/starts/sspd-11.json` starts mapped through `from_innovations(., 1.0)` | 97201–97224    |
| `neal_funnel_10d`      | Neal's funnel, `omega ~ N(0, 3^2)`, `x_i ~ N(0, e^omega)`, 9 latents, `exp(-omega)` overflow recoverable | 0.5  | `omega in {-3, -1, 1, 3}`, latents 0                        | 97301–97306    |
| `gaussian_100d`        | 100-D standard normal                                                                          | 0.5  | `uniform_starts(., 4, seed, 2.0, 100)`                     | 97301–97306    |

The state-space target is the only one on which the event is expected. The
funnel and the Gaussian are identity controls: the event must not occur, and
the two arms must then be bit-identical.

Seeds were verified unused as whole words anywhere in the repository
(excluding build, virtual-environment, posteriordb, model, artifact and
evidence trees) before freezing.

## Run plan and process contract

72 one-shot cells: 24 seeds x 2 arms on `sspd_repaired`, 6 seeds x 2 arms on
each control. Every cell is a separate child process launched exactly once in
manifest order; a nonzero exit, a timeout (1,800 s) or a missing result is a
recorded result and is never rerun, replaced or deleted. The child writes one
JSON record per cell: completion status, error kind and message if any, wall
time, total target calls, recoverable target failures, nonfinite-position
rejections split into discarded (warmup) and retained phases, retained
divergences, a SHA-256 over the IEEE-754 bit patterns of every retained draw
in chain-major then draw-major order, and the monitored functionals below.

Monitored functionals, computed in-process with `owalnuts::diagnostics`
(rank-normalised split R-hat, bulk and tail ESS):

- `sspd_repaired`: coordinates 0–6 (`mu`, `log sigma_x`, `log alpha`,
  `log beta`, `log gamma`, `log eta`, `x_1`) plus centred latents `x_500` and
  `x_1000` (coordinates 505 and 1005), nine in total;
- `neal_funnel_10d`: `omega` and `P(omega < -5)` pooled over the four chains
  (exact value 0.047790, the `N(0, 9)` tail);
- `gaussian_100d`: coordinates 0, 49 and 99.

## Gates

- **G1 identity (controls).** On every control seed both arms complete, their
  draw hashes and total target calls are equal, and the `reject` arm records
  zero nonfinite-position rejections. 12 of 12 seeds.
- **G2 completion.** The `reject` arm completes 24 of 24 `sspd_repaired`
  cells with exit 0 and a valid record.
- **G3 informativeness.** The `abort` arm fails at least one `sspd_repaired`
  cell with `ErrorKind::Numerical` and the nonfinite-position message. If
  `abort` completes 24 of 24, the study is *uninformative on completion* and
  G2–G5 cannot qualify the opt-in (recorded as `UNINFORMATIVE`, not as a
  pass).
- **G4 health.** On every completed `reject` `sspd_repaired` cell, all nine
  monitored coordinates have R-hat <= 1.01, bulk ESS >= 400 and tail ESS
  >= 400.
- **G5 confinement.** On every `reject` `sspd_repaired` cell the retained
  phase records zero nonfinite-position rejections; every event is in warmup.
- **G6 consistency.** On every `sspd_repaired` seed where `abort` completed,
  the `reject` arm recorded zero rejections and the two arms' draw hashes and
  total target calls are equal.

Descriptive, not gated: the number and warmup-transition indices of
rejections per cell, wall time, and the `abort` failure count.

## Decision

`QUALIFIED_OPT_IN` if G1–G6 all pass. `UNINFORMATIVE` if G3 fails and
G1, G2, G4, G5, G6 pass. Otherwise `NOT_QUALIFIED`. Under every outcome no
default changes; `QUALIFIED_OPT_IN` authorises documenting `RejectLeaf` as a
supported research opt-in for deterministic finite-or-recoverable targets and
nothing more.

## Predictions

1. G1 passes: no control cell records the event and the arms are
   bit-identical.
2. `abort` fails between 1 and 8 of the 24 `sspd_repaired` cells (the
   diagnostic rate was 2 of 13).
3. `reject` completes 24 of 24.
4. G4 passes on every completed `reject` cell.
5. G5 passes: every rejection is in the first 100 warmup transitions.
6. The decision is `QUALIFIED_OPT_IN`.
