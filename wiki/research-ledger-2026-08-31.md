# oWALNUTS research ledger (2026-08-31 program)

Entries follow the Polyscope ledger template. Newest last.

### WP3-1 — outer-selection-bps-vs-multinomial-v1 (reverse ablation of the outer join)
- Ordered time: 2026-08-31T06:22Z (analysis completion; sampling seconds earlier).
- Protocol/config: `STUDIES/outer_selection_bps_vs_multinomial_v1/protocol.json`
  SHA-256 `1ef8074f2a5fc1f3003003e0da1287247245a99b3314e42228cd3d77f6c6c3d1`;
  sampler revision `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v8`
  (`src/walnutpie.rs` `3e8af684…6e02ac`, `src/kernel.rs` `c0cdec7b…5de1d46`);
  exact v38 noncentered Eight Schools density and four frozen starts; 4
  sequential chains; 1,000 discarded / 1,000 retained; initial step 0.3, depth
  8, refinement levels 8, `max_error` 1.0, divergence threshold 1,000; target
  acceptance 0.95 with dual-averaged step and Welford diagonal mass; arms differ
  only in `OuterOrbitSelection::{BiasedProgressive, ExactNormalizedMultinomial}`;
  10,000,000-call and 120 s caps per cell.
- Seeds: 82001–82003 consumed (both arms, identical starts); no reserved seeds.
- Status: exploratory sampling evidence (preregistered; three seeds; not
  confirmation).
- Outcome: **pass** — primary ratio BPS/multinomial of bulk ESS per retained
  target call (geomean over six functionals) = **1.7453** ≥ 1.10; all safety
  gates held (zero retained divergences/invalid stops in all 24 chains; depth-cap
  delta 0.000; min tail-ESS/call ratio 1.4387; min squared-functional
  bulk-ESS/call ratio 1.6398). All six cells passed health gates.
- Diagnostics: BPS max rank R-hat 1.00303/1.00160/1.00226, min bulk ESS
  2328/2100/2079, min tail ESS 1628/1552/1192, retained calls
  61,871/49,253/63,986, wall 0.099/0.085/0.107 s. Multinomial max R-hat
  1.00344/1.00629/1.00547, min bulk ESS 1139/1143/1244, min tail ESS
  670/1247/991, retained calls 51,945/51,445/62,794, wall 0.087/0.083/0.097 s.
  Self-retention 0.39% (BPS) vs 10.74% (multinomial); lag-1 ACF lower by
  ≈0.3 on every functional under BPS; mean depth 3.77 vs 3.67, leaves built
  13.46 vs 12.62, calls/transition 14.59 vs 13.85; E-BFMI 0.856–1.014 vs
  0.836–1.052. Zero maximum-depth stops in every cell.
- Artifacts: `artifacts/summary.json` SHA-256
  `ecede7fec16818b38b458efc12e4d18f9c81b4098eb19329e411f3dcf98a4c01`;
  runner `src/main.rs` `317a54a1…f63170`; raw cells and `RESULTS.md` pinned in
  `CHECKSUMS.sha256`.
- Conclusion: the biased-progressive outer join is a material efficiency lever
  (≈43% more bulk ESS and ≈30% more tail ESS per gradient on this target) and
  the production default stands. The mechanism is selection (near-zero
  self-retention, reduced lag-1 autocorrelation), not trajectory length.
  Claims not supported: this does not explain the NextStat public-API gap
  (oWALNUTS already uses BPS); no cross-target generality; no source change.
- Next decision: freeze; close the "progressive selection" clue from the
  clean-room study; remaining NextStat decomposition items are adaptation,
  density specialization, and random-start sensitivity.

### WP2-FUNNEL-REPRO-V1 — paper Neal's-funnel reproduction at fixed paper tuning
- Ordered time: 2026-08-31, approximately 02:20–02:45 local (UTC−4); artifacts carry file
  mtimes; preflight preceded sampling.
