### WP66-FUNNEL-TAIL-DEFICIT-V1 — the WP53 funnel tail deficit does not replicate at the preregistered threshold (fresh default 0.0465 ± 0.0017 vs exact 0.0478; 80,000-draw sanity arm 0.0488 ± 0.0007); none of three mechanisms (step adaptation, refinement ceiling, U-turn rule) is supported; `endpoint` passes D1–D4 only on a wider s.e. and is not a default candidate; side finding: `levels10` removes funnel divergences (59 -> 1) at 1.00x cost
- Ordered time: 2026-10-25/26 on `wt/funnel-tail` at `main` `a49df800`. `PREREGISTRATION.md` + `protocol.json` were frozen and committed (`1979faca`), with a pipeline-check disclosure added in `06442454`, both before the first evidence cell. Non-evidence work was disclosed: a post-hoc look at WP53 cells, and pipeline checks on seed 990661. Blocks A (120 cells), S (10) and C (80) ran strictly sequentially on the shared AWS box `owalnuts-bench`, lane 3, pinned `taskset -c 8-11` with three other lanes active (walls pinned, co-tenanted). All cells exited 0; no reruns.
- Protocol/config:
  - Target and run: Neal's 10-D funnel, WP53's harness copied and parametrised, house starts, 4 chains / 4 threads, `Metric::diagonal()`, admit-worst-case.
  - Arms: `default`; `accept0.9` (`Adaptation::DualAveraging { target_accept: 0.9 }`, H1); `levels10` (`max_refinement_levels(10)`, H2); `endpoint` (`kernel_options(KernelOptions::default())`, H3).
  - Blocks: A is 4 x 2,000/20,000 x 30 seeds; S is default 4 x 2,000/80,000 x 10 seeds; C is Eight Schools noncentred + 100-D Gaussian, 4 x 1,000/1,000 x 10 seeds.
  - Per-transition diagnostics are aggregated by starting omega class (bulk / neck [-7,-5) / deep < -7).
  - Removal rule (all four): D1 |pooled − exact| <= between-seed s.e.; D2 mean z in [−0.2, 0.2]; D3 exceedances <= 4 and divergence rate < 1e-3; D4 no library change and `kernel_fingerprint` passes.
  - Recommendation rule (both): E1 side-check paired ESS/gradient >= 0.95x on both targets; E2 no ledgered posteriordb loss >= 4 %.
  - Hypothesis support: paired t >= 2 plus a frozen signature.
- Seeds: A 668101–668130, S 668201–668210, C 668301–668310 (git grep over the tracked files of `a49df800` and over sibling-worktree protocols: unused); pipeline 990661.
- Status: preregistered mechanism and default-candidate study; all 210 cells present.
- Outcome:
  - **Replication, default arm:** 0.0465 ± 0.0017 (−2.7 %, t −0.76), so the deficit does **not** replicate (rule: more than 1 s.e.). Mean z −0.39, 3/30 |z| > 2 (all low). The upper tail P(>5) is 0.0489 ± 0.0008 (+2.4 %).
  - **`accept0.9`:** 0.0471 ± 0.0017, paired +0.0006 ± 0.0024, h 0.67x, D2 fails (−0.30). H1: signature present (neck energy-acceptance proxy 0.41 vs bulk 0.73), not causal.
  - **`levels10`:** 0.0453 ± 0.0015, paired −0.0012 ± 0.0007; D1 and D2 fail. H2 NOT SUPPORTED: deep top-level+exhaustion is 12.8 %, but the relative deficit does not grow with depth (−0.4 % at c = −8 vs −2.7 % at −5). Exhaustions 756 -> 10 and divergences 59 -> 1; side targets 1.00x, draw-identical.
  - **`endpoint`:** 0.0496 ± 0.0024, mean z −0.13, so D1–D4 hold and it "removes the deficit". But it is paired +0.0031 ± 0.0032 (t 0.97), its omega tail ESS is 299 vs 727, it runs at 0.79x the default's min ESS/gradient, E1 fails (Gaussian 0.900x) and E2 fails (WP31/32), so it is not a default candidate. H3: the depth signature holds in the opposite direction (endpoint neck depth 1.49 vs `MomentumSum` 2.55), not causal.
  - **Sanity arm S:** 0.0488 ± 0.0007 (+2.1 %), first 20k 0.0477, reading INCONCLUSIVE (above exact).
  - **Predictions:** P1, P4, P5, P7 held; P2, P3, P6 failed.
  - **Post hoc (not preregistered):** 70 default seeds at 20,000 draws (WP53 + WP66 + S prefixes) pool to 0.0464 ± 0.0010 (−3.0 %, t −1.4). Four of the five lowest seeds contain a slow chain (h <= 0.023, <= 38 neck entries).
- Diagnostics: `artifacts/results-table.md` (rule tables, tail profiles c = ±1..±10, class tables, level histograms, per-chain and per-seed values), `artifacts/summary.json`, `artifacts/cells/`, `artifacts/environment.json` (fingerprint 3/3 passed, library diff empty), `artifacts/fingerprint.log`, `artifacts/run-log.txt`, `artifacts/run_all.sh`.
- Artifacts: `STUDIES/funnel_tail_deficit_v1/{PREREGISTRATION.md, protocol.json, README.md, LEDGER-ENTRY.md, Cargo.toml, Cargo.lock, src/lib.rs, src/bin/funnel.rs, src/bin/side.rs, run_study.py, checksums.py, CHECKSUMS.sha256, artifacts/}`; no library change.
- Conclusion:
  - Supported: on fresh seeds and at 4x the draws the default's funnel tail mass is consistent with exact within about 3 %; the WP53 "4–5 % deficit" was partly a low draw. The residual low-z pattern is per-seed: occasional slow chains silently under-visit the neck, and the MCSE z correlates with the estimate.
  - Not supported: step adaptation, the refinement ceiling and the `MomentumSum` rule as causes; any single setting as a fix.
- Next decision:
  1. Close open-question 3's "tail-deficit" sub-item: no default change is needed for tail mass.
  2. If the residual is to be settled, run a default-only confirmation at 30 seeds x 4 x 2,000/80,000 (expected s.e. about 0.0004, 0.8 % relative, from S's 10-seed spread; each cell about 6 s pinned).
  3. Preregister `max_refinement_levels(10)` separately as a funnel-divergence fix, with posteriordb gates. It is draw-identical wherever level 7 is not exhausted.
