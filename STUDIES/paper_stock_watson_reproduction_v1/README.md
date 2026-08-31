# Paper Stock–Watson SV reproduction v1 (WP2b)

Evidence class: preregistered exploratory sampling evidence (one seed per arm,
four chains each) for the JMLR §4.4 Stock–Watson stochastic-volatility
benchmark on **simulated** data. Kernel revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9` for every arm (all three
evidence arms were sampled concurrently from the same binary).

`PREREGISTRATION.md` records the frozen design and seven amendments, all made
before any evidence was interpreted; `protocol.json` is normative. Reproduce:

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release      # gradient vs finite differences; innovation round trip
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --data artifacts/data.json
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight artifacts/preflight.json
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample F artifacts/F.json   # likewise N, A
python analyze.py
python checksums.py
```

## Target and fixture

Paper model (eqs. 35–38) with one shared random-walk scale `σ`, prior
`σ⁻² ~ Gamma(5, rate 0.5)`, innovation parameterization, identity mass,
dimension `3T = 756`. Deviations: simulated series (the 1955Q1–2018Q1 US
inflation series is not available offline) generated from the model with
`σ = 0.3`, `z₁ = −6`, `x₁ = −2`, `μ₁ = 2`, data seed `2026083120` chosen by the
preregistered range rule (`z ∈ [−14, 0]`, `x ∈ [−7, 3]`; obtained
`z ∈ [−7.6, −0.5]`, `x ∈ [−6.3, 2.9]`, `y ∈ [−5.6, 5.8]`); initial-state
priors `N(0, 10²)`. Starts: innovation image of the simulated true paths at
each chain's `σ`, `φ = log σ²_true + {−0.6, −0.2, +0.2, +0.6}`, `N(0, 0.01²)`
jitter; 500 discarded + 2,000 retained per chain, 4 chains, 4 threads.

## Results

| arm | tuning | pass | max R-hat | min bulk ESS | min tail ESS | div | exh | depth cap | retained calls | wall s | bulk ESS / M calls | bulk ESS / s | orbits with `max H − min H > 2` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **F** paper fixed | h=0.1, δ=0.3, min 8 micro, 8 levels, depth 10 | **no** (1 exhaustion) | 1.0016 | 2,156 | 1,777 | 0 | **1** | 0.00% | 20,753,272 | 90.4 | 103.9 | 23.9 | **13.2%** (q99 6.54, max 20.9) |
| **N** NUTS control | h=0.002, no refinement, no local cap | **no** (1 div, 1 exh, 99.99% depth cap) | 1.0022 | 1,291 | 2,351 | 1 | 1 | **99.99%** | 8,191,457 | 85.0 | 157.6 | 15.2 | 0.10% (q99 0.77, max 2,049) |
| **A** paper adaptation | from δ=1.0, h=0.05; Δ=2, p_a=.95, Γ=.8 | **yes** | 1.0031 | 1,363 | 2,088 | 0 | 0 | 0.00% | 6,445,520 | 45.9 | **211.4** | **29.7** | 2.0% (q99 2.55, max 9.6) |

Gate functionals: `log σ²`, `z_T−1`, `x_T`, `μ_T` (R-hat ≤ 1.01, bulk/tail
ESS ≥ 400, zero retained divergences / invalid evaluations / refinement
exhaustions, depth-cap rate ≤ 1%). Work unit is fused target calls.

Posterior means agree across the three arms to within Monte-Carlo error
(e.g. `log σ²` −2.316 / −2.326 / −2.329; `z_T−1` −3.155 / −3.120 / −3.204;
`x_T` 2.072 / 2.090 / 2.073; `μ_T` 1.094 / 1.091 / 1.054), so all three
kernels sample the same posterior on this fixture.

Arm F kernel behaviour: selected refinement levels 3/4/5/6/7 =
27/3,585/3,265/275/11 of 8,000 retained transitions (micro steps
7.8e-4–3.9e-4 dominate), depth 1/2/3 = 837/1,155/6,008, 3,540 reverse-coarser
stops (WALNUTS-D reversibility rejections, 44%), 2,594 calls per transition.