- Protocol/config: `STUDIES/paper_funnel_reproduction_v1/protocol.json` and
  `PREREGISTRATION.md` (frozen before sampling; hashes in `CHECKSUMS.sha256`).
  Target: 10-D Neal funnel, arXiv 2506.18746 eq. (32). Primary arm F: oWALNUTS
  `KernelTuning(h=0.36, depth 10, min micro 1, 10 refinement levels, δ=0.21)`,
  identity `DiagonalMass`, no `WarmupConfig`, 4 chains from ω ∈ {−3,−1,1,3},
  2,000 discarded + 10,000 retained; F50 = 50,000 retained; N11 = no refinement,
  h=0.11, no local cap (fixed-step NUTS control); N36 = no refinement at h=0.36,
  δ=0.21. Reference arms R0/R1: Flatiron `walnutpie` 0.0.3 PyPI wheel via
  `walnuts_pyfunc`, same δ, 9 halvings, 10 doublings, identity inverse metric,
  R0 zero warmup (its own step search gives per-chain steps 0.127/0.36/1.018/1.018),
  R1 as shipped with 1,000 adaptive warmup. Runtime callback budget
  `min(1e9, exact worst case)`; wall cap 1,200 s per arm. Binary built from the
  working tree while WP1 was editing `src/`; post-hoc arm FT (same seed, rebuilt
  binary) is bit-identical to F, so the fixed-kernel path did not change.
- Seeds: consumed base seeds 81001 (F), 81101 (F50), 81201 (N11), 81301 (N36);
  reference seeds 81001 (R0, R1). Post-hoc: 81001 (FT), 81401 (G), 81501 (S),
  81601 (M8), reference single-chain seeds 81001, 81005, 81006, 81009 (R36;
  81002–81004, 81007, 81008 tried and discarded because their step search did
  not land on 0.36).
- Status: confirmed sampling evidence for the preregistered arms; post-hoc arms
  are exploratory mechanism probes, not evidence.
- Outcome: **paper-claim gates failed for oWALNUTS; passed for the reference.**
  F: P(ω<−5)=0.0959 vs exact 0.0478 (±0.0175), P(ω<−6)=0.0509 vs 0.0228
  (±0.0122), var(ω)=11.06, health clean. F50: 0.0971 ± 0.0090 (z≈10.7),
  0.0557 ± 0.0063, var 11.41, 17 retained refinement exhaustions and 64 depth
  caps in 200,000 transitions; convergence gates pass (R-hat 1.0053, bulk/tail
  ESS ω 1,162/2,147). N11 reproduces the paper's NUTS failure (0.0163, ω never
  below −5.7). N36: 77% refinement exhaustion, R-hat 1.43. R0/R1 tail mass
  within interval. Post-hoc R36 (reference at exactly h=0.36, identity metric,
  4×30,000): P(ω<−5)=0.0477 (z −0.01), P(ω<−6)=0.0217 (z −0.25), 1% quantile
  −6.978 vs exact −6.979, var 8.87, R-hat 1.0042. Post-hoc G (10-D N(0,I), same
  tuning): exact (all |z|<1.3, tails 0.0213–0.0245 vs 0.0228). Post-hoc S
  (h=0.005625, no refinement, depth 14): 0.0350 (z −1.4), 0.0137 (z −1.4).
  Post-hoc M8 (min micro 8, 7 levels): chains trapped below ω=−8 with 99%
  exhaustion, R-hat 1.19.
- Diagnostics: F retained stop mix outer U-turn 22,677 / recursive 3,419 /
  reverse-coarser-accepted 13,904 (34.8%); reverse-coarser stops 31–42% even
  for ω>0 where mean selected level <0.5. Trace kinetics: escape
  P(ω′≥−5|ω<−5)=0.081, entry P(ω′<−5|ω≥−5)=0.0086 (implied neck mass 0.096 =
  observed); arm S entry 0.0031 (implied 0.035). Target calls: F 2,858,238 in
  1.3 s; F50 12,770,697 in 7.4 s; N11 4,430,890; R36 9,939,052 (Python
  callback wall 103.7 s, not a throughput measurement).
- Artifacts: `STUDIES/paper_funnel_reproduction_v1/artifacts/{preflight,F,F50,N11,N36,R0,R1,summary}.json`,
  `artifacts/posthoc-{FT,G,S,M8,R36}.json`, `artifacts/posthoc-summary.json`,
  `artifacts/posthoc-R36-summary.json`; every SHA-256 in
  `STUDIES/paper_funnel_reproduction_v1/CHECKSUMS.sha256`.
