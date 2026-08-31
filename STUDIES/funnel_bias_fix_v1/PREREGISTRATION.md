# funnel_bias_fix_v1 — preregistration

Frozen 2026-08-31 after the kernel `v9` endpoint-criterion correction
(`ALGORITHM_REVISION = walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`) and
before any sampling in this directory.

Question: does deciding micro-step acceptance on `|H(end) − H(start)|`
(upstream `within_tolerance`) instead of the path-wide maximum departure remove
the neck over-weighting measured by `paper_funnel_reproduction_v1` (arm F50:
P(ω<−5) = 0.0971 ± 0.0090 vs exact 0.0478)?

Target, starts, tuning, and reported functionals are identical to
`paper_funnel_reproduction_v1` (10-D Neal funnel, h = 0.36, δ = 0.21, 10
refinement levels, depth 10, min micro 1, identity mass, dispersed starts
ω ∈ {−3, −1, 1, 3}, 2,000 discarded + retained draws, 4 chains, 1 thread).

Arms and fresh seeds (chain `i` uses `base_seed + i`):

* `F50` — 4×50,000 retained, base seed 85001 (chains 85001–85004). Primary.
* `F` — 4×10,000 retained, base seed 85101. Secondary (WP2 arm-F budget).
* `G` — 10-D standard Gaussian, 4×10,000, base seed 85201. Sanity.

Primary gates (arm F50, all must hold):

1. `|P(ω<−5) − 0.04779| ≤ 0.009` and `|P(ω<−6) − 0.02275| ≤ 0.006`;
2. `var(ω) ∈ [8.2, 9.8]`;
3. zero retained divergences; retained invalid evaluations and refinement
   exhaustions reported (WP2's F50 had 17 exhaustions; they are reported, not
   gated, because the exhaustion path is unchanged by this fix);
4. the WP2 convergence gates (rank R-hat ≤ 1.01, bulk/tail ESS ≥ 400 on ω and
   x₁) are reported and expected to pass at this budget.

Regression checks (not gates on the fix, reported): arm G mean/variance and
P(x₁<−2) against the exact standard normal; and one seed (82001) of
`outer_selection_bps_vs_multinomial_v1` re-run under `v9` with the copied
runner (`src/eight_schools.rs`), comparing bulk ESS per target call and health
with the `v8` cell artifacts in that study.

Decision rule: if every primary gate holds, the defect is considered fixed
and `v9` ships; otherwise the kernel change is reported as insufficient and
the differential oracle results stand alone.
