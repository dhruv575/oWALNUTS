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
