# Preregistered Stock–Watson SV reproduction (WP2b)

Frozen 2026-08-31 before any sampling. `protocol.json` is normative.

## Target

JMLR §4.4 (eqs. 35–38): three coupled random-walk factors with one shared
scale `σ` for `z` and `x`, prior `σ⁻² ~ Gamma(5, rate 0.5)`, in the paper's
innovation parameterization with identity mass. Dimension `3T = 756`.

Deviations from the paper, recorded:

* **Data.** The paper uses the 1955Q1–2018Q1 US quarterly inflation series
  (T=252). That series is not available offline, so `y` is simulated from the
  model with `σ=0.3`, `z₁=0`, `x₁=0`, `μ₁=2`, data seed `2026083102`. The
  geometry (nonlinearly coupled funnels) is the model's, not the data's, but
  absolute posterior numbers are not comparable to the paper's Figure 15.
* **Initial-state priors.** Not stated in the paper; `z₁, x₁, μ₁ ~ N(0, 10²)`.

The analytic gradient is unit-tested against central finite differences at
relative tolerance `1e-6`, and the innovation map is round-trip tested against
simulated truth.

## Arms

| arm | h | δ | min micro | levels | depth | warmup | seed |
|---|---|---|---|---|---|---|---|
| F | 0.1 | 0.3 | 8 | 8 | 10 | none (1,000 discarded burn-in) | 84001 |
| N | 0.002 | 1000 (off) | 1 | 1 | 10 | none | 84002 |
| A | 0.05 → adapted | 1.0 → adapted | 8 | 8 | 10 | paper Appendix C: Δ=2, p_a=0.95, Γ=0.8, identity mass | 84003 |

Four chains, dispersed starts (`φ ∈ {−3.5,−2.5,−1.5,−0.5}`, other
coordinates standard normal), 1,000 discarded + 5,000 retained per chain,
four threads, 1.5e3 s wall cap and 1e9 callback cap per arm. Seeds 84001–84003
were verified absent from every ledger and study; 84004 is reserved.

## Gates (per arm)

* rank-normalized folded split R-hat ≤ 1.01 on `log σ²`, `z_T−1`, `x_T`, `μ_T`;
* bulk and tail ESS ≥ 400 on the same functionals;
* zero retained divergences, invalid evaluations, refinement exhaustions;
* retained maximum-depth rate ≤ 1%.

Headline (paper Figure 16): per-orbit Hamiltonian range `max H − min H` over
retained transitions. The paper's claim reproduces if arm F passes all gates
with at most 1% of orbits above 2 while arm N exceeds 10% above 2.

Arm A reports where δ and h land against 0.3 / 0.1; there is no gate on it.

## Reporting

All numbers are reported as measured. Failed gates are reported as failed.
Runtime deviations (draw reductions) are recorded in the README and ledger.

## Amendment 1 (2026-08-31, before any evidence was interpreted)

The original start rule (prior-scale `N(0,1)` innovations, `φ` dispersed) put
chains far outside the typical set of a 756-dimensional nonlinear target.
Arms F and A stopped every transition at the first evaluation
(`invalid_evaluation`, zero leaves built, 2–3 target calls per transition);
arm N had two chains stuck the same way and two chains with 22–25% divergent
transitions and 77% depth caps. Those runs are recorded only as a compact
summary in `artifacts/superseded-start-rule-v1/summary.json` and are not
evidence.

Amended start rule: `φ ∈ {−3.5, −2.5, −1.5, −0.5}` (unchanged); `μ` path
started on the data (`μ₁ = y₁`, `η_μ,k = y_k − y_{k−1}` with `z` flat at zero);
`x₁ = log(½·mean (Δy)²)`; `z`/`x` innovations zero; then `N(0, 0.1²)` jitter on
every coordinate, seeded per chain. Seeds, arms, draw counts and gates are
unchanged. Sampling seeds 84001–84003 are reused because the superseded runs
produced no retained evidence; this is recorded here rather than hidden.

Side observation for WP1 (not a study result): under 100% invalid
transitions the paper Γ-rule drove arm A's step to its `1e6` bound
(`final step_size = 1000000.0`), i.e. transitions with zero built leaves count
as fully unrefined. Reported as a defect in the ledger.

## Amendment 2 (2026-08-31, before any evidence): non-finite policy

The reference implementation treats a failed density/gradient evaluation as
`log p = −∞` with a zero gradient (`walnutpie/util.hpp`), and its `micro`
loop keeps halving until `|ΔH| ≤ max_error` or the halvings are exhausted.
oWALNUTS instead stops the transition at the first recoverable target error
(`InvalidEvaluation`, no refinement). To evaluate the paper's kernel rather
than this facade policy, the study target now returns a finite penalty
(`−1e10`, zero gradient) for non-finite evaluations (`nonfinite_policy =
finite_penalty`). The difference is reported as a parity defect in the ledger.

## Amendment 3 (2026-08-31, before any evidence): typical-set starts

The amendment-1 data-informed starts were still far outside the typical set:
with the finite-penalty policy, arm-F-tuned smoke chains refined to
exhaustion at all eight levels with constant per-orbit Hamiltonian ranges of
about 12 and 482 (integration error would shrink with the micro step; a
constant error means the orbit leaves the region the start was in). Arm N
(NUTS, h = 0.002) under the same starts had 22–25% divergent transitions and
77% depth caps on the chains that moved.