- Conclusion: **oWALNUTS's fixed kernel is biased on Neal's funnel at the
  paper's tuning — it places about twice the correct mass in the neck — while
  the reference implementation at identical tuning is exact.** The bias is
  absent on a Gaussian and absent when refinement is disabled, so it lives in
  the refinement/reverse-check path, not in orbit construction or selection.
  Claims not supported: any statement that oWALNUTS reproduces the paper's
  funnel result; any funnel efficiency comparison using the current kernel.
  The paper's NUTS-side claim is supported (N11).
- Next decision: **stop** funnel tuning/adaptation work on the current kernel;
  open a defect hunt in the refinement/reverse-check path. Concrete first
  steps: (1) unit-test that no reverse check runs at level 0 (`num_steps ==
  1` returns reversible in the reference) and count reverse checks per level;
  (2) extend the walnutpie oracle fixtures with funnel-like leaves (large
  forward level, flat reverse region, and the exhaustion-then-stop case) and
  compare leaf acceptance bit-for-bit against `macro_step`/`reversible` in
  `walnutpie-f5bba365/include/walnutpie/walnuts.hpp`; (3) rerun arm F as the
  regression gate (P(ω<−5) within ±0.0090 of 0.0478 at 4×50,000). WP1's
  adaptive warmup must not be evaluated on the funnel until this is fixed.

### WP4-ESSGT-V1 — exact state-space ground truth versus fixed path metrics
- Ordered time: preregistered and executed 2026-08-31T06:0x–06:35Z (UTC); byte-identical re-execution at 06:33Z.
- Protocol/config: `STUDIES/exact_state_space_ground_truth_v1/protocol.json` SHA-256 `2fda8c213c3cbc67c70b7b0292840ffe386e276aee6c923d0371f984897ae928`; sampler commit `bc49ffb` (`walnutpie.rs` `1b1bcbc5…`, built from a git-archive snapshot because the live `src/` was mid-edit by WP1); centered Gaussian local-level path, globals fixed, exact tridiagonal posterior; arms I/D/P/Q (identity, posterior-variance diagonal, posterior-precision bidiagonal Cholesky, prior-precision only); depth 8, refinement 3, max error 1.0, dual-averaged step at 0.8, mass adaptation off, 500/2,000, 4 chains, prior-dispersed starts; admission 25.5M/113M per cell.
- Seeds: consumed 83001, 83003 (T=100) and 83002, 83004 (T=1000); data seed 2026083101; reserved 83011–83012 untouched.
- Status: diagnostic evidence against an exact posterior; not a benchmark or target claim.
- Outcome: 16/16 cells completed, zero-callback preflights, zero retained divergences/invalid/refinement-exhaustion stops. Cap/no-cap predictions held 16/16: I and D never cap at T=1000 (min bulk ESS ~6,000, kappa ≈ 13 independent of T); P mixes at depth 3–4 with min bulk ESS 17.8k–18.0k at T=1000 (ESS/call 0.14, 4.8× I, ~1,000× Q); Q caps 92–93% at T=1000 (step 0.0026, min bulk ESS 256–292, R-hat 1.025). Accuracy: mean z² 0.70–1.24, no |z|>5, variance ratios 0.94–1.06; one boundary accuracy-gate failure (T=100 D seed 83001, 1/100 coords at |z|=3.04) not replicated. The ±1 median-depth heuristic gate failed 9/16 because adapted steps sit ~3× below the stability limit; the Q "level direction is slow" mechanism clause was wrong (level is the stiff direction; fine-scale modes are slow).
- Diagnostics: full table in the study README and `artifacts/results-table.md`; reverse-coarser stops at level 0 in every arm (0.2–0.6% I/D/P, 5–8% Q) with no measurable bias on this target.
- Artifacts: `STUDIES/exact_state_space_ground_truth_v1/{PREREGISTRATION.md,protocol.json,README.md,analyze.py,src/main.rs,artifacts/…}`; `artifacts/summary.json` SHA-256 `a96e05928f63603bb72dbea4258d6de4532459867df986545f74e0aab5d6887f`; all hashes in `CHECKSUMS.sha256`; raw draws reproducible, not committed.
- Conclusion: the T=1000 phenomenology in the Polyscope ledger (83–92% caps, collapsed steps, ESS < 10) is reproduced in a controlled Gaussian by prior-based path metrics and eliminated by the posterior-precision tridiagonal metric, which the facade already represents. Not supported: any claim about the real target's global–path coupling or the globals' geometry.
- Next decision: freeze a fresh-seed canonical-v2 a=1 diagnostic with globals frozen (Kalman truth), arms I and P; then release (mu, log sigma_x) with a boundary-refreshed posterior-precision path block plus rank-2 arrowhead. No sspd-10 sampling authorised.

