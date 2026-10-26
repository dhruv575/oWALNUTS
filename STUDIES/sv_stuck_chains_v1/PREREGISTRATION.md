# Preregistration: sv_stuck_chains_v1 (WP89)

Frozen on `wt/sv-stuck-chains` (base `main` at `522a6c84`; harness `23785f41` before the smoke,
the freeze commit recorded in `README.md`) before the first evidence cell. `protocol.json` is
the machine-readable copy and wins on any discrepancy. Ledger id `WP89-SV-STUCK-CHAINS-V1`.

## Question

WP84 (`STUDIES/online_sv_quote_v1`) re-fitted the 250-return stochastic-volatility model (t5
returns, AR(1) log-volatility with rho = 0.95, intercept; 253 unconstrained coordinates) from
scratch 300 times per sampler at 4 x 1,000/1,000 with best-of-16 starts. One chain froze
(warmup step collapsed to about 1e-6, log density thousands below the others, log_sigma at
+1.3 to +1.9 against the posterior's -1.85, zero movement, zero divergences) on 21/300
oWALNUTS and 39/300 CmdStan fits, on 0/300 nutpie fits, and on 4/100 ticks of the 4 x 20,000
reference; oWALNUTS's chain warnings named every frozen chain (open-questions item 23). WP89
asks: (1) what traps the chain, mechanistically, in oWALNUTS's warmup on this model; (2) why
nutpie's warmup never does; (3) whether a candidate closes the gap without cost elsewhere.

Related: WP57 (`lotka_volterra_stall_v1`: the secondary-mode trap and the end-of-S1 step rule),
WP67 (`trapped_chain_restart_v1`: the research flag `WarmupConfig::with_trapped_chain_restart`,
step ratio 0.1 at transition 99, independent best-of-16 restart; supported on two events),
WP69 (`trapped_chain_restart_confirmation_v1`: not proposed; 2 of 2 fresh lotka flags were
chains that would have recovered, one real trap sat at ratio 0.111, one healthy `earnings`
chain at 0.031 was flagged), WP27 (`step_collapse_v1`: Stan's regularisation installs a mass
of 1e4-1e5 on a chain that could not move in a window), open-questions items 12, 19 and 23.

## What is already known from source (not evidence)

- oWALNUTS defaults: `Init::best_of(16)` (the highest-density of 16 uniform(-2, 2) candidates
  per chain), initial macro step 0.6 with no initial-step search, Stan's window schedule
  (75 / 25, 50, 100, 200, 500 / 50), the identity metric through the initial fast window,
  Stan's diagonal regularisation `(n/(n+5)) var + 1e-3 x 5/(n+5)` (the default since WP32),
  dual averaging on the coarse-endpoint acceptance statistic (gamma 0.05, t0 10, kappa 0.75).
- CmdStan: uniform(-2, 2) starts, `init_stepsize` doubling/halving search, identity metric for
  75 transitions, the same regularisation.
- nutpie 0.16.8 (nuts-rs): standard-normal starts per unconstrained coordinate with no
  candidate selection (`src/stan.rs` `init_position`); the diagonal mass matrix is initialised
  from the gradient at the start, variance_i = 1/|g_i| clamped to [1e-20, 1e20]
  (`src/transform/adapt/diagonal.rs` `Strategy::init` -> `update_diag_grad`), and re-estimated
  from the first transitions on (early window 30 % of warmup, mass-matrix switch every 10
  transitions early, 80 later) as sqrt(var(draws) / var(gradients)) per coordinate.

## Smoke (disclosed, non-evidence; what it showed and what it changed)

Before the freeze, `run_study.py smoke` ran on diagnostic seeds 9989001-9989030 (oWALNUTS
defaults with telemetry), `custom_noop` on two seeds (equal to `defaults` bit for bit: hashes
`f54581609f9d229a` on 9989001), CmdStan and nutpie on two seeds, one funnel pair (diag and
restart identical) and one `earnings` house cell (passed). The numpy density used for the
CmdStan starts agrees with BridgeStan's `sv.stan` density to 9e-11 over five points
(`artifacts/smoke/density_check.json`); WP84 had shown Stan = Rust to 4e-12. Outputs are in
`artifacts/smoke/` and are not evidence. Findings that shaped the design:

- 0 of 120 smoke chains were trapped by the census; every chain ended at log_sigma -1.85.
- Every chain's step sits at 2e-4 to 1e-3 through the identity-metric phase (transitions
  10-100, depth 8-9, 700-900 gradients per transition) and only reaches 0.1 after the first
  metric update. The identity metric is wrong by a factor of 10-150 on the z-coordinates there.
