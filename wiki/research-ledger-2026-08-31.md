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

### WP2b-SW-REPRO-V1 — paper Stock–Watson SV reproduction on simulated data
- Ordered time: 2026-08-31, sampling approximately 02:50–02:55 local (UTC−4);
  preflight (zero callbacks) preceded sampling; seven preregistration
  amendments were all recorded before any evidence was interpreted.
- Protocol/config: `STUDIES/paper_stock_watson_reproduction_v1/protocol.json`
  SHA-256 `fbb03f47384685f5a09af0c1aff0065730aec4df57e4ce28b70229965742cbc9`;
  `PREREGISTRATION.md` `7b73806c…edf9ef`; runner `src/main.rs` `505b0f72…26ad1`;
  kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9` (`src/walnutpie.rs`
  `22928d30…54e2a40`, `src/kernel.rs` `23fd69c4…720eac` at checksum time).
  Target: JMLR §4.4 eqs. 35–38, shared σ, `σ⁻² ~ Gamma(5, .5)`, innovation
  parameterization, identity mass, dimension 756; simulated series (data seed
  2026083120 by preregistered range rule, `data.json` `df90ca84…a70b4`);
  starts on the simulated true paths with `φ` offsets ±0.2/±0.6 and 0.01
  jitter; 4 chains, 500 discarded / 2,000 retained, 4 threads; finite-penalty
  target policy emulating the reference's `−∞` failure semantics. Arms:
  F fixed paper tuning (h=.1, δ=.3, min 8 micro, 8 levels, depth 10);
  N NUTS-like control (h=.002, one level, δ=1000); A Appendix C adaptation
  from δ=1, h=.05 (Δ=2, p_a=.95, Γ=.8, no mass adaptation).
- Seeds: 84001 (F), 84002 (N), 84003 (A) consumed once for evidence; 84004
  consumed by non-evidence smoke arm S. Superseded start-rule/fixture runs
  reused 84001–84003 before any retained evidence existed (recorded in
  `PREREGISTRATION.md` amendments 1–7).
- Status: exploratory sampling evidence (preregistered; one seed per arm).
- Outcome: **paper claim not reproduced; adaptive arm passes.** F: all
  statistical gates pass (max R-hat 1.0016, min bulk 2,156, min tail 1,777)
  but 1 retained refinement exhaustion and 13.2% of orbits with
  `max H − min H > 2` (gate ≤ 1%). N: 1 divergence, 1 exhaustion, 99.99%
  depth-10 caps, only 0.10% of orbits above 2 (gate for the claim > 10%).
  A: all gates pass (max R-hat 1.0031, min bulk 1,363, min tail 2,088, zero
  health events), 2.0% of orbits above Δ = 2.
- Diagnostics: retained calls F 20,753,272 / N 8,191,457 / A 6,445,520; wall
  90.4 / 85.0 / 45.9 s; min bulk ESS per million calls 103.9 / 157.6 / 211.4;
  per second 23.9 / 15.2 / 29.7. F selected levels 4–5 (micro 7.8e-4–3.9e-4)
  on 86% of transitions with 44% reverse-coarser rejections; A landed
  δ = .567/.389/.362/.367 and h = .00371/.00424/.00515/.00419 (coarsest micro
  ≈ 5e-4) with window unrefined fractions .77–.81. Posterior means agree
  across arms within Monte-Carlo error.
- Artifacts: `artifacts/summary.json`
  `b0c9f88be9d551cf9ac939fab22a4551bdfaf92818c79d778d599ea1184abca3`;
  `F.json` `f77f1c51…adf1f6`, `N.json` `16a3b2bb…5feafe`, `A.json`
  `30c983f0…21abcd5`; all pinned in `CHECKSUMS.sha256`.
- Conclusion: on a simulated Stock–Watson series with paper-like latent
  ranges, the paper's fixed WALNUTS tuning is far too coarse (every macro
  step refines 4–5 halvings below h/8) and its orbit energy ranges exceed 2
  in 13% of orbits, while the fixed-step NUTS control is stable — so the
  Figure 16 contrast is data-specific and not supported here. The Appendix C
  adaptation implemented by WP1 finds a self-consistent δ/h, passes every
  gate, and is 2.0× more efficient per call than the paper tuning and 1.3×
  than the NUTS control. Not supported: any claim about the real series;
  cross-seed replication; comparison with an adapted external NUTS.
- Defects: (1) kernel parity — non-finite/recoverable evaluations stop the
  transition instead of failing the micro tolerance and halving as the
  reference does; the study had to emulate `−∞` semantics target-side.
  (2) Γ-rule counts transitions with zero built leaves as unrefined and drove
  h to the 1e6 bound under all-invalid transitions. (3) Per-transition
  Hamiltonian range for exhausted transitions is constant per chain.
- Next decision: fix defect (1) in the kernel (treat non-finite coarse
  attempts as failed tolerance), exclude zero-leaf transitions from the
  Γ statistic, then replicate arm A on fresh seeds and, if the real series
  can be obtained, on the paper's data.

### WP9-PAPER-H-RULE-STABILISATION-V2 — stabilising the Appendix C `h` rule and fixing its statistic
- Ordered time: 2026-08-31, after WP7-FUNNEL-ADAPTIVE-V1 and WP2b-SW-REPRO-V1; kernel HEAD `cfd813b` (`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`) at sampling time; paper adaptation `walnutpie-paper-adaptation-kquantile-gamma-v2` at sampling time, `v3` after the default decision (commit `8cadd94`).
- Protocol/config: `STUDIES/paper_funnel_adaptive_v2/protocol.json` SHA-256 `713c96f9ba857b1d1290d6a0c8a15af7803e059ce1806a1c730b9cacb2e533f2`; `PREREGISTRATION.md` `a916f20f34dba5cc8c5f066a8f45c668d1af4c1532b6f329c82c6c89a1cb7c21`; 10-D Neal funnel, identity mass, 10 refinement levels, depth 10, min micro 1, 4 chains from ω ∈ {−3,−1,1,3}, 2,000 discarded (paper adaptation, mass adaptation off, start δ = 1.0, h = 0.1) + 4×50,000 retained, one thread, 1e9 callback cap, 900 s wall cap per arm; eight arms = Δ ∈ {2.0, 0.72} × {control: per-transition statistic + restart at δ installs; S: cumulative statistic; R: continue through δ installs; SR: both}. Gates: WP6/WP7 bias and health gates plus final-h max/min ≤ 1.5, final-δ max/min ≤ 1.2, bulk ESS(ω)/call ≥ 0.8× and tail ≥ 0.7× F9 (`funnel_bias_fix_v1` F50, `b0d51a5e…`).
- Seeds: consumed base seeds 89001, 89011, 89021, 89031, 89041, 89051, 89061, 89071 (chains base+0..3). No confirmation seeds exist for this study.
- Status: preregistered diagnostic evidence with a preregistered default decision rule.
- Outcome: **(b) continue-through-δ-install passes every gate in both families; cumulative statistic falsified.** A2-R: δ 1.116–1.254 (1.12×), h 0.511–0.618 (1.21×), P(ω<−5) 0.0503 (z +0.53), P(ω<−6) 0.0215 (z −0.39), var 8.97, R-hat 1.0012, bulk/tail ESS ω 1,383/2,057, 0/0/0 div/inval/exhaust, 31 depth caps, 4,739,088 retained calls, 1.41×/1.61× F9 bulk/tail ESS per call. AD-R: δ 0.353–0.402 (1.14×), h 0.365–0.465 (1.27×), P(ω<−5) 0.0504 (z +0.49), P(ω<−6) 0.0248 (z +0.57), var 9.15, R-hat 1.0012, ESS 1,575/1,666, 0/0/0, 68 caps, 6,994,024 calls, 1.09×/0.89× F9. Controls: A2-C h spread 1.68 (1.24×/1.18× F9, unbiased, healthy), AD-C h spread 2.77 (0.76×/0.54×). Cumulative arms: h spread 26.4× (A2-S, 4 retained refinement exhaustions), 44.8× (A2-SR), 95.2× (AD-S), 15.1× (AD-SR), 178–12,974 depth caps, 0.12–0.47× F9. All eight arms passed the bias gates. Preflight zero callbacks; walls 2.5–29.5 s.
- Diagnostics: predictions P1 7/8, P2 held, P3 held, P4 falsified, P5 falsified, P6 held for C/R only, P7 held for (b). Mechanism for the cumulative failure: dual averaging integrates `Γ − statistic`; a lagged running mean is a persistent offset that is integrated for hundreds of transitions before the mean catches up. Also fixed in this WP (revision `v2`, commit `cfd813b`): the `v1` unrefined fraction counted leaves rejected as invalid at the coarsest level as unrefined, so an all-invalid transition read as 1.0 and drove h to the 1e6 dual-averaging ceiling (reported by WP2b); the fraction is now taken over built leaves only (kernel `refinement_level_built` histogram), leaf-less transitions contribute no sample and no step update (`PaperAdaptationUpdate::transitions_without_statistic`), and the paper-mode step is bounded to `PAPER_STEP_RELATIVE_BOUND` = 1e3 × the configured initial step. The installed step was already the dual-averaging averaged iterate (no change). Acceptance-driven warmup and all fingerprints unchanged; 103 lib + 43 facade tests, strict Clippy, fmt, rustdoc clean.
- Artifacts: `STUDIES/paper_funnel_adaptive_v2/{README.md,PREREGISTRATION.md,protocol.json,src/main.rs,analyze.py,make_readme.py,CHECKSUMS.sha256,artifacts/*}`; `artifacts/summary.json` `ca0536eb7e05003dc8e0c85c7f66e686ba6415e0d743f5f9b0f017ca9f0455d1`; `artifacts/A2-R.json` `fdd708def3ed41a54e5db61cf508664bdfa54fb8e2e75a76703117f0d41a1453`; `artifacts/AD-R.json` `54c4c43bed0a1881779ddc621efaff427dc90a41bd7eb737bad08174bce5ba03`; source commits `cfd813b` (options + v2 statistic), `e16af20` (study), `8cadd94` (v3 default).
- Conclusion: supported — restarting dual averaging at δ installations is the cause of WP7's chain-specific h; one continued stream is stable (≤ 1.3×) and at Δ = 2 more efficient than the paper's fixed funnel tuning (1.41×/1.61× F9). Not supported — the cumulative statistic as a stabiliser (harmful), and any claim about targets other than the funnel; WP7's numbers are for revision `v1` and are unchanged.
- Next decision: `PaperRestartPolicy::ContinueThroughLocalErrorInstall` is the paper-mode default (`v3`, commit `8cadd94`); `RestartOnLocalErrorInstall` and `Cumulative` remain opt-in. Paper mode is release-ready as a documented opt-in with Δ as its single knob; re-run WP2b's paper-adaptation arm under `v3` before quoting Stock–Watson adaptive results.

### WP4B-REAL-TARGET-PATH-METRIC-V1 — canonical-v2 at T=1000: NumPyro reference, centered adapted diagonal, and the posterior-precision path block
- Ordered time: preregistered 2026-08-31T05:5xZ; oWALNUTS arms executed ~06:2x–06:3xZ; NumPyro arm N ~06:25–07:05Z; post-hoc arms ~06:45–06:55Z; finalized 2026-08-31T07:11Z (UTC).
- Protocol/config: `STUDIES/real_target_path_metric_v1/protocol.json` SHA-256 `9ac8722cec8941f0260a262193f352cfdeb30ddf0917e358f3e16cf9f31ca9cb`; target `polyscope-canonical-v2` ported verbatim (oracle parity 4/4 in Rust and JAX); fixtures sspd-11 (`2fff9766…83baad`, primary), sspd-10 (`005a5c7d…687ac`, pathological), sspd-05 (`1d10f68e…8091d`, T=100 sanity); kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9` at `1666dbb` (post-hoc arms at `0a04c2d`, `src/` identical); oWALNUTS arms: depth 8, refinement 3, max error 1.0, dual-averaged step at 0.8 with initial step search, 4 chains, 500/2,000; arm N: NumPyro 0.21 NUTS, depth 12, 1,000/2,000, target 0.9, adapted diagonal, a ∈ {1, 0.75}; shared data-informed starts with `mu` offsets (sspd-11 cold factor deliberately not applied); admission 25.5M/113M per T=1000 arm, zero callbacks in every preflight.
- Seeds: consumed 86001 (sspd-11), 86002 (sspd-10), 86003 (sspd-05) for every arm; no reserved seeds.
- Status: preregistered diagnostic evidence with external reference; post-hoc arms P2/FI/FP are labelled exploratory.
- Outcome (gates: R-hat ≤ 1.01, bulk/tail ESS ≥ 400 on eight functionals, zero retained divergences/invalid/exhaustion, cap rate ≤ 1%, P-vs-N means within 3 combined MCSE):
  sspd-11 — N(a=1) PASS (max R-hat 1.0073, min bulk 853, median depth 6); N(a=.75) FAIL narrowly (1.0124, 573); I PASS (1.0053, 955, cap 0.79%, median depth 8; 2.16M calls); P PASS (1.0044, 795, cap 0.04%, depth 6; 598k calls; 2.8× I's ESS/call; agreement z ≤ 1.25); B FAIL narrowly (1.0103, 445, cap 0.08%, depth 6).
  sspd-10 — every arm FAILS including the reference: N(a=1) R-hat 1.2944, min bulk 11.5, 1,510 divergences, 13.0% depth-12 hits, 648 s; N(a=.75) 1.5318, 7.2, 913 divergences; I/P/B caps 74%/33%/50%, steps 6e-4–1.3e-3, min bulk 4–5, R-hat 2.8–3.9.
  sspd-05 — I PASS (1.0057, 523); P FAIL (1.0250, 273, tail 129); B FAIL (1.0129, 340); N(a=1) FAIL (1.06, 56, tail 19); N(a=.75) FAIL narrowly (1.0134, 524).
  Post-hoc, globals frozen at arm I posterior means: FP (posterior-precision block) vs FI (identity) — sspd-11 depth 4 vs 5, 163k vs 477k calls, 1.3e-1 vs 2.5e-3 bulk ESS/call (≈50×); sspd-10 depth 4 with 0 caps vs depth 8 with 74% caps, 1.0e-1 vs 5.0e-4 ESS/call (≈200×); sspd-05 ≈6×. Post-hoc P2 (accurate path block, globals free) was worse than P everywhere (sspd-11 depth 7, 2× calls, min bulk 549; sspd-10 66% caps).
- Diagnostics: predictions — (1) P passes sspd-11: held for the gates, failed the depth ≤ 5 clause (median 6); (2) I passes, no cap: held; (3) B caps ≫ 10%: **falsified** (0.08%); (4) sspd-10 reported: all arms and the reference fail; (5) sspd-05 all pass: only I (and no N run) passed. Full tables in `STUDIES/real_target_path_metric_v1/README.md` and `artifacts/owalnuts-v1/results-table.md`.
- Artifacts: `STUDIES/real_target_path_metric_v1/{PREREGISTRATION.md,protocol.json,README.md,src/,make_starts.py,numpyro_reference.py,analyze.py,checksums.py,starts/,fixtures/,artifacts/numpyro/,artifacts/owalnuts-v1/,artifacts/owalnuts-v1-posthoc/}`; `artifacts/owalnuts-v1/summary.json` SHA-256 `4a25f7cb0bc99dffb27289d63693d89eb7b1f2982fc561cc90131eb71c235341`; raw functional draws hashed in `CHECKSUMS.sha256`, not committed.
- Conclusion: (a) the first external baseline on the T=1000 fixtures shows sspd-10 is not sampled by NumPyro NUTS at depth 12 either (hundreds to thousands of divergences): Polyscope rows 72/75/77 compared arms on a target no tested Euclidean sampler handles and are uninformative about the sampler; (b) on the non-pathological T=1000 cell, centered adapted-diagonal oWALNUTS passes at depth 8 and the a=0.75 production baseline only narrowly fails — "any diagonal metric caps at T=1000" is false as a general claim; (c) the posterior-precision tridiagonal path block is the correct conditional metric on the real target (≈50–200× ESS/call with globals frozen, zero caps on the funnel cell) and gives 2.8× ESS/call with globals free on sspd-11; (d) with globals free a stiff correct path block hurts (P2 < P) because the innovations are in absolute units in every centeredness, so all parameterizations share the `sigma_x → 0` funnel — the residual problem is global–path scale coupling, not the path block. Not supported: any oWALNUTS-vs-NUTS efficiency claim (work units differ), any claim about the sspd-10 posterior.
- Next decision: (1) product: sample canonical-v2 in a=1 coordinates with the posterior-precision path block refreshed from adapted globals at slow-window boundaries (stage-6 machinery + linear-time `BidiagonalCholesky`); (2) model: version canonical-v3 with scale-non-centered innovations `epsilon_t = (q_t − mu)/sigma_x` before any further funnel-cell work — no Euclidean metric fixes a `sigma_x → 0` funnel; (3) retire sspd-10 as a qualification fixture; keep it as a stress cell with the NumPyro failure as its reference; (4) freeze a fresh-seed confirmation of arm P on sspd-11 with three seeds before any product claim.

### WP10-INVALID-EVALUATION-PARITY-V10 — recoverable failures refine like upstream
- Ordered time: 2026-08-31, after WP9 and WP4b; kernel commit `452befb`
  (`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`), study commit follows.
- Protocol/config: `STUDIES/invalid_evaluation_parity_v1/PREREGISTRATION.md`
  SHA-256 `1f028fe997a5…` (two amendments, both recorded before the affected
  artifact was interpreted); sub-protocols `truncated/protocol.json`
  `7cd68f903fa5…`, `funnel/protocol.json` `1266e971040b…` (frozen copy of WP6's),
  `stock_watson/protocol.json` `09453694c122…` (frozen copy of WP2b's with the
  finite-penalty emulation removed: `nonfinite_policy = recoverable`);
  `src/kernel.rs` `112eb2658099…`, `src/walnutpie.rs` `58d880c2f019…`. Three
  arms: truncated 2-D Gaussian (h=0.9, δ=0.5, 6 levels, depth 6,
  4×500/50,000), Stock–Watson F (paper tuning) and A (Appendix C, paper-mode
  v3 defaults) at 4×500/2,000 on WP2b's series, funnel F at paper tuning
  4×2,000/20,000. Full hashes in `CHECKSUMS.sha256`.
- Seeds: consumed 90031–90034 (truncated), 90011–90014 (SW F), 90021–90024
  (SW A), 90001–90004 (funnel); post-hoc non-evidence replicate 90041–90044.
- Status: confirmed correction (leaf level) plus exploratory sampling
  evidence (sampler level, one seed set per arm).
- Root cause: through `v9` the facade mapped `TargetError::recoverable` to a
  NaN evaluation and the kernel stopped the whole transition
  (`StopReason::InvalidEvaluation`, counted as a divergence). Upstream
  `walnutpie::detail::NoExceptLogpGrad` (`util.hpp`) maps a failed evaluation
  to `logp = -inf`, `grad = 0`; `macro_step`/`within_tolerance` then see an
  infinite endpoint error, refine, and only `build_leaf` returning `nullopt`
  after every halving stops the orbit in that direction. `reversible` treats
  a `-inf` endpoint identically (never within tolerance). The kernel now
  implements exactly this: `-inf` with a finite gradient is a zero-density
  point that integration continues through (with the supplied zero
  gradient), excluded from the Hamiltonian extrema and divergence statistic,
  reported as `zero_density_evaluations`; NaN/`+inf`/nonfinite gradients stay
  malformed and fatal. Detailed balance: the leapfrog map with a
  position-dependent (zero on the region) force is still a reversible
  volume-preserving involution and acceptance depends only on the two
  endpoint Hamiltonians, so the target restricted to its support is invariant;
  forward and reverse selections agree because both use the same endpoint
  statistic.
- Outcome: **leaf oracle passes 4,000/4,000.** New differential oracle
  `oracle/walnutpie/f5bba365_invalid_leaves` (`invalid_leaf_cases.json`
  `7dc3f587d3e0…`), generated by a C++ driver against the unmodified upstream
  headers with a throwing wall target wrapped in `NoExceptLogpGrad` (343
  wall-touching leaves, 50 accepted after refining away): acceptance, calls,
  zero-density call count, adaptation statistic and endpoint agree to 1e-11;
  under `v9` every wall-touching leaf stopped on its first wall call.
  Sampler level: truncated target — all gates pass, every draw inside,
  5,061,666 recoverable = zero-density evaluations, 0 invalid stops, 0
  divergences, x₀ mean 0.8046 (exact 0.7979, z +2.41), var 0.3684 (0.3634,
  z +2.23), x₁ mean z −0.80, var z +1.62; post-hoc replicate on seed 90041
  gave x₀ z −0.12 / −0.11, so the offset is sampling variation.
  Stock–Watson F: 3,404,887 recoverable evaluations (16.5% of 20.57M retained
  calls) with **0 invalid-evaluation stops**, max gated R-hat 1.0011, min
  bulk/tail ESS 2,268/2,453, 1 exhaustion, 13.0% orbits with H range > 2,
  110 bulk ESS per M calls (WP2b emulated: 104); A: 522 recoverable, 0
  stops, max gated R-hat **1.0101 (fails ≤1.01 on log σ²)**, min bulk/tail
  630/1,051, 0/0/0 health, 6.8% > 2, 219 ESS per M calls (WP2b 211).
  Funnel: P(ω<−5) 0.0464 (z −0.17), P(ω<−6) 0.0206 (z −0.38), var ω 8.65,
  0/0/0/7 health, all gates pass.
- Diagnostics: 146 → 154 crate tests (110 lib + 44 facade), strict Clippy,
  `fmt --check`, `-D warnings` rustdoc pass; no locked fingerprint changed
  (no frozen fixture returns a recoverable error); facade tests
  `recoverable_target_failures_are_deterministic_rejections_with_exact_partitions`
  (rewritten for v10 semantics) and
  `zero_density_boundary_keeps_truncated_target_stationary` (new).
- Artifacts: `STUDIES/invalid_evaluation_parity_v1/{README.md,RESULTS.md,
  PREREGISTRATION.md,summarize.py,CHECKSUMS.sha256,artifacts/summary.json
  92080b223ea5…, truncated/artifacts/{T.json a9aea6ea23d0…, T2.json
  9e46678b187c…}, funnel/artifacts/F20.json f68196c70f06…,
  stock_watson/artifacts/{F.json 8f6c03ee4cbd…, A.json b95e7f070714…}}`;
  oracle `oracle/walnutpie/f5bba365_invalid_leaves/{generate_invalid_leaves.cpp,
  invalid_leaf_cases.json,README.md,SHA256SUMS.txt}`; test
  `src/oracle_tests/invalid_leaf.rs`.
- Conclusion: WP2b defect (1) is fixed with reference semantics; stiff
  models whose coarse micro-steps overshoot into a non-representable region
  no longer produce no-op transitions. Claims not supported: cross-seed
  replication of the Stock–Watson arms; arm A meeting the R-hat gate (it
  missed by 0.0001 on one seed under paper-mode v3 defaults, which WP2b did
  not use); any efficiency claim beyond "ESS/call within ±10% of WP2b".
- Next decision: ship `v10`; re-run the WP2b arm A on fresh seeds under v3
  defaults before quoting it; the `StopReason::InvalidEvaluation` variant is
  now unreachable for successful runs and may be removed at the next
  breaking release.

### WP12-SSPD11-CONFIRMATION-V1 — fresh-seed confirmation of arms I and P on sspd-11 (kernel v10) and Stock–Watson arm A robustness
- Ordered time: 2026-08-31, preregistered before sampling (protocol hashes below), sampling ~03:22–03:27 local (UTC−4), after WP10 (`93ed8e9`).
- Protocol/config: `STUDIES/sspd11_confirmation_v1/PREREGISTRATION.md` SHA-256 `cd3beed410510b5d…`; `primary/protocol.json` `2679b4edc6bf582c…` (WP4b's protocol with fixture sspd-11 only, arms I and P only, seeds as a list); `stock_watson/protocol.json` `8b4c5010b72948af…` (WP10's Stock–Watson sub-protocol with three copies of arm A at fresh base seeds); runners copied from WP4b (`primary/src/main.rs`, seed loop added) and WP10 (`stock_watson/src/main.rs`, verbatim). Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at `93ed8e9` (`src/kernel.rs` `112eb2658099…`, `src/walnutpie.rs` `58d880c2f019…`). Primary: fixture sspd-11 (`2fff9766…83baad`), a=1, 4 chains, 500 / 2,000, depth 8, refinement 3, max error 1.0, dual-averaged step at 0.8 with initial step search; I = identity initial diagonal with mass adaptation; P = `StructuredBlockMass([globals diag from arm I of the same seed, BidiagonalCholesky path block at data-informed globals])`, mass adaptation off. Gates exactly WP4b's (R-hat ≤ 1.01, bulk/tail ESS ≥ 400 on eight functionals, zero div/invalid/exhaustion, cap ≤ 1%) plus P-vs-I (same seed) and P-vs-N agreement within 3 combined MCSE, N = WP4b NumPyro a=1 seed 86001 (`sspd-11-N-a1-86001.json` `e8587b3d…63cd6`). Confirmation rule: all three seeds pass every gate. Secondary: WP10 arm A configuration unchanged (Appendix C, paper-mode v3 defaults, natural recoverable errors, 4×500/2,000). Full hashes in `CHECKSUMS.sha256`.
- Seeds: consumed 91001–91003 (primary, both arms) and 91011–91013 (Stock–Watson A1–A3); verified unused beforehand; no reserved seeds.
- Status: confirmed sampling evidence for arm I; negative confirmation (not confirmed) for arm P; exploratory robustness evidence for Stock–Watson arm A.
- Outcome: every preflight started zero callbacks; no wall cap hit; no deviation. Arm I passed 3/3 (max R-hat 1.0066 / 1.0072 / 1.0035, min bulk 931 / 962 / 919, min tail 2,119 / 1,884 / 1,714, 0/0/0 health, cap 0.40% / 0.61% / 0.39%, median depth 8, max |z| vs N 1.83 / 0.89 / 1.46) → **confirmed**. Arm P passed 2/3: seeds 91002 and 91003 pass every gate (max R-hat 1.0070 / 1.0058, min bulk 697 / 740, min tail 962 / 776, cap 0.04% / 0.05%, depth 6); seed 91001 fails only the R-hat gate on `beta` (1.0102 vs 1.01; other seven functionals ≤ 1.0040; bulk 691 / tail 624; 0/0/0 health; cap 0.01%; agreement |z| 1.86 vs I, 1.25 vs N) → **not confirmed** under the conjunctive rule. Efficiency P/I (min bulk ESS per retained call): 2.573, 2.963, 2.683; geometric mean 2.735; wall P 7–9 s vs I 24–28 s. Stock–Watson A1/A2/A3: gated max R-hat 1.0074 / 1.0071 / 1.0101 (`log_sigma2`), min bulk 592 / 463 / 484, min tail 1,287 / 796 / 527, 0/0/0 health, zero caps, δ landing 0.24–0.37, h 0.0060–0.0070 → pass rate 2/3.
- Diagnostics: predictions — P confirmed 3/3 **failed**; I confirmed 3/3 held; P/I ≥ 2 held (2.74); agreement on every seed held (max |z| 1.92); depth (P 6, I 8 with cap ≤ 1%) held. Stock–Watson predictions held (2/3 or 3/3 pass; max R-hat within [1.000, 1.015]; clean health). Tables: `STUDIES/sspd11_confirmation_v1/README.md`, `artifacts/RESULTS.md`.
- Artifacts: `STUDIES/sspd11_confirmation_v1/{PREREGISTRATION.md, README.md, analyze.py, checksums.py, CHECKSUMS.sha256, primary/{protocol.json, src/, fixtures/, starts/, artifacts/primary-v1/*.json, artifacts/primary-v1-log.txt}, stock_watson/{protocol.json, src/, artifacts/{preflight.json, data.json, A1-3.json, A1-3.log}}, artifacts/{summary.json, RESULTS.md}}`; raw functional draws (`primary/artifacts/primary-v1/draws/*.f64`) hashed in `CHECKSUMS.sha256`, not committed.
- Conclusion: supported — on the non-pathological T=1000 canonical-v2 fixture in a=1 coordinates, oWALNUTS with a plain adapted diagonal passes modern gates at depth 8 on three fresh seeds and agrees with NumPyro NUTS (product-facing claim for the centered-coordinate path); the posterior-precision path block is healthy, unbiased (agrees with I and N on every seed) and ≈2.7× more efficient per target call with a stable range. Not supported — a claim that arm P passes the strict 1.01 R-hat gate on every seed at 500 / 2,000 (one single-functional miss of 0.0002), and any Stock–Watson arm A pass claim beyond 2/3 at 4×2,000 (both misses are hairline R-hat excursions with clean health and ESS above the gates, consistent with run length rather than a seed-specific pathology).
- Next decision: freeze a P confirmation at 4×4,000 retained draws (or with the path block refreshed at slow-window boundaries per WP4b) as a new preregistration; do not relax the gate. Arm I may be cited now as confirmed. Stock–Watson arm A: report as 2/3 at this draw count; a 4×4,000 rerun would resolve the run-length question if it matters for the release notes.

### WP15a-AUTODIFF-BRIDGESTAN-ENZYME-V1 — autodiff track: survey, BridgeStan integration, Enzyme feasibility
- Ordered time: 2026-08-31, after WP12/WP13; exact UTC not recorded.
- Protocol/config: engineering evidence, not preregistered. Kernel v10 at `d8617a8`+; GNU Rust 1.88; BridgeStan 2.9.0 (mingw g++ 16.1.0, STAN_THREADS=true); `reverse` 0.2.2 tape; benchmarks in `integrations/bridgestan/src/bin/bench.rs` and `integrations/enzyme/src/bin/bench.rs`.
- Seeds: reused v38-ablation seeds 82001–82003 for the paired Eight Schools re-measurement (paired by design); 84101/84201 for local-level engineering runs. No preregistered namespace consumed.
- Status: feasibility/engineering evidence.
- Outcome: BridgeStan `Target` works end to end. Agreement at 20 random points: Eight Schools |Δlp| ≤ 1.4e-14, |Δgrad| ≤ 2.9e-16; local level gradients ≤ 4.5e-13 (value differs by Stan's normalizing constants only). Per-call gradient: 6.7 µs vs 40 ns hand (Eight Schools, 167×), 8.4 µs vs 201 ns (T=100, 42×), 38 µs vs 2.9 µs (T=1000, 13×). Paired sampling (identical seeds/settings): Eight Schools trajectories bit-identical, ESS/s 12.5k→1.2k (v38 config) and 38.6k→3.4k (paper adaptation); local level ESS/s ratio 4.7×/3.7× (T=100, 1/4 threads) and 2.3×/2.5× (T=1000); STAN_THREADS 4-thread speed-up 2.6–3.3× on one shared instance; 0 recoverable failures in 1.16M calls; Stan domain exceptions map to recoverable/zero-density (tested). Enzyme: nightly `rustc 1.100.0-nightly (2026-08-30)` accepts `-Zautodiff` but the sysroot ships no `libEnzyme-23` on Windows; not usable (probe committed). Tape fallback (`reverse` 0.2.2): gradients agree to 1e-13 but 58–68× hand per call, ESS/s 4.3× (T=100) to 11× (T=1000) worse — off-the-shelf Rust tapes are not competitive.
- Diagnostics: `integrations/bridgestan/artifacts/bridgestan-benchmark.json`, `integrations/enzyme/artifacts/tape-benchmark.json`; tests 4 (bridgestan, incl. concurrency + exception mapping) + 2 (tape parity); strict Clippy/fmt clean on both crates.
- Artifacts: `integrations/AUTODIFF-RESEARCH.md` (survey, measurements, facade proposal), `integrations/bridgestan/`, `integrations/enzyme/`; model shared objects are build artifacts and untracked.
- Conclusion: supported — BridgeStan is the right first autodiff integration; oWALNUTS can sample any Stan model today with Stan-level gradient cost, and the T=1000 state-space case keeps a 2.3–2.5× ESS/s penalty only. Not supported — any claim that Eight Schools ESS/s throughput survives autodiff gradients (the 6.7 µs Stan gradient dominates a 40 ns hand gradient; the public throughput claim must say "hand-written target"); any near-term Rust-native (Enzyme/tape) route.
- Next decision: preregister a same-`.stan`-file three-way (oWALNUTS-BridgeStan vs CmdStan vs nutpie); land the small additive facade items (`?Sized` targets, error-mapping contract, `parameter_names`); re-probe Enzyme when a rustup component ships.

### WP14-NUMPYRO-COMPARISONS-V10-V1 — sspd-05 timing, real-market T=48, and the funnel, measured against NumPyro on kernel v10
- Ordered time: 2026-08-31 (after WP12/WP13; kernel v10 at `d8617a8`).
- Protocol/config: `STUDIES/numpyro_comparisons_v10_v1/{PREREGISTRATION.md,protocol.json}`, frozen before sampling; three parts — (1) exact `matched-timing-v1` replication on v10 plus adapted-diagonal and path-block arms (sspd-05, a=1, 500/4,000, accept .9, depth 8, one thread, frozen shared diagonal `afbc3318…d63ea`); (2) real-market T=48 (`73185a16…714a`, wrapping Phase 0 fixture `cf929ec6…8aa6`) at depth 10, a=0.75 and a=1, vs Phase 0.2 NumPyro settings; (3) 10-D Neal funnel, 2,000 + 4×50,000, oWALNUTS fixed paper tuning and Appendix C v3 vs NumPyro NUTS accept .8/.95 depth 10. ArviZ 1.3 diagnostics from exported draws, one code path per backend; JAX transcription parity-checked against the pinned oracle (4/4).
- Seeds: evidence 92001–92003 consumed once per backend cell; compile probe 92000 non-evidence; verified fresh before freezing.
- Status: exploratory sampling evidence (paired, preregistered, fresh seeds).
- Outcome: part 1 — primary T-F/T-N bulk ESS per sampling second **4.03** (tail 4.12; 2/3 eligible; per-work-unit ratio 1.00, labelled); T-N 3/3, T-F 2/3 (seed 92002 `alpha` R-hat 1.0594 under the nine-functional gate), T-I 1/3 (exhaustion gate), T-P 0/3; P1 held, P2/P3 failed — **the v7 figure 5.4–7.3× is retired; the path block has no advantage at T=100** (per-call ratios 2.26/0.51/0.52). Part 2 — R-B, R-I, R-N all **3/3**; zero depth caps at depth 10 (pre-v9 pilot: 3.625%); ESS/s R-B/R-N 3.82, R-I/R-N 3.17; per work unit 0.48/0.41 (labelled); P4/P5/P6 held — **the last NumPyro-favourable comparison is retracted**. Part 3 — NumPyro under-covers the neck on 6/6 cells (P(ω<−5)=0.0000 in five, 0.0115 in one; exact 0.0478), var ω 5.34–8.80, divergences 365–3,449 per cell, 0/6 gates; oWALNUTS FN-F **3/3 exact** (P(ω<−5) .0461–.0510, 0 divergences), FN-A 2/3 (one ω R-hat 1.0102 miss, tail masses exact); P8/P9/P10 held, P7 failed.
- Diagnostics: full per-cell tables in `artifacts/RESULTS.md` and `artifacts/summary.json`; machine shared with two concurrent agents (wall caveat recorded; ESS/work is the robust figure).
- Artifacts: `STUDIES/numpyro_comparisons_v10_v1/` (protocol, sources, per-cell JSON, RESULTS.md, summary.json); raw draws hashed in `CHECKSUMS.sha256`, not committed.
- Conclusion: supported — ~4× wall advantage on the matched sspd-05 track at per-work-unit parity; real-market T=48 passes 3/3 at depth 10 in both parameterizations, 3.2–3.8× ESS/s; NumPyro NUTS catastrophically under-covers the funnel neck where oWALNUTS v10 is exact. Not supported — the v7 5.4–7.3× magnitude; any small-T path-block advantage; frozen-metric robustness on all nine sspd-05 functionals; FN-A/paper-mode borderline ω R-hat at 4×50k (recurrent, third sighting).
- Next decision: update the public claims table (README/release page) with the corrected 4× figure and the funnel measurement; version a paper-mode R-hat robustness look (longer runs or pooled-δ) before quoting FN-A 3/3 anywhere; no confirmation seeds consumed.

### WP15B-PYTHON-TARGETS-V1 — Python package with callable/JAX/PyTorch/PyMC targets and overhead benchmark
- Ordered time: 2026-08-31, after WP15A survey sections existed; exact UTC not recorded.
- Protocol/config: `integrations/python/BENCH.md` (frozen before execution); kernel v10 at `d8617a8`; extension `owalnuts 0.1.0b2` (PyO3 0.28, GNU 1.88); Python 3.11.16; Eight Schools v38 settings (1,000/1,000, accept .95, depth 8, 8 levels, budgeted entry point) and WP4 local-level settings (500/2,000 or 1,000, accept .8, depth 8, 3 levels, mass adaptation off) with identity and tridiagonal posterior-precision metrics.
- Seeds: 93001–93003 consumed (verified fresh before use); data seed 2026083131+T.
- Status: engineering evidence with bounded exploratory benchmarks; not a public benchmark claim (shared machine; NumPyro/nutpie work counters are leapfrog proxies, labelled).
- Outcome: package built and 10/10 adapter tests pass, including v10 zero-density refine-through from Python (`-inf`/exception → recoverable; truncated-Gaussian moments exact; zero invalid stops). Overhead per fused call: native 0.6–0.8 µs, PyMC 6 µs, numpy 10–13 µs, JAX 26–84 µs, torch 170–290 µs. Geomean min-bulk ESS/s: Eight Schools — owalnuts+pymc 1,439 vs NumPyro warm 897 (native 15,226; 44,749 at 4 threads); T=1000 local level — numpy+precision metric 2,455 vs NumPyro identity 720. owalnuts loses on pure-JAX targets (414 vs 897) and against nutpie on PyMC models (1,298–2,120 vs 17,844–25,043 ESS/s; nutpie is GIL-free numba cfunc on 4 cores; per-gradient efficiency comparable). GIL serialises Python targets: threads=4 is slower than threads=1 for numpy.
- Diagnostics: zero divergences, zero max-depth caps, zero invalid-evaluation stops in every oWALNUTS cell; worst R-hat 1.0061; posterior agreement max |z| 2.44 across backends and references.
- Artifacts: `integrations/python/` (crate, package, tests, BENCH.md, bench/run_bench.py, bench/pymc_compare.py, bench/artifacts/summary.json, bench/artifacts/pymc-compare.json, bench/artifacts-full.log); design and proposals in `integrations/AUTODIFF-RESEARCH.md` §"Python callable targets (WP15b)".
- Conclusion: supported — oWALNUTS from Python beats NumPyro when the gradient is compiled outside JAX and whenever a structured metric applies; not supported — any claim on pure-JAX targets or vs nutpie's GIL-free transport. The nutpie gap is callback transport, not sampler efficiency.
- Next decision: implement a GIL-free raw-pointer target entry in the facade (proposal 2), then rerun the PyMC comparison; propagate target error messages through `Error` (proposal 1).

### WP16-REFRESHED-PATH-BLOCK-V1 — boundary-refreshed structured metrics: facade driver, P confirmation, refresh policy falsified
- Ordered time: 2026-08-31, preregistered before sampling; runs after facade commit `b413c88`.
- Protocol/config: `STUDIES/sspd11_refreshed_block_v1/{PREREGISTRATION.md, protocol.json}` (WP12's protocol extended: arms I/P/R, retained ∈ {2,000, 4,000}, fresh seeds; gates unchanged incl. agreement vs arm I and the WP4b NumPyro a=1 reference `e8587b3d…63cd6`). Facade addition under test: `sample_chains_structured_refresh` (`walnutpie-structured-metric-refresh-v1`, kernel `ALGORITHM_REVISION` v10 unchanged; identity refresh proven bit-identical to the fixed direct driver; 159 tests, strict Clippy/fmt/rustdoc clean). Hashes in `CHECKSUMS.sha256`.
- Seeds: consumed 94001–94003 (sspd-11, all arms, both draw counts) and 94001 (sspd-05 sanity, arms I/R); smoke seed 9999 labelled non-evidence. No reserved seeds.
- Status: confirmed sampling evidence for arm P at 4×500/4,000; confirmed for arm I at both counts; negative (policy falsified) for arm R; engineering evidence for the driver itself.
- Outcome: every preflight zero-callback; no wall caps; 20/20 cells completed. **Arm P confirmed 3/3 at 4×500/4,000** (worst R-hat 1.0030–1.0070, min bulk 1,142, zero div/invalid/exhaustion, caps ≤0.03%, agreement max |z| 2.33; ESS/retained-call 2.2–2.3× arm I) — closing WP12's open confirmation (its 2,000-draw miss was run length, prediction P5 held). **Arm R (per-window refresh) not confirmed**: 2/3 at both counts; seed 94001 cap rate 1.38%/1.26% and worst R-hat 1.0198 at 2,000; ESS/call only 0.25–0.52× P and 0.58–1.11× I (predictions P2–P4 failed; P1 held — 16/16 installs, zero refresh failures).
- Diagnostics: R's failure mechanism is estimation, not machinery — early slow windows sampled at small steps underestimate a slow global's variance; seed 94001 chain 2 installed globals precision entries up to ≈2,000 (windows 1–3), boundary step searches oscillated (0.086 → 0.0069), and a ≈5% depth-8 tail persisted after freeze. Full per-boundary telemetry in the run artifacts.
- Artifacts: `STUDIES/sspd11_refreshed_block_v1/{PREREGISTRATION.md, protocol.json, README.md, src/, analyze.py, checksums.py, CHECKSUMS.sha256, artifacts/{run-2000,run-4000,sanity,smoke}/*.json, artifacts/{summary.json, RESULTS.md}}`; raw draws hashed, not committed.
- Conclusion: supported — the refresh driver is correct and exact (installation seam bit-identity, zero-callback preflight, deterministic parallel), and the one-shot posterior-precision path block is a confirmed 2.2× efficiency win over adapted-diagonal at T=1000 on fresh seeds at 4×500/4,000. Not supported — per-window refresh as a policy; any claim that arm P passes at 4×500/2,000 (2/3 there).
- Next decision: keep the driver opt-in; do not default per-window refresh. Candidate next preregistration: final-boundary-only rebuild from the longest window (self-contained R without arm-I input), or arm P with a calibrated globals diagonal, as the production path.