### WP6-FUNNEL-BIAS-FIX-V9 — root cause and correction of the funnel neck over-weighting
- Ordered time: 2026-08-31, after WP2-FUNNEL-REPRO-V1 and WP4-ESSGT-V1; kernel commit `29621b8`, study commit follows it.
- Protocol/config: `STUDIES/funnel_bias_fix_v1/protocol.json` SHA-256 `5079aba976d3343e7e1c0ed0a736252ab294804953b9d7b8f180ad5f5348dffb`; `PREREGISTRATION.md` `cf86a119e95e9eddf6c01da9936ca31fd4202cbd483bca908077d7bee5aad40a`; sampler revision `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9` (`src/kernel.rs` `23fd69c4…`, `src/walnutpie.rs` `22928d30…`); WP2 target/starts/tuning (10-D funnel, h=0.36, δ=0.21, 10 levels, depth 10, min micro 1, identity mass, 2,000 discarded, 4 chains, 1 thread); WP2 gates plus fix gates |ΔP(ω<−5)| ≤ 0.009, |ΔP(ω<−6)| ≤ 0.006, var(ω) ∈ [8.2, 9.8], zero retained divergences.
- Seeds: consumed 85001–85004 (F50), 85101–85104 (F), 85201–85204 (Gaussian G); Eight Schools regression reused WP3's seed 82001 with WP3's runner (both arms) as a paired `v8`/`v9` comparison, not fresh evidence for WP3's claim.
- Status: confirmed correction; root cause identified by differential oracle against the unmodified upstream implementation.
- Root cause: `kernel::integrate` decided micro-step acceptance on `max_j |H(z_j) − H(z_0)|` over every visited micro-step (documented as the "inclusive full-trajectory" tolerance) and the pinned macro-leaf oracle carved out the three upstream cases that disagreed as an intended "health correction". Upstream `walnutpie::macro_step`/`within_tolerance` decide on `|H(end) − H(start)|` only. The path-wide statistic is not symmetric under time reversal (reverse departures are measured from `H(z_ℓ)`), so the deterministic reverse selection could differ from the forward one while the kernel only re-checks *coarser* levels; non-reversible leaves were accepted and the funnel neck was over-weighted. A 4,000-leaf funnel oracle generated by the upstream headers (`oracle/walnutpie/f5bba365_funnel_leaves`, `funnel_leaf_cases.json` `7ed7ad47…`) disagreed with `v8` on 1,555 leaves (wrong acceptances, wrong rejections, different selected levels, different adaptation statistics) and agrees with `v9` on all 4,000 to 1e-11.
- Outcome: **all primary gates pass.** F50: P(ω<−5) 0.0474 vs 0.0478 (z −0.08), P(ω<−6) 0.0223 vs 0.0228 (z −0.14), var(ω) 9.04, q1% −7.01 (exact −6.98), mean ω +0.041 (MCSE 0.074), rank R-hat 1.0016/1.0010, bulk/tail ESS ω 1,644/2,134, 0 divergences / 0 invalid / 0 exhaustions / 43 depth caps in 200,000 transitions, 8,209,439 calls (v8: 12,770,697), 4.1 s. F (4×10k): z −0.29/−0.47, var 8.63, all gates pass. WP2's `v8` F50 at the same tuning was 0.0971/0.0557, var 11.41.
- Diagnostics: Gaussian G exact (mean z 0.16/−0.29, var 1.012/1.001, tail z 0.98/−0.50, zero health events). Eight Schools 82001 healthy under `v9` (max R-hat 1.0020/1.0026, min bulk ESS 1,907/1,233, zero divergences/depth caps); geomean bulk ESS/call `v9`/`v8` 0.84 (BPS) and 0.91 (multinomial) on one 4×1,000 seed — within ESS noise, reported not interpreted; BPS/multinomial remains 1.41×. All 142 crate tests, strict Clippy, fmt, and `-D warnings` rustdoc pass; no locked fingerprint changed because the frozen default tuning never reaches a leaf where the two statistics differ.
- Artifacts: `STUDIES/funnel_bias_fix_v1/{PREREGISTRATION.md,protocol.json,README.md,src/main.rs,src/eight_schools.rs,analyze.py,artifacts/…}`; `artifacts/F50.json` `b0d51a5e…`, `artifacts/summary.json` `67f923ec…`; full hashes in `CHECKSUMS.sha256`. Oracle: `oracle/walnutpie/f5bba365_funnel_leaves/{generate_funnel_leaves.cpp,funnel_leaf_cases.json,README.md,SHA256SUMS.txt}`; test `src/oracle_tests/funnel_leaf.rs`.
- Conclusion: the funnel bias was a kernel correctness defect in the acceptance statistic, not tuning; `v9` restores exact upstream leaf semantics and the paper's funnel marginal is reproduced at the paper's tuning. Claims not supported: that `v8` results on refinement-active targets (any `max_refinement_levels > 1` run that actually refined) are unbiased — every such prior study result is provisional until re-run under `v9`; that the WP2 arm-F ESS numbers are the kernel's efficiency (they were measured on a biased kernel).
- Next decision: ship `v9`; re-run refinement-active prior evidence (Neal funnel pilots v1–v3, Stock–Watson WP2b if it ran on `v8`, Eight Schools v38 timing) under `v9` before any external claim; WP1's paper adaptation may now be evaluated on the funnel.