Arm A adaptation landing (paper values δ = 0.3, h = 0.1 with 8 micro-steps,
i.e. coarsest micro step 0.0125): final δ per chain 0.567 / 0.389 / 0.362 /
0.367; final h 0.00371 / 0.00424 / 0.00515 / 0.00419 (coarsest micro step
≈ 5e-4). Window unrefined fractions 0.77–0.81 against Γ = 0.8; five
installations per chain, no fallbacks. Retained transitions selected level
0/1/2 = 6,197/1,618/32 and depth 7 in 75% of transitions (orbit length
≈ 0.5 time units); 806 calls per transition.

Arm N: every retained transition but one hit the depth-10 cap (1,024
leapfrogs of 0.002 = 2.05 time units without a U-turn); one divergence with
Hamiltonian range 2,049.

## Verdict against the preregistered claim

**The paper's Figure 16 claim did not reproduce on this fixture.** The
preregistered criterion required arm F to pass all gates with ≤ 1% of orbits
above energy range 2 while arm N exceeded 10%. Observed: arm F 13.2% and one
retained refinement exhaustion; arm N 0.10%. NUTS at the paper's fixed step
0.002 is *stable* on this simulated series, whereas the paper reports many
divergent NUTS transitions on the real series; the fixed paper tuning
(δ = 0.3 per macro step, up to 8 macro steps per orbit) accumulates
orbit-level energy ranges above 2 in 13% of orbits, consistent with Appendix
C's inflation factor `K` rather than with the paper's flat energy plot.

What did hold:

* Arm F reaches the same posterior as NUTS with clean health apart from one
  exhaustion, and its refinement lands at micro steps 4e-4–8e-4 — 4–5
  halvings below `h/8` on every macro step, so the paper's `h = 0.1` is far
  too coarse for this fixture and most of arm F's cost (2,594 calls per
  transition, 44% reversibility rejections) is spent rejecting coarse
  attempts.
* **Arm A (Appendix C adaptation) is the best arm**: it passes every gate,
  lands δ ≈ 0.36–0.57 (paper 0.3) and a coarsest micro step ≈ 5e-4 that
  matches the level arm F actually selected, and delivers 2.0× the bulk ESS
  per target call of the fixed paper tuning and 1.3× that of the NUTS
  control (1.24× and 1.95× in ESS/s). Its 2.0% of orbits above Δ = 2 is what
  `p_a = 0.95` on the orbit inflation quantile is designed to produce.

Claims not supported: no statement about the real inflation series; no
cross-seed replication (one seed per arm); the NUTS control is oWALNUTS with
refinement disabled at a fixed step, not Stan/NumPyro NUTS with adaptation.

## Defects observed (reported, not fixed here)

1. **Non-finite evaluations stop the transition instead of triggering
   refinement.** The reference (`walnutpie/util.hpp`) maps a failed
   `logp_grad` to `−∞` with a zero gradient and its `micro` loop keeps
   halving; oWALNUTS stops the transition with `InvalidEvaluation` at the
   first recoverable error or non-finite state, including inside a *coarse
   attempt that would have been refined away*. On this target that turned
   65–100% of transitions into no-ops until the study target emulated the
   reference semantics (bounded exponent, gradient clipping to ±1e8, finite
   penalty −1e10; amendments 2 and 7). This is a kernel parity gap that any
   stiff real model will hit.
2. **Paper Γ-rule under all-invalid transitions:** with every transition
   stopping at zero built leaves, the unrefined-fraction statistic reads as
   fully unrefined and dual averaging drove `h` to its `1e6` bound
   (`artifacts/superseded-start-rule-v1/summary.json`, arm A). Transitions
   with no built leaves should be excluded from the Γ statistic.
3. The reported per-transition `maximum_hamiltonian − minimum_hamiltonian`
   for refinement-exhausted transitions is constant per chain across
   transitions (e.g. 224 / 593 / 3,436 in the amendment-4 smoke); it appears
   to summarise one specific attempt rather than the orbit. Not investigated.

## Artifacts

`artifacts/{data,preflight,F,N,A,S,summary}.json`, fixture scans
(`fixture-scan/`, `fixture-scan-v2/`), superseded-run summaries
(`superseded-start-rule-v1/`, `superseded-start-rule-v2/`), and
`CHECKSUMS.sha256` over protocol, sources, binary, sampler source and
artifacts. Arm S is the amendment-7 smoke (50/100 draws) and is not evidence.