- One chain (9989017 chain 2, start log_sigma 1.60, log density -5,733) rejected its first
  three transitions at steps 0.5-1.2 (refinement exhausted, max |gradient| 3e4), then its step
  fell to 2e-4 by transition 5 and to 7.5e-7 by transition 10 as it moved into a region with
  max |gradient| 1.5e6 at log_sigma 1.43; it crawled there (log density -1,900 -> -1,700 over
  150 transitions, 600-900 gradients each). Its first metric update (transition 99) installed
  the regularisation floor on every coordinate (mass 6e3 = 1 / (1e-3 x 5/30), the chain had
  not moved), the step after it was 6.7e-7, and the second update (149) installed mass 1.1e4.
  It escaped by luck near transition 200 (log density -1,694 -> +449, log_sigma 1.37 -> -0.32
  -> -1.86). This is the WP84 frozen signature (step 1e-6, log_sigma +1.4, log density
  thousands below) for a chain that happened to get out in time.
- The healthy chains of the same cell started at log_sigma 1.55-1.70 too; their first
  transition (step 0.5, depth 1-3) flung them to log_sigma -32 to -53, from where they climbed
  to the mode in 25 transitions (max |gradient| 4e2-2e3 on that side).
- The chosen best-of-16 starts' log_sigma is roughly uniform on (-2, 2) (quartiles -1.0, 0.0,
  1.0), so candidate selection does not single out large-sigma starts.
- CmdStan's step at transitions 1-2 is 14 and 2.4 (the `mu = ln(10 h0)` overshoot), then
  3e-4 to 7e-4 through S1; nutpie's step is 0.25-0.5 from the first transition on.