### WP7-FUNNEL-ADAPTIVE-V1 — JMLR Appendix C warmup on the funnel (phase-2 arm A)
- Ordered time: 2026-08-31, after WP6-FUNNEL-BIAS-FIX-V9; kernel HEAD `1666dbb` (`v9`), paper adaptation `walnutpie-paper-adaptation-kquantile-gamma-v1`.
- Protocol/config: `STUDIES/paper_funnel_adaptive_v1/protocol.json` SHA-256 `1728d58bd6ea025e190985bda8a409826c1c3919957cba7b056327d9b54d7d92`; `PREREGISTRATION.md` `af0ab43d7014a586dcb9e8f659c3140fc69034fc341e3718aae61fb0cde09a5d`; 10-D Neal funnel, identity mass, 10 refinement levels, depth 10, min micro 1, 4 chains from ω ∈ {−3,−1,1,3}, 2,000 discarded (paper adaptation, mass adaptation off) + 4×50,000 retained, one thread, 1e9 callback cap, 1,200 s wall cap; conservative start δ = 1.0, h = 0.1; arms A2 (Δ = 2, p_a = .95, Γ = .8) and AD (Δ* = 0.72 = calibration-arm pooled q95 of the retained orbit energy range at the paper's fixed tuning, rule frozen before calibration); control F9 = `funnel_bias_fix_v1` F50 (not rerun). Gates as WP6 plus rank R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on ω and x₁.
- Seeds: consumed 87021–87024 (C, calibration), 87001–87004 (A2), 87011–87014 (AD), 87031–87034 (post-hoc CU, non-evidence). No confirmation seeds exist for this study.
- Status: preregistered diagnostic evidence; post-hoc CU labelled non-evidence.
- Outcome: **both adaptive arms pass every gate**; the preregistered default-recommendation rule is met only narrowly (A2 bulk ESS/call 0.82 × F9) and P2/P4 failed. A2: final δ 1.30–1.58, h 0.18–0.43 (spread 2.38×), P(ω<−5) 0.0423 (z −0.97), P(ω<−6) 0.0186 (z −1.05), var(ω) 8.80, R-hat 1.0031, bulk/tail ESS ω 1,501/1,448, 0/0/0 div/inval/exhaust, 206 depth caps, 8,841,164 retained calls, bulk ESS/call 0.82× and tail 0.61× F9. AD: δ 0.402–0.422 (1.05×), h 0.087–0.337 (3.86×), P(ω<−5) 0.0431 (z −0.78), P(ω<−6) 0.0209 (z −0.43), var 8.94, R-hat 1.0018, ESS 1,437/1,242, 0/0/0, 488 depth caps, 12,744,552 calls, 0.54×/0.36× F9. Retained q95 energy range: C 0.72, A2 1.82, AD 0.78 (both arms sit on the eq. 42 fixed-point invariant q95(range) ≈ Δ).
- Diagnostics: paper text states no numeric Δ (p_a = 0.95 as example, Γ = 0.8 "typically"); δ = 0.21/h0 = 0.36 are "auto-tuned" outputs. The δ rule converges within a few windows in both arms; its fixed point is a curve in (δ, h) (K95 = 3.4 at (0.21, 0.36) vs 1.9 at (0.41, 0.25), both = Δ*/δ), so the calibrated Δ* does not recover the paper's pair. The h rule tracks Γ = 0.8 inside every window but the unrefined fraction is position dependent on the funnel (post-hoc CU at fixed paper tuning: per-window 0.00–0.86, typically 0.4–0.75 — the paper's own tuning does not satisfy Γ = 0.8) and dual averaging restarts after every δ installation, giving per-window h swings of 10–30× and final h 0.045–0.96 across chains. Preflight zero callbacks; all cells under caps; A2 6.5 s, AD 10.2 s.
- Artifacts: `STUDIES/paper_funnel_adaptive_v1/{README.md,protocol.json,PREREGISTRATION.md,src/main.rs,analyze.py,CHECKSUMS.sha256,artifacts/*}`; `artifacts/A2.json` `7e319ba1417c94460c04a75d740bb6ac202dc5554d385f1babae0ee49a09e980`; `artifacts/AD.json` `de3543b31f2f15e4409f9059ab06aa258d24c3d1bc9024cfd32c5f2a92adab2a`; `artifacts/C.json` `fb6fb5bc14fd14bb0d47b07ef5bf7c0b4f9d9a37987ed147be77068081f9997d`; `artifacts/summary.json` `75133da1d63f73c82cab261e66d280a30abc2c52530949da984f4c7823034b21`; full list in `CHECKSUMS.sha256`.
- Conclusion: supported — the Appendix C mode is unbiased and health-clean on the funnel from a conservative start, and the K-quantile δ rule is reliable with Δ as its single knob. Not supported — that it reproduces the paper's (δ, h) pair, that Γ = 0.8 is the rule behind h0 = 0.36, or that it matches fixed paper tuning in efficiency (0.54–0.82× bulk, 0.36–0.61× tail ESS/call); the h rule is position/start sensitive on the funnel. No `src/` change was made (the instability is not an implementation defect relative to the paper's stated rule).
- Next decision: ship paper adaptation as documented opt-in, not as the default for hard targets. Preregister one generic h-rule stabilisation (no dual-averaging restart at δ installs, and/or pooled/cumulative unrefined statistic) as a separate study before any default change; fixed paper tuning (δ = 0.21, h = 0.36) remains the funnel reference configuration.

