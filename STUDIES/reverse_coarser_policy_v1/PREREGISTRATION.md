# Preregistration — reverse_coarser_policy_v1 (WP39-REVERSE-COARSER-POLICY-V1)

Frozen 2026-09-05 before the first cell. `protocol.json` carries the same
content in machine form; its hash is in `CHECKSUMS.sha256` and in
`summary.json`.

## Question

`refinement_role_v1` (WP34) found that the four posteriordb models where
oWALNUTS is furthest behind CmdStan per gradient (noncentered eight schools
0.75x, `gp_pois_regr` 0.75x, centered eight schools, `accel_gp` 0.47x) are
exactly those where the reverse-coarsening check ends the most retained
transitions (10 %, 20 %, 21 %, 54 %), while the check's own gradient cost
is negligible (`target_calls_reverse` below 1 % of the retained calls on
every model; 7k of 1.2M on `accel_gp`). WP34's "next decision" named a
cheaper check; the data say the cost is not the check but what the kernel
does when it fails: the doubling is discarded and the orbit ends, so the
orbit is truncated where refinement is doing real work.

The kernel now carries a research-only alternative,
`ReverseCoarserPolicy::ZeroWeightBeyond` (commit `e5a6617`): when a
refined leaf fails the check, its forward endpoint and every leaf beyond it
in that direction are kept at zero weight (reverse checks skipped while
poisoned; the forward refinement rule unchanged) and the orbit runs on to
its U-turn or the depth cap. Validity: the set of states reachable through
passing leaves is the same from any positive-weight state of the orbit, so
selection restricted to that component is reversible (the argument in the
enum's doc comment); `tests/reverse_coarser_policy.rs` verifies bit-identity
when no leaf fails and exact moments on an anisotropic Gaussian where 
failures are frequent.

**Does `ZeroWeightBeyond` pay per gradient on posteriordb, and is it exact on
the funnel, well enough to become the sampler default?**

## Arms (`arms.rs`; everything else the shipped defaults)

| arm | `Tuning::reverse_coarser_policy` | behaviour at a failed reverse check |
|---|---|---|
| `stop` | `StopOrbit` (default) — `Tuning::default()` itself | doubling discarded, orbit ends |
| `beyond` | `ZeroWeightBeyond` | endpoint and everything beyond kept at zero weight, orbit runs on |

Common: `Tuning::default()` (`h0 0.5`, depth 10, eight levels, `delta 1`,
`MomentumSum`), `Adaptation::default()` (dual averaging at 0.8 on the
coarse-endpoint statistic, Stan regularisation, WP24 exhaustion rule),
`Metric::diagonal()`, `Init::uniform()`, `Limits::admit_worst_case()`, four
threads. No per-model tuning, no source change between arms. `stop` is
bit-identical to WP34's `da` at equal seeds; this study uses fresh seeds.

## Protocol

The `posteriordb_bench_v5` cell protocol: 17 posteriors at posteriordb
`28f8d3d`, 4 chains x 1,000 warmup / 1,000 retained, BridgeStan 2.9.0
libraries compiled without `STAN_THREADS` for `posteriordb_bench_v6`
(reused from `C:/dev/owalnuts-wt/posteriordb-v6/STUDIES/posteriordb_bench_v6/models`,
not recompiled), ArviZ 0.23.4 rank R-hat / bulk / tail ESS on the reference
parameter set, gates rank R-hat <= 1.01, bulk and tail ESS >= 400, zero
sampling divergences, finite draws, no sampler error. Statistic per cell:
minimum over reference parameters of bulk ESS divided by all target calls
(warmup included; the v5 and WP34 statistic). Seeds **91101, 91102, 91103**
(grep-verified unused). Run order: models as listed, `stop` then `beyond`,
seeds ascending, sequential; then the funnel rows. 102 cells + 6 funnel
rows. CmdStan cited from v5 (seeds 87101–87103), not rerun.

Side check: Neal's 10-D funnel at the sampler defaults plus the arm's
policy, 4 x 2,000 / 20,000, starts `omega in {-3, -1, 1, 3}`, per-seed MCSE
z of `P(omega < -5)` (exact 0.0478), the WP28 statistic.

Target models (where WP34's reverse-coarser stop fraction was >= 10 %):
noncentered eight schools, centered eight schools, `gp_pois_regr`,
`accel_gp`. The other thirteen are controls.

## Predictions

- **P1.** `beyond` has zero reverse-coarser stops on every cell (by
  construction) and continued-leaf counts equal to `stop`'s rejection
  counts within seed noise; adapted `h` within 0.95–1.05x of `stop`'s on
  every model (the dual-averaging statistic does not see the zero-weight
  leaves).
- **P2.** On the four target models `beyond` is 1.15–2.0x `stop` per
  gradient, largest on `accel_gp` (54 % stops in WP34) and smallest on the
  noncentered eight schools (10 %); leaves per orbit rise by at most
  `1 / (1 - rc stop)`.
- **P3.** On the thirteen controls (0.8–7 % stops) `beyond` is within
  0.95–1.05x of `stop`; the geomean over 17 lands at 1.05–1.20.
- **P4.** Funnel `|z| <= 2` on every seed for both arms; `beyond`'s omega
  ESS per call within 0.9–1.2x of `stop`'s.
- **P5.** `beyond` passes at least as many of the 51 gates as `stop`; max
  rank R-hat and `|z|` against the reference unchanged in distribution.
- **Risk.** The zero-weight tail can drive orbits to the depth cap on the
  target models (WP34: `accel_gp`'s depth histogram sits at 9–10). If
  depth-cap stops exceed 20 % of transitions on a model, the gain there
  will fall short of P2 and that is the mechanism to report, not a reason
  to change the depth.

## Decision rule (frozen)

Flip the sampler default to `ZeroWeightBeyond` iff all of

- **C1** geomean over the 17 models of the seed-median ratio
  `beyond`/`stop` of min bulk ESS per gradient >= **1.10**;
- **C2** no model's ratio < **0.90**;
- **C3** `beyond` passes at least as many of the 51 gates as `stop`;
- **C4** funnel `|z| <= 2` on every seed for `beyond`;
- **C5** geomean over the four target models >= **1.15**.

Otherwise `StopOrbit` stays the default and the opt-in stays research-only,
with the per-model table as the finding. Report all cells; no reruns;
failures are results; nothing is tuned after seeing results. A flip is a
separate labelled commit that changes `ReverseCoarserPolicy::default()` /
`KernelTuning::new()` and re-freezes the affected fingerprints.
