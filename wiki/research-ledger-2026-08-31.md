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