Changes made because of the smoke, all before any evidence cell: the `stan_reg` arm (identical
to the defaults, whose regularisation already is Stan's) became `unit_reg`; the `nutpie_init`
arm was added (nutpie's gradient-scaled initial metric, the direct test of question 2);
the strict guard ratio 0.001 was replaced by 0.01 (the smoke's frozen chain sat at ratio
0.004 at transition 99, above 0.001; WP67/WP69's lowest healthy ratios were 0.024 and 0.031);
predictions P2-P4 were rewritten against the mechanism seen.

## Design

All SV cells: the WP84 target and data (`models/data.json`, seed 84084, N = 250, the first 250
returns), 4 chains x 1,000 warmup / 1,000 retained, 4 threads, diagonal metric, worst-case
admission. The real-data variant is skipped: WP84 did not reuse the repo's Deribit receipts (no
reuse licence recorded), and neither does WP89.

**Part A, descriptive.** 120 fresh seeds (8901001-8901120) x {nutpie, CmdStan, oWALNUTS
defaults}. Recorded per chain: trapped or not (rule below), the start's log density and
log_sigma (oWALNUTS: the chosen candidate and all 16 candidate densities; CmdStan: inits drawn
in the driver as uniform(-2, 2) with the numpy density; nutpie: the first warmup draw stands
in, the init is not exposed), the step trajectory through warmup (oWALNUTS: every transition
from the comparison observer; CmdStan: `stepsize__` with `save_warmup`; nutpie: `step_size`
with `save_warmup`), the first checkpoint at which the step collapses, the installed metric
diagonals (oWALNUTS: every update; CmdStan: the final inverse metric; nutpie: `mass_matrix_inv`
at transitions 0, 9, 19, 49, 99, 299 and the last), log density and log_sigma traces,
divergences, final step, chain warnings.

**Part B, mechanism (oWALNUTS only).** 60 fresh seeds (8902001-8902060) per arm, sized to the
budget: at about 2 % of chains trapped, 240 chains give about 5 expected events, so B can
detect a factor-of-3 change, not finer. Arms, everything else at the defaults, in this order:
`nutpie_init` (nutpie's initial mass matrix, per chain mass_i = clamp(|g_i(start)|, 1e-20,
1e20), then the default adaptation; run through the low-level entry point as single-chain
runs with base seed `seed + c`, which is chain c's own RNG stream), `unit_reg`
(`TowardUnit` regularisation, floor 5/(n+5)), `small_step` (initial macro step 0.05),
`stan_search` (Stan's `init_stepsize`), `early_windows` (windows 10 / 10, 20, 40, ... / 50),
`grad_metric` (nutpie's estimator in the Stan windows, the WP71 flag), `uniform`
(CmdStan's one-candidate rule), `median16` (`Init::median_of(16)`), `normal` (nutpie's
standard-normal starts).

**Part C, candidates (oWALNUTS), paired with A-defaults on the same 120 seeds.** Each
candidate is `Adaptation::Custom` of the configuration `Adaptation::default()` builds plus one
research option:
- `restart`: WP67's `TrappedChainRestartConfig::step_rule()` (ratio 0.1 at transition 99).
- `guard-0.01-0`: the warmup step-collapse guard, ratio 0.01 at transition 99.
- `guard-0.01-1`: ratio 0.01 at the end of the second slow window (transition 149), via
  `TrappedChainRestartConfig::with_check_window(1)` (this study's library addition, research
  feature, default 0 = unchanged behaviour, unit-tested bit-identical).
Controls: Neal's 10-D funnel at 4 x 2,000/20,000 on 30 seeds (8903001-8903030) for `diag` and
each candidate (WP85 harness); three house posteriordb models by the v7 gates on 3 seeds
(8904001-8904003) for `defaults` and each candidate (WP67 harness and scoring): `earnings`
(transient warmup step dips at ratios 0.03-0.14 in WP69, the specificity case),
`eight_schools_centered` (lowest healthy ratio 0.301 in WP67), `hmm_drive_0` (a genuine
second mode on which the rule must not act).

**Order.** A-nutpie, A-cmdstan, A-defaults, B (arm by arm), C (candidate by candidate), F, P;
1,416 cells, each run once in `protocol.json`'s manifest order; a started cell is never rerun;
failures are results. Every evidence seed was grep-verified unused.

## Trapped chain (frozen definition)

Anchor: the median over all Part A nutpie chains of the chain-median retained log_sigma
(and of h_last). A chain is **trapped** iff |median retained log_sigma - anchor| > 1.0 or
|median retained h_last - anchor| > 2.0 (the WP84 post hoc census; posterior SDs about 0.3
and 0.45; every WP84 frozen chain sat 3-4 units away). Reported alongside, not deciding: the
first checkpoint (ends of init 74, S1 99, S2 149, S3 249, S4 449, S5 949, term 999) at which
the chain's step is below 0.1 x the median over chains, and whether oWALNUTS's chain warnings
named exactly the trapped chains.

## Decision rule (frozen)

A candidate **qualifies** (proposed for a default-flip confirmation study; nothing is flipped)
iff all of:
- R1 efficacy: its trapped-chain count over the 480 Part C chains is 0, or Fisher's exact test
  against the A-nutpie count gives p >= 0.05 and the count is at most half the A-defaults count;
- R2 fingerprint: every C cell on which no chain restarted has the draw hash of the A-defaults
  cell on the same seed; where a chain restarted, every untouched chain is bit-identical per
  chain; no C cell errored; the library kernel fingerprint tests pass with and without `research`;
- R3 funnel: all 30 cells complete; no restart fired and every cell is bit-identical to its
  `diag` pair, or, where one fired, the pooled P5 is within 2 s.e. of the exact 0.04779;
- R4 house models: all 9 cells complete; passes candidate >= defaults; no restart fires on a
  cell that passes at the defaults; every unfired cell is bit-identical to the defaults cell;
- R5 library: `cargo test` (default and research) and `cargo clippy -D warnings` pass on 1.88;
  no default changed.
A candidate that errors on any cell FAILS (implementation).

## Predictions (written after the smoke, before any evidence cell)

- P1: trapped chains of 480: oWALNUTS defaults 3-16, CmdStan 8-28, nutpie 0-1.
- P2 (mechanism): every trapped oWALNUTS chain has its retained median log_sigma above +0.5
  (it never left the high-sigma basin), its step is below 0.1 x the median by the end of the
  initial fast window, and its first installed metric is the regularisation floor on every
  coordinate (mass about 6e3); at least 80 % of trapped chains start at log_sigma > 0.5; the
  trapped point is more than 1,000 nats below the healthy chains.
- P3: `nutpie_init` traps 0-1 of 240 chains; `unit_reg` at most half the defaults' rate but not
  zero; `uniform` at least as often as the defaults; `normal`, `median16`, `small_step`,
  `stan_search`, `grad_metric` within a factor of 2 of the defaults; `early_windows` at least
  as often as the defaults.
- P4: `restart` and both guards each remove at least 80 % of the trapped chains; `restart`
  fires on at least one `earnings` cell and the guards on none; no candidate fires on the
  funnel; `guard-0.01-0` fires on at least one A-defaults chain that would have recovered.
- P5: R2 holds for every candidate.

## Execution notes

Lane 1 of the shared c7a.4xlarge box (`taskset -c 0-3`, `RAYON_NUM_THREADS=4`,
`OMP_NUM_THREADS=1`), co-tenanted with other lanes: walls are "pinned, co-tenanted"; trapped
counts, draw hashes, gates and gradient counts are unaffected. Budget: about 2-2.5 h of lane
time. Telemetry (`artifacts/telemetry/*.json.gz`) is hashed in `CHECKSUMS.sha256` and kept
out of git; cell JSONs are committed. A second disclosed smoke (`lowlevel_noop` must equal
`defaults` bit for bit; `nutpie_init` runs on two diagnostic seeds) precedes the first evidence
cell; its outcome is recorded in `README.md`.
