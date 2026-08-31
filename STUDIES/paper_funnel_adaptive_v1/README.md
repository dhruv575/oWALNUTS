# paper_funnel_adaptive_v1 — Appendix C warmup on the funnel (WP7)

Question: starting from conservative tuning (`delta = 1.0`, `h = 0.1`), does
the JMLR Appendix C warmup implemented by WP1 (`WarmupConfig::with_paper_adaptation`,
revision `walnutpie-paper-adaptation-kquantile-gamma-v1`) on kernel `v9`
find a `delta`/`h` that gives an unbiased and efficient 10-D Neal funnel
sampler, and where does it land relative to the paper's auto-tuned
`delta = 0.21`, `h0 = 0.36`?

Evidence class: preregistered fresh-seed diagnostic (`PREREGISTRATION.md`,
`protocol.json`). Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`.
Control F9 is `funnel_bias_fix_v1` arm F50 (fixed paper tuning, seeds
85001–85004), not rerun.

## What the paper specifies

The extracted paper text gives `p_a` only as an example (0.95), says
`Gamma = 0.8` "typically works well", and states **no numeric `Delta`**.
The funnel values `delta = 0.21`, `h0 = 0.36` are described as "auto-tuned".
At the fixed point of eq. 42, `Delta = q_{p_a}(H_max − H_min)` evaluated at
that tuning, so arm AD used `Delta*` = the pooled retained 0.95-quantile of
the orbit energy range measured at the paper's fixed tuning (calibration arm
C: `q95 = 0.7191`, rounded to `0.72`). The rule was frozen before C ran.

## Results (4 chains, dispersed starts ω ∈ {−3, −1, 1, 3}, 2,000 discarded, 4×50,000 retained)

| arm | Δ | final δ per chain | final h per chain | R-hat ω/x₁ | bulk/tail ESS ω | var ω (exact 9) | P(ω<−5) (exact .0478) | P(ω<−6) (exact .0228) | q1% (exact −6.98) | div/inval/exhaust/depth-cap | retained calls | bulk ESS/call ×F9 | tail ESS/call ×F9 | gates |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F9 (control, fixed) | — | 0.21 | 0.36 | 1.0016/1.0010 | 1,644/2,134 | 9.04 | 0.0474 (z −0.08) | 0.0223 (z −0.14) | −7.01 | 0/0/0/43 | 7,939,792 | 1.00 | 1.00 | pass |
| A2 (Δ=2, paper example constants) | 2.0 | 1.304, 1.471, 1.576, 1.350 | 0.181, 0.225, 0.430, 0.414 | 1.0031/1.0021 | 1,501/1,448 | 8.80 | 0.0423 (z −0.97) | 0.0186 (z −1.05) | −6.67 | 0/0/0/206 | 8,841,164 | **0.82** | 0.61 | **pass** |
| AD (Δ*=0.72, calibrated) | 0.72 | 0.402, 0.407, 0.419, 0.422 | 0.087, 0.337, 0.295, 0.232 | 1.0018/1.0012 | 1,437/1,242 | 8.94 | 0.0431 (z −0.78) | 0.0209 (z −0.43) | −7.20 | 0/0/0/488 | 12,744,552 | 0.54 | 0.36 | **pass** |
| C (calibration, fixed, 4×5k) | — | 0.21 | 0.36 | 1.0065/1.0045 | 184/283 | 9.07 | 0.0588 (z +0.87) | 0.0249 (z +0.24) | −7.02 | 0/0/0/0 | 770,374 | — | — | n/a (calibration) |

Gates per adaptive arm: `|ΔP(ω<−5)| ≤ 0.009`, `|ΔP(ω<−6)| ≤ 0.006`,
`var(ω) ∈ [8.2, 9.8]`, zero retained divergences/invalid/exhaustions, rank
R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on ω and x₁. Both adaptive arms pass all
gates. Preflight started zero target callbacks (`artifacts/preflight-all.json`).
Wall: A2 6.5 s, AD 10.2 s, one thread.

### Adaptation trajectories (`step_after` / `max_error_after` at each update point; chain order = start ω −3, −1, 1, 3)

A2 (Δ = 2): δ paths end at 1.30–1.58 with `K95` 0.9–2.0 (the `q.max(1)` clamp
pinned δ at Δ = 2 in windows 1–2 of every chain). h paths per window:
chain 0 `0.60, 0.18, 0.21, 0.12, 0.45, 0.71, 0.54`;
chain 1 `0.12, 0.07, 0.09, 0.83, 0.22, 0.54, 0.96`;
chain 2 `0.06, 0.32, 0.52, 0.21, 0.82, 0.26, 0.60`;
chain 3 `0.43, 0.07, 0.43, 0.52, 0.34, 0.57, 0.56`.
Window unrefined fractions were 0.78–0.82 everywhere (the Γ rule hits its
target inside each window).

AD (Δ = 0.72): δ converges tightly to 0.40–0.42 (spread 1.05×) with
`K95` 1.6–1.9. h paths: chain 0 `0.11, 0.43, 0.53, 0.36, 0.19, 0.25, 0.05`;
chain 1 `0.80, 0.55, 0.09, 0.54, 0.18, 0.46, 0.67`;
chain 2 `1.33, 0.04, 0.52, 0.28, 0.79, 0.05, 0.29`;
chain 3 `0.14, 0.03, 0.37, 0.49, 0.50, 0.38, 0.43`.

Retained orbit energy-range `q95`: C 0.72, A2 1.82, AD 0.78 — i.e. both
adaptive arms sit at the eq. 42 fixed point `q95(range) ≈ Δ`, as they should.

### Post-hoc (non-preregistered, not evidence): unrefined fraction at the paper's own tuning

Arm CU (`artifacts/posthoc-CU.json`, both paper rules disabled, fixed
h = 0.36, δ = 0.21, seed base 87031) measured the per-window fraction of
unrefined macro leaves at the paper's tuning: chain 0 `0.02, 0.00, 0.21, 0.76,
0.65, 0.47, 0.46`; chain 1 `0.56, 0.74, 0.52, 0.71, 0.55, 0.73, 0.60`;
chain 2 `0.75, 0.62, 0.86, 0.79, 0.76, 0.39, 0.38`; chain 3 `0.21, 0.00, 0.46,
0.60, 0.56, 0.51, 0.68`. The paper's funnel tuning therefore does **not**
satisfy `P(micro = 1) = 0.8`; its unrefined fraction is ~0.4–0.75 and strongly
position dependent. A `Gamma = 0.8` rule is not the rule that produced
`h0 = 0.36`, or it was evaluated on a different region of phase space.

## Predictions

* P1 (both arms unbiased and healthy): **held**. Retained draws use a fixed
  per-chain kernel and `v9` leaf semantics are exact; adaptation cannot bias.
* P2 (landing): A2 predicted δ ≈ 1.0–1.7, h ≈ 0.4–0.6 — δ held, h partly
  (0.18–0.43). AD predicted δ ∈ [0.12, 0.35], h ∈ [0.25, 0.55] — **failed**:
  δ = 0.40–0.42, h = 0.09–0.34. The calibrated Δ* reproduces the fixed-point
  *invariant* `q95(range) = Δ*` but not the paper's (δ, h) pair, because the
  δ rule's fixed point is a curve in (δ, h), not a point: at (0.21, 0.36)
  `K95 = 0.72/0.21 = 3.4`; at (0.41, 0.25) `K95 = 0.78/0.41 = 1.9`; both
  satisfy `δ = Δ*/K95`. Which point is reached is decided by the h rule.
* P3 (efficiency): A2/F9 bulk ESS/call 0.82 (predicted ≥ 0.7) — **held**;
  AD/F9 0.54 (predicted [0.8, 1.25]) — **failed**. Tail ESS/call: A2 0.61,
  AD 0.36 (not preregistered, reported).
* P4 (spread): δ spread 1.21× (A2) and 1.05× (AD) — held; h spread 2.38×
  (A2) and 3.86× (AD) versus predicted ≤ 1.5× — **failed**.

## Interpretation

1. **The δ rule works as specified.** The K-quantile update is closed-form
   correct (WP1 tests), converges within a few windows, and lands both arms
   exactly on the eq. 42 invariant. The paper's default-free Δ is the knob:
   Δ = 2 gives δ ≈ 1.3–1.6 on the funnel; Δ = 0.72 gives δ ≈ 0.41.
2. **The h rule is the unstable component.** The `Gamma`-targeted dual
   averaging tracks its 0.8 target inside every window, but the statistic it
   targets (the unrefined fraction) is strongly position dependent on the
   funnel (post-hoc CU: 0.0–0.86 across windows at fixed tuning), and dual
   averaging is restarted after every δ installation, so each window is a
   short independent episode. The installed h therefore reflects where the
   chain happened to be during the last window: swings of 10–30× between
   consecutive windows and final per-chain h from 0.045 to 0.96. This is the
   same start/position sensitivity the Neal v2/v3 studies measured for the
   acceptance-driven adapter, now reproduced for the paper's rule. It is not
   an implementation defect relative to Appendix C (the paper specifies the
   target, not the update), so no `src/` change was made.
3. **Efficiency is below fixed paper tuning.** A2 keeps 82% of F9's bulk
   ESS/call (61% tail); AD keeps 54% (36%), mostly because chain 0's h
   collapsed to 0.087 (its last window sat in the neck), producing 488
   depth-10 caps and 60% more target calls.

## Verdict against the preregistered decision rule

The rule ("P1 for both arms and at least one arm with bulk ESS/call ≥ 0.8 ×
F9") is satisfied by A2 at 0.82 — narrowly, on the bulk criterion only. I do
not recommend making paper adaptation the documented default for hard
targets on that basis: P4 failed by 1.6–2.6×, tail efficiency is 0.36–0.61×,
and the h rule's window-to-window instability means the retained kernel is a
draw from a wide distribution of h rather than a tuned value. Recommendation:
ship the mode as documented **opt-in** (unbiased, health-clean, δ rule
reliable) with this study cited, and stabilise the h rule before any default
change — the two obvious candidates are (a) do not restart dual averaging at
δ installations (carry the averaged iterate), and (b) target the unrefined
fraction pooled across chains or across all completed windows rather than
per chain per window. Both are generic changes and must be preregistered
separately; neither was made here.

## Files

`protocol.json`, `PREREGISTRATION.md`, `src/main.rs`, `analyze.py`,
`artifacts/{preflight-C-A2,preflight-all,C,A2,AD,posthoc-CU,summary}.json`,
`CHECKSUMS.sha256`. Reproduce with
`cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample A2 out.json`
and `PYTHONIOENCODING=utf-8 python analyze.py`; artifact outputs refuse to
overwrite.
