# Preregistered paper funnel reproduction v1

Frozen before execution on 2026-08-31 (WP2 of
`wiki/research-program-2026-08-31.md`). No sampler source is modified.

## Target

Neal's funnel exactly as JMLR/arXiv 2506.18746 eq. (32) with `d = 9`
(dimension 10): `ω ~ N(0, 9)`, `x_i | ω ~ N(0, exp(ω))`, `i = 1..9`.
Log density `-ω²/18 - 4.5 ω - ½ e^{-ω} Σ x_i²` (unnormalized), analytic
gradient. Identical to `neal_funnel_health_pilot_v1`. Exact marginals used as
truth: `ω ~ N(0, 9)`; `P(ω < -5) = Φ(-5/3) = 0.047790`;
`P(ω < -6) = Φ(-2) = 0.022750`.

## Paper settings being reproduced

Paper §4.3 / Figures 11–12: WALNUTS with `δ = 0.21`, macro step `h = 0.36`,
identity mass, warm start, up to 10 orbit doublings and up to 8 micro-step
halvings observed. The paper's variant there is WALNUTS-R2P and used 200,000
(Fig. 11) and 1,000,000 (Fig. 12) single-chain iterations; the paper itself
states that "both samplers mix very slowly". The paper's claim is **tail
accuracy**: WALNUTS explores the left tail of ω where NUTS at matched cost
(`h_NUTS = 0.11`) does not.

## Arms

All arms: 4 chains, dispersed starts `ω ∈ {-3,-1,1,3}`, `x = 0`; identity
`DiagonalMass`; no `WarmupConfig` (discarded transitions are burn-in with the
same fixed kernel); `RunConfig` default limits with an explicit budgeted
admission (`TargetEvaluationAdmissionLimit` = exact worst case, runtime
`TargetEvaluationBudget` = 1e9 callbacks); one thread per chain sequentially
(`max_threads = 1`); divergence threshold 1000.

| Arm | Sampler | h | δ (`max_error`) | refinement levels | depth | discarded | retained | base seed |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| F | oWALNUTS fixed paper tuning (primary) | 0.36 | 0.21 | 10 | 10 | 2,000 | 10,000 | 81001 |
| F50 | same as F, extended draws (secondary; tail statistics) | 0.36 | 0.21 | 10 | 10 | 2,000 | 50,000 | 81101 |
| N11 | oWALNUTS with refinement disabled = fixed-step NUTS-like control at the paper's NUTS step | 0.11 | 1000 (no local cap) | 1 | 10 | 2,000 | 10,000 | 81201 |
| N36 | refinement disabled at the WALNUTS step ("what refinement buys") | 0.36 | 0.21 | 1 | 10 | 2,000 | 10,000 | 81301 |
| R0 | Flatiron `walnutpie` 0.0.3 (PyPI), `min/max_warmup_iter = 0`, `step_size_init = 0.36`, `max_hamiltonian_error = 0.21`, `max_step_halvings = 9`, `max_trajectory_doublings = 10`, identity inverse metric, same starts | 0.36 init (the reference performs its own initial step search even with zero warmup; per-chain final step is recorded) | 0.21 | 9 halvings | 10 | 0 | 10,000 | 81001 |
| R1 | `walnutpie` 0.0.3 as shipped: adaptive warmup 1,000 iterations (`min = max = 1000`), same δ/halvings/doublings, `step_size_init = 0.36` | adapted | 0.21 | 9 | 10 | 1,000 warmup | 10,000 | 81001 |

Chain `i` of an oWALNUTS arm uses `splitmix64(base_seed + i)`; the seeds
81001–81004, 81101–81104, 81201–81204, 81301–81304 are fresh (not present in
any ledger). The reference RNG is unrelated; its seed value is recorded only.

If any arm exceeds 20 minutes of sampling wall time it is stopped and the
deviation is recorded; retained draws are then halved for that arm only.

## Gates (evaluated per arm, retained draws only)

Diagnostics use ArviZ 1.3 on the 4 retained chains:

1. rank-normalized folded split R-hat ≤ 1.01 for `ω` and `x_1`;
2. bulk ESS ≥ 400 and tail ESS ≥ 400 for `ω` and `x_1`;
3. zero retained divergences, invalid-evaluation stops, and
   refinement-exhaustion stops (oWALNUTS arms; the reference exposes no such
   counters, recorded as unavailable);
4. **paper-claim tail gate**: the pooled retained fraction of `ω < -5` lies
   within a 95% interval of the exact value 0.047790 whose half-width is
   `1.96·sqrt(p(1-p)/ESS_tail)` using the measured tail ESS of `ω` (so the
   interval honestly reflects autocorrelation); same for `ω < -6` (0.022750).
5. Reported, not gated: `mean(ω)` vs 0 and `var(ω)` vs 9 with MCSE from ESS;
   left-tail quantiles of `ω` at 1%, 0.5% vs exact (−6.979, −7.727).

Success for the reproduction claim = arm F passes gate 3 and gate 4 (tail
mass correct with no divergences) and arm N11 fails gate 4 in the direction the
paper reports (too little left-tail mass). Gates 1–2 are reported as the
program's convergence standard; failing them with 4×10,000 draws is consistent
with the paper's own statement about slow mixing and is not, on its own,
a failed reproduction — but it is reported as a failed gate.

Failure = arm F has retained divergences/exhaustions, or its `ω < -5` mass
falls outside the interval, or the tail quantiles are biased upward like the
NUTS control.

## Outputs

`artifacts/<arm>.json` (samples, per-transition depth/stop/refinement summary,
telemetry, wall), `artifacts/summary.json`, `CHECKSUMS.sha256`, README table,
and a ledger entry in `wiki/research-ledger-2026-08-31.md`.
