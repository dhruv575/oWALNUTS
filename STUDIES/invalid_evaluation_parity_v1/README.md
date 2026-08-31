# Invalid-evaluation parity v1 — kernel `v10` validation

Validates the `v10` rule that a `TargetError::recoverable` result is a
zero-density point (`logp = -inf`, `grad = 0`, as upstream walnutpie maps a
failed evaluation) that refines like any over-tolerance micro-step, instead of
stopping the transition (`v9`: `StopReason::InvalidEvaluation`, counted as a
divergence). Leaf-level parity is proven separately by
`oracle/walnutpie/f5bba365_invalid_leaves` (4,000 upstream leaves against a
throwing wall, 343 touching it, 1e-11 agreement). This directory checks the
sampler-level consequences. Kernel commit `452befb`; preregistration and
amendments in `PREREGISTRATION.md`; every artifact is create-only.

```powershell
# from each sub-directory
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight artifacts/preflight.json
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample <ARM> artifacts/<ARM>.json
python analyze.py
# then, here
python summarize.py
```

## 1. Truncated Gaussian (`truncated/`, seed 90031)

`N(0, I_2)` restricted to `x_0 > 0` purely through recoverable errors; fixed
tuning h=0.9, δ=0.5, 6 levels, depth 6; 4 × 500/50,000.

| functional | R-hat | bulk ESS | tail ESS | mean (exact) | z | variance (exact) | z |
|---|---:|---:|---:|---:|---:|---:|---:|
| x₀ | 1.0001 | 47,895 | 59,391 | 0.8046 (0.7979) | +2.41 | 0.3684 (0.3634) | +2.23 |
| x₁ | 1.0001 | 44,924 | 59,053 | −0.0038 (0) | −0.80 | 1.0097 (1) | +1.62 |

Retained: 5,061,666 recoverable failures = 5,061,666 zero-density evaluations
(52% of 9.75M calls); **0 invalid-evaluation stops, 0 divergences**; every
draw has x₀ > 0; 145,836 of 200,000 transitions stop by refinement exhaustion
at the wall (the coarse step overshoots and even the finest level cannot
escape), 37,162 by outer U-turn; mean depth 1.59; 1.3 s wall.
**All preregistered gates pass** (|z| ≤ 3). Because the two x₀ moments sat at
+2.2–2.4σ with the same sign, a post-hoc, non-evidence replicate on fresh seed
90041 (amendment 2) was run: x₀ mean z −0.12, variance z −0.11, x₁ mean z
+1.87, variance z −0.12. The offset does not replicate; it is sampling
variation.

## 2. Stock–Watson without `-inf` emulation (`stock_watson/`, seeds 90011 / 90021)

WP2b's target with amendments 2 and 7 removed: non-finite evaluations return
`TargetError::recoverable`; no finite penalty, no gradient clipping, no
exponent bound. Same simulated series (`data.json` SHA-256 `df90ca84…a70b4`),
starts, draws (4 × 500/2,000), 4 threads, and gates as WP2b.

| arm | max R-hat (gated) | min bulk / tail ESS | recoverable failures (retained) | invalid-evaluation stops | div / exh / depth-cap | orbits with H range > 2 | retained calls | bulk ESS per M calls | wall | gates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| F fixed paper tuning | 1.0011 | 2,268 / 2,453 | 3,404,887 (16.5% of calls) | **0** | 0 / 1 / 0 | 13.0% | 20.57M | 110 | 48.7 s | fail (1 exhaustion, as WP2b) |
| A Appendix C (paper-mode v3 defaults) | 1.0101 (log σ²) | 630 / 1,051 | 522 | **0** | 0 / 0 / 0 | 6.8% | 2.88M | 219 | 12.2 s | fail by 0.0001 on R-hat |

WP2b (v9, `-inf` emulated target-side): F 1.0016, 2,156/1,777, 13.2% > 2,
20.75M calls, 104/M; A 1.0031, 1,363/2,088, 2.0% > 2, 6.45M calls, 211/M.
WP2b's recoverable-policy runs under v9 produced 65–100% no-op transitions.

Predictions: no-op transitions 0 in both arms — **held**; recoverable
failures > 0 and equal to zero-density evaluations — **held** (3,404,887 and
522); arm F statistical gates pass and ESS/call within ±30% of WP2b — **held**
(110 vs 104/M; the single exhaustion recurs); arm A passes every gate —
**failed narrowly**: log σ² rank R-hat 1.0101 against ≤ 1.01 (all other
functionals, health and ESS gates pass; ESS/call 219 vs 211/M within ±30%).
Arm A is one seed at paper-mode v3 defaults (v1 in WP2b) and used 37% fewer
calls; the R-hat miss is reported as a gate failure, not explained away.
Arm F's 16.5% recoverable-call rate with zero no-ops is the headline: the
kernel now refines through the non-representable region exactly as the
reference does.

## 3. Funnel gate on `v10` (`funnel/`, seed 90001)

WP6 arm F (h=0.36, δ=0.21, 10 levels, depth 10) at 4 × 2,000/20,000.

| P(ω<−5) (exact 0.0478) | P(ω<−6) (exact 0.0228) | var ω (exact 9) | R-hat ω / x₁ | bulk/tail ESS ω | div / inval / exh / cap | calls | wall |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.0464 (z −0.17) | 0.0206 (z −0.38) | 8.65 | 1.0077 / 1.0043 | 601 / 686 | 0 / 0 / 0 / 7 | 3.27M | 1.6 s |

**All gates pass**; the funnel never returns a recoverable error at this
tuning, so `v10` reproduces `v9`'s unbiased result (WP6 F50: 0.0474 / 0.0223 /
9.04).

## Verdict

`v10` removes the no-op-transition defect (WP2b defect 1) with reference
semantics: zero invalid-evaluation stops in 216,000 retained transitions across
three targets while 8.5M recoverable evaluations occurred; the truncated
target is stationary; the funnel result is unchanged. Not established here:
cross-seed replication of the Stock–Watson arms, and any claim about arm A's
R-hat beyond "1.0101 on one seed".

Artifacts and sources are pinned in `CHECKSUMS.sha256`; aggregate in
`artifacts/summary.json` and `RESULTS.md`.