The paper's Figure 16 characterises the stationary regime after warmup. All
arms therefore start from the innovation image of the simulated true latent
paths with `φ = log σ²_true + {−0.6, −0.2, +0.2, +0.6}` per chain and
`N(0, 0.1²)` jitter on every coordinate. Arms, seeds, draw counts and gates are
unchanged; arm A still adapts from `δ = 1.0, h = 0.05`. Superseded runs are
summarised in `artifacts/superseded-start-rule-v2/summary.json`.

## Amendment 4 (2026-08-31, before any evidence): fixture stiffness rule

Under amendment-3 typical-set starts the seed-2026083102 fixture still
exhausted refinement at all eight levels or overflowed (Hamiltonian ranges up
to 1e265) at arm-F tuning. The cause is the fixture, not the start: its
transient volatility path reaches `x = −8.6`, so `max exp(−x) = 5494`; the
largest curvature of the μ-innovation block scales as
`max exp(−x)·(2T/π)²`, giving a stable leapfrog step of about `1.7e-4`, at or
below the finest WALNUTS micro step (`0.1/8/2⁷ ≈ 9.8e-5`). The paper's real
series has `x ∈ [−5, 1]` (Figure 15), i.e. about 37× less stiff, consistent
with its NUTS step of 0.002.

Fixture rule: take the first data seed in `[2026083102, 2026083104,
2026083105, …]` whose simulated latent ranges satisfy `min x ≥ −5`,
`max x ≤ 1.5`, `max z ≤ 1` (the paper's Figure 15 ranges). Seeds 2026083104–
2026083108 fail the range criteria; **2026083109** is the first admissible
seed (`z ∈ [−5.6, 1.0]`, `x ∈ [−5.0, 0.4]`, `y ∈ [−3.9, 10.5]`). The scan is
kept in `artifacts/fixture-scan/`. Arms, seeds, draws, starts (amendment 3)
and gates are unchanged.

## Amendment 5 (2026-08-31, before any evidence): exact true-path starts, jitter 0.01, 500/2,000 draws

An independent numpy replica of the target (gradient agrees with the Rust
target to 2e-11) was used to measure leapfrog energy error over one macro
interval (0.1) from candidate starts. On the exact true path the endpoint
error is 0.006 at ε = 7.8e-4; with `N(0, 0.01²)` innovation jitter it is
8.9 at 7.8e-4 and 0.13 at 9.8e-5; with `N(0, 0.1²)` jitter (amendment 3)
it is 572 and 8.5 respectively. The innovation coordinates are therefore
extremely concentrated (largest curvature ≈ `max exp(−x)·(2T/π)² ≈ 4e6`,
stable step ≈ 1e-3, δ = 0.3 needs ≈ 2e-4), and amendment-3 starts were
outside the region any of the eight refinement levels can integrate.

Changes: innovations are computed at each chain's own σ so every chain starts
on the true latent paths; jitter is `N(0, 0.01²)`; evidence arms use 500
discarded + 2,000 retained draws per chain (projected cost at 1,000/5,000:
≈ 512 gradients per macro step × tens of macro steps × 24,000 transitions,
beyond the wall cap); wall cap 2,400 s. Arms, seeds and gates are unchanged.

## Amendment 6 (2026-08-31, before any evidence): low persistent-volatility fixture

With amendment-5 starts the seed-2026083109 fixture still exhausted all eight
refinement levels (2,041 target calls per transition, zero leaves built). The
numpy probe explains why: with `z ∈ [−5.6, 1]`, `exp(z/2)` multiplies the
trend innovations by up to 1.6, so each μ-innovation coordinate moves every
later `μ_t` by O(1) and the observation precision `exp(−x)` makes those
directions stiff (δ = 0.3 needs micro steps near 1e-4 – 2e-4, below the
finest available `9.8e-5` on some transitions). In the paper's data the
persistent volatility drifts from 0 to about −12 (`exp(z/2)` down to 2e-3),
which is what makes the innovation parameterization sampleable at
`h = 0.002` for NUTS and `h/8` with one or two halvings for WALNUTS.

Fixture rule: simulate with `z₁ = −6`, `x₁ = −2`, `μ₁ = 2`, `σ = 0.3`, and
take the first seed in `[2026083120, 2026083121, …]` with `z ∈ [−14, 0]`
and `x ∈ [−7, 3]`. **2026083120** is admissible (`z ∈ [−7.6, −0.5]`,
`x ∈ [−6.3, 2.9]`, `y ∈ [−5.6, 5.8]`); its numpy leapfrog probe gives
endpoint errors 4.1e3 / 0.013 / 0.053 / 0.012 at 0.0125 / 0.00625 / 0.002 /
0.001, the paper's regime. The scan is kept in `artifacts/fixture-scan-v2/`.
Starts (amendment 5), arms, seeds, draws (500/2,000) and gates are unchanged.

## Amendment 7 (2026-08-31, before any evidence): bounded penalty region

With the seed-2026083120 fixture and amendment-5 starts, the smoke arm built
leaves (levels 4–6, depths 1–3) but 65–81% of transitions still stopped with
`invalid_evaluation`: a coarse refinement attempt overflows the position and
the oWALNUTS kernel stops the whole transition instead of halving (the
reference treats a failed evaluation as `−∞` with zero gradient and keeps
halving). To evaluate the paper's kernel, the study target now bounds the
observation exponent (`exp(min(−x, 700))`) and clips gradient components to
`±1e8` under the finite-penalty policy, so positions stay finite and the
kernel's energy-error test (not its non-finite stop) rejects the coarse
attempt. Clipping only binds where the macro-step energy error is many
orders above δ, so no accepted macro step is affected and the target is
unchanged on its region of non-negligible density. The kernel difference is
reported as a parity defect in the ledger.
