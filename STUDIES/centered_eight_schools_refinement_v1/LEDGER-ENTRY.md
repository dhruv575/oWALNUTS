### WP82-CENTERED-EIGHT-SCHOOLS-REFINEMENT-V1: the centred eight schools pays the funnel neck in refinement at a bulk-set step; costda, stanacc and levels2 each fail the frozen rule

- **Ordered time:** 2026-10-26 on `wt/centered-refine`.
  - Library commit `70343cdf` adds the default-off `DualAveragingAcceptance::CostWeightedCoarseEndpoint`.
  - Preregistered at `7966207f`. Amendment 1 (`62a0caad`) sets the source revision; the first two
    launches ran no cell.
  - Lane 2 of the shared box; no reruns.
- **Protocol:** `STUDIES/centered_eight_schools_refinement_v1/{PREREGISTRATION.md,protocol.json,AMENDMENTS.md}`.
  - Telemetry on centred and non-centred eight schools x 6 seeds (821821–6) vs CmdStan 2.39.0.
  - Candidates: `costda` (cost-weighted step statistic), `stanacc` (Stan's `accept_stat__`) and
    `levels2` (2 refinement levels).
  - Rule:
    - K1: centred ratio vs CmdStan >= 0.60 (WP72 form);
    - K2: gates and divergences held;
    - K3: funnel 10 seeds x 4 x 2,000/20,000;
    - K4: 5 models x 3 seeds, passes not lower and geomean >= 0.95;
    - K5: tests.
- **Telemetry:**
  - oWALNUTS step 1.18x CmdStan's.
  - 25 % of transitions are refined, and they take 72 % of sampling gradients.
  - 71 % of refined transitions start in log-tau Q1, where a transition costs 184 gradients against
    CmdStan's 13 leapfrogs (acceptance 0.48, 11 % divergent).
  - P1–P3 held; P4 failed (twin refined fraction 0.054).
  - Default vs CmdStan on these seeds: 0.269 per total gradient.
- **Rule:**
  - **`costda`:** K1 0.577 and K4 0.909 fail.
  - **`stanacc`:** K1 0.929 passes; K3 (P5 0.0524 ± 0.0039) and K4 (0.618, hmm_example 0.16, one
    lost pass) fail.
  - **`levels2`:** K1 0.799 passes; K2 (256 vs 12 divergences) and K3 (P5 0.0075) fail.
  - **All three:** K5 fails, because the directional `cost_weighted_acceptance` test failed on
    Linux (2 of 4 chains); the integrity tests passed.
- **Decision:** no candidate qualifies; defaults unchanged.
