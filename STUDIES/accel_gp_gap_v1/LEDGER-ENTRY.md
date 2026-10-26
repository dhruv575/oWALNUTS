### WP70-ACCEL-GP-GAP-V1: no candidate closes the accel_gp gap (baseline 0.567x CmdStan per gradient); no hypothesis met its frozen criterion; post hoc, the adapted step sets the reverse-coarser stop share (14 % to 80 %) and through it the mixing, and target_accept 0.95 passes accel_gp 3/3 at 2.5x the gradients

- **Ordered time:** 2026-10-26 on `wt/accel-gp-gap`, on the shared AWS box, lane 2 (cores 4-7), with three other lanes active.
  - Preregistered at `9d8a015d` (library `d39efaad`), after a disclosed smoke run on the non-study `kidiq-kidscore_momiq`. That run moved D1's integration time from merged orbit states to leaves built x h; no threshold changed.
  - One run of 75 cells, 02:05–02:12 UTC, strictly sequential; no error, timeout or rerun.
- **Protocol/config:** `STUDIES/accel_gp_gap_v1/{PREREGISTRATION.md,protocol.json}`.
  - Samplers: oWALNUTS defaults via BridgeStan 2.9.0 (`ReplicatedStanTarget`, WP65-qualified) and CmdStan 2.39.0 defaults.
  - Seeds 700711–700713, 4 x 1,000/1,000, v7 gates and metric code.
  - Controls: eight_schools_noncentered, kidiq_momhsiq, arK, gp_pois_regr and garch11.
  - Hypotheses: H1 reverse-coarser truncation (RC share >= 0.40 and median integration-time ratio <= 0.60); H2 depth cap (max-depth share >= 0.05); H3 metric mismatch vs posteriordb reference variances (ratio >= 1.5).
  - Candidates (all run): `target_accept` 0.95, `max_depth` 12, warmup 2,000.
  - Rule: R1 accel_gp ESS/gradient vs CmdStan >= 0.75; R2 accel gates not lower and no passing |z| > 4; R3a control passes not lower; R3b control geomean >= 0.95.
- **Outcome:**
  - **Baseline:** 0.567x CmdStan (P0 [0.25, 0.55] failed narrowly); gates oWALNUTS 0/3, CmdStan 0/3 (37–174 divergences).
  - **D1:** RC share 0.55 but integration ratio 0.87, so H1 is not supported (predicted supported).
  - **D2:** 0.0001, not supported (predicted).
  - **D3:** 1.43, not supported (predicted).
  - **Candidates:** none qualifies.

    | candidate | R1 | accel gates | control geomean | control passes |
    |---|---:|---:|---:|---:|
    | `target095` | 0.616 | **3/3** | 0.804 | 15/15 |
    | `depth12` | 0.084 | 0/3 | 0.981 | 14/15 |
    | `warmup2000` | 0.192 | 0/3 | 0.740 | 15/15 |
- **Diagnostics (post hoc, descriptive):**
  - RC-stopped orbits integrate 0.8–1.2 time units, against 3.8–4.0 for U-turn orbits. The frozen median statistic missed this bimodality.
  - Across the four oWALNUTS arms, the median step (0.0050 / 0.0076 / 0.0092 / 0.0097) orders the RC share (0.14 / 0.55 / 0.75 / 0.78) and min bulk ESS (about 1,240 / 460 / 190 / 55).
  - Longer warmup and a deeper cap both settle at a 20–30 % larger step.
  - `target095` gives ESS x2.7 and 3/3 gates at 2.5x gradients, so 1.09x the default per gradient.
- **Artifacts:** `STUDIES/accel_gp_gap_v1/`:
  - `{README.md,LEDGER-ENTRY.md,PREREGISTRATION.md,protocol.json,run_gap.py,build_models.py,checksums.py,Cargo.toml,Cargo.lock,src/main.rs}`;
  - `artifacts/{cells/,diagnosis.{json,md},summary.json,results-table.md,build-manifest.json,measured_on.json}`;
  - `CHECKSUMS.sha256`, including the uncommitted draws and per-transition arrays.
- **Conclusion:**
  - Not supported, as preregistered: H1, H2, H3, and all three candidates.
  - Supported descriptively: accel_gp's gap is a step/truncation trade-off. At the 0.8 fixed point half the orbits are cut by failed reverse checks. A smaller step removes the cut but not the per-gradient gap; longer warmup and a deeper cap make it worse.
- **Next decision (coordinator):**
  - No default change and no research flag.
  - Document `target_accept = 0.95` as the gate-passing setting for accel_gp-type GPs (3/3, 2.5x cost).
  - Any follow-up should preregister the RC-stop share and a step-dose design, and target the reverse-check / step-statistic interaction (open question 1).