### WP8-EIGHT-SCHOOLS-V9-REBENCH-V1 — paired re-measurement of the public Eight Schools throughput claim on kernel v9
- Ordered time: 2026-08-31T06:48Z; kernel HEAD `1666dbb` (`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`), after WP6-FUNNEL-BIAS-FIX-V9.
- Protocol/config: `STUDIES/eight_schools_v9_rebench_v1/protocol.json` SHA-256 `07756d5819fe5da09111aefbedc1b9154ef2f306673af1df44ed5ba953b009b6`; `PREREGISTRATION.md` `b4e7a6f0393faa5423ea85ac97cd2d0c9c0c83429a214bc50959cad0bb328404`; exact v38 strict track copied from `polyscope/STUDIES/public_owalnuts_numpyro_suite_v2/confirmation-v38/src/main.rs`: v38 noncentered Eight Schools density, four frozen starts, 4 sequential chains, 1,000 warmup + 1,000 retained, target .95, depth 8, `h=0.3`, 8 refinement levels, `max_error=1.0`, divergence threshold 1000, adapted diagonal from identity, one thread, 10M callback cap, timing strictly around `sample_chains_with_target_budget`; 5 timing repetitions per seed with bit-identity required; arviz 1.3 rank R-hat, bulk ESS, tail ESS (.05/.95); ESS/call uses total callbacks started as v38. Reference evidence: v38 `analysis-summary.json` SHA-256 `1fb8c295681a848280e126c815cb6e5f2d3a7c31682790d384af91d55c45e04f`; competitor minima from `RELEASES/owalnuts-x-2026-08-30-v3/finalized.json`.
- Seeds: paired 100070101–100070104 (the v38 evidence seeds, deliberately reused for a paired re-measurement of a frozen protocol — not fresh); fresh 88001–88003 (verified unused). No confirmation namespace.
- Status: paired re-measurement evidence for the throughput claim; not a new confirmation.
- Outcome: **claim survives v9 under both aggregations; published numbers were mislabelled.** True conservative minimum over all seven seeds and six functionals on v9: **12,830.11 bulk / 10,345.91 tail ESS/s** (2.04× CmdStan 6,290.30 bulk; 2.47× BlackJAX 4,195.13 tail); paired-4 release-style (min over functionals of seed-median) 15,373.43 / 11,530.33; fresh-3 true minimum 15,892.97 / 12,205.76. All seven v9 cells passed health (0 divergences, 0 depth caps, 0 invalid, 0 exhaustions, max rank R-hat 1.0029, min bulk ESS 1,763, min tail ESS 1,349) and every paired cell passed the v38 posterior-agreement rule against its v7 cell on all six functionals. Paired geometric-mean ESS per target call v9/v7: 0.961 bulk, 0.986 tail; total target calls within 1% per seed — the correction is cost-neutral on this target.
- Diagnostics: the release package's 19,054.65 / 14,494.34 is `summaries.rust.across_seeds.tau.{bulk,tail}_ess_per_total_second.median` in the v38 summary (min over functionals of the across-seed median), reproduced exactly by `analyze.py`; competitor figures in `validate_release.py` are true minima over all eligible cells. The like-for-like v7 minimum is 8,634.35 / 5,949.29 (seed 100070101, sampler wall 0.255 s vs 0.092–0.108 s on the other seeds), which still beat every strict competitor (1.37× / 1.42×). v9 walls 0.117–0.161 s (median of 5; ranges ≤ 0.008 s) were measured with three other agents running; wall-based v9 numbers are therefore conservative, and ESS/call is the machine-independent figure.
- Artifacts: `STUDIES/eight_schools_v9_rebench_v1/{protocol.json,PREREGISTRATION.md,README.md,RELEASE-NOTE.md,src/main.rs,analyze.py,artifacts/cell-*.json,artifacts/summary.json,artifacts/RESULTS.md,CHECKSUMS.sha256}`; `artifacts/summary.json` SHA-256 `4d8aa7aaae504797040097975ede57bd9126ee277822abf6a4a1ea31e0ce3765`; `src/main.rs` `fa52c079bb4c35b913b2fe22f5a1d399ebe5e9d64c80831236163f3624bd93d8`; `analyze.py` `8b69c706a8236a342ea02416f118002dd45451a095767946444b175aeaa77904`.
- Conclusion: supported — "fastest among strict matched competitors tested locally" on the v38 track holds on v9 with a ≥2× margin under the true conservative minimum; v9 does not change Eight Schools efficiency per gradient. Not supported — the specific published figures 19,054.65 / 14,494.34 as "conservative minima" (they are medians; the correct v7 minima were 8,634 / 5,949), and any wall-based v9 number as a clean-machine measurement.
- Next decision: publish the erratum drafted in `RELEASE-NOTE.md` with the v9 re-measured numbers; any future release package must compute the oWALNUTS aggregation with the same `minima()` rule as competitors. Re-measure on an idle machine before quoting v9 ESS/s externally.
