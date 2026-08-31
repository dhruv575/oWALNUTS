# paper_funnel_adaptive_v1 — preregistration

Frozen 2026-08-31 on kernel `v9`
(`ALGORITHM_REVISION = walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`) and
paper adaptation `walnutpie-paper-adaptation-kquantile-gamma-v1`, before any
sampling in this directory.

Question (WP2 arm A, phase 2): starting from conservative tuning, does the
JMLR Appendix C warmup (K-quantile `delta` rule, eq. 41–42; `Gamma`-target
macro step rule, eq. 43) find a `delta`/`h` that gives an unbiased and
efficient funnel sampler on the corrected kernel, and where does it land
relative to the paper's auto-tuned `delta = 0.21`, `h0 = 0.36`?

What the paper says (extracted text `paper_funnel_reproduction_v1/paper_text.txt`,
Appendix C and Figures 11–12): `p_a` is given only as an example (0.95),
`Gamma = 0.8` "typically works well", and **no numeric `Delta` is stated**.
The funnel values `delta = 0.21`, `h0 = 0.36` are described as "auto-tuned",
i.e. outputs of this warmup with an unstated `Delta`. At the fixed point of
eq. 42, `delta = Delta / q_{p_a}(K)` with `K = range/delta` implies
`Delta = q_{p_a}(H_max − H_min)` measured at that `delta`. Arm AD therefore
uses `Delta*` = the pooled retained 0.95-quantile of the orbit energy range at
the paper's fixed tuning, measured by calibration arm C and rounded to two
significant digits. This rule is fixed here before C is run.

Target, starts, functionals, and gates are identical to
`funnel_bias_fix_v1` (10-D Neal funnel, dispersed starts ω ∈ {−3, −1, 1, 3},
identity mass, 10 refinement levels, depth 10, min micro 1, 2,000 discarded,
4 chains, 1 thread).

Arms and fresh seeds (chain `i` uses `base_seed + i`; none of 87001–87024
appears as a seed in any ledger or study):

* `C` — fixed `h = 0.36`, `delta = 0.21`, 4×5,000 retained, base 87021.
  Calibration only; non-evidence.
* `A2` — paper adaptation, `Delta = 2`, `p_a = 0.95`, `Gamma = 0.8`, from
  `delta = 1.0`, `h = 0.1`; mass adaptation off; 4×50,000 retained; base 87001.
  Primary.
* `AD` — as A2 with `Delta = Delta*`; base 87011. Secondary. Added to
  `protocol.json` after C with its `Delta*` value; nothing else changes.
* `F9` — control: `funnel_bias_fix_v1` arm F50 (seeds 85001–85004, artifact
  SHA-256 `b0d51a5e…`), not rerun.

Gates per adaptive arm (all must hold to pass):

1. `|P(ω<−5) − 0.04779| ≤ 0.009`, `|P(ω<−6) − 0.02275| ≤ 0.006`;
2. `var(ω) ∈ [8.2, 9.8]`;
3. zero retained divergences, invalid evaluations, and refinement exhaustions;
4. rank R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on ω and x₁.

Reported, not gated: final `delta`/`h` per chain and their max/min ratio;
per-window `K` quantile, `delta` before/after, unrefined fraction, `h`
before/after; retained target calls, ESS per target call vs F9, depth and
refinement-level histograms, stop reasons, retained-orbit energy-range
quantiles.

Predictions (committed):

* P1. Both A2 and AD pass gates 1–3: retained draws use a fixed kernel and the
  `v9` leaf semantics are correct at any tuning, so adaptation cannot bias.
* P2. A2 lands at `delta ≈ 1.0–1.7` (K-quantile clamp `q.max(1)` with observed
  `K ≈ 1.3–2.8`) and `h ≈ 0.4–0.6`; AD lands at `delta ∈ [0.12, 0.35]` and
  `h ∈ [0.25, 0.55]`.
* P3. Bulk ESS(ω) per retained target call: A2/F9 ≥ 0.7 (looser `delta` means
  fewer micro steps per macro step but more reverse-coarser stops and larger
  orbit energy range, roughly cancelling); AD/F9 ∈ [0.8, 1.25].
* P4. Chain-to-chain spread of final `delta` is ≤ 2× in both arms and of
  final `h` ≤ 1.5×.

Decision rule: paper adaptation is recommended as the documented default for
hard targets only if P1 holds for both arms and at least one arm satisfies
P3 with ESS/call ≥ 0.8 × F9. If P1 fails, the adaptation is not release-ready
regardless of efficiency and the telemetry is used to name the rule at fault.
