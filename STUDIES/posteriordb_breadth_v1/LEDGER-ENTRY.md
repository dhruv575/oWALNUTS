### WP46-POSTERIORDB-BREADTH-V1 — the shipped defaults on 19 never-used posteriordb posteriors: 40/42 on the reference-draw tier, 8/15 on the gates-only families, two new failure classes (box-constraint corner traps, silent funnel)
- Ordered time: 2026-10-24 on `wt/posteriordb-breadth`. The preregistration, frozen selection rule (`select_posteriors.py`), harness and predictions were committed at `2a5f8187` before the first evidence cell. 57 cells ran 18:09–21:41 local in strict model/seed order: reference tier first, then the gates-only tier. Analysis followed immediately.
- Protocol/config: `STUDIES/posteriordb_breadth_v1/{PREREGISTRATION.md,protocol.json}`. oWALNUTS only, `Sampler` defaults with nothing overridden: post-WP36, so **no chain rescue**, unlike v6. 4 x 1,000/1,000, four threads, Windows owned BridgeStan worker (`OwnedSerialised`, one effective replica), posteriordb `28f8d3d`, house gates (rank R-hat <= 1.01, bulk/tail ESS >= 400 on every gate parameter, zero retained divergences), v6 z against reference draws with a flag above 4, and a frozen mechanical failure classifier over per-cell telemetry: step spread, warmup step trace, depth-cap fraction, refined-leaf fraction, invalid evaluations, installed/empirical metric variance, cross-chain disagreement and energy. Availability finding before selection: only 47 of 147 posteriors have reference draws, 30 remain after removing the 17, 22 of those are ARM regressions, and none covers GLMMs, hierarchical logistic models, survival, ordinal models, hundreds of parameters or new ARMA/GARCH variants. Reference tier: 14 posteriors by the condition-number rule. Gates-only tier: 5 posteriors, one per absent family, chosen before sampling.
- Seeds: 461461, 461462, 461463, verified unused by `git grep -w` over every tracked file and the sibling study protocols.
- Status: all 57 cells completed; 0 process errors or timeouts. All 19 models compiled. Walls are contended and serialised and are not evidence: radon 707–1,150 s, sat 787–1,519 s per cell.
- Outcome:
  - **Reference tier 40/42 (95 %)**: above v6's 45/51 on the tuned set and above the registered 32 (28–36). P1 failed optimistically because the reference-draw set is mostly easy. P4 held (no passing |z| > 4; max 2.79). P5 held. Retained divergences were 0 in all 57 cells.
  - **Gates-only tier 8/15**: P3 held (7–13).
  - P2 failed: kilpisjarvi, kidscore_interaction and seeds_centered failed as predicted; hmm_drive_1 and logearn_logheight_male passed 3/3; GLMM_Poisson and grsm failed unpredicted.
  - P6 failed: only 2 failing reference cells.
  - Failures:
    - GLMM_Poisson 0/3, **box-constraint corner traps**. 4 of 12 chains were held in the region created by `uniform` priors on boxes; three were wall-pinned (alpha -20, beta1/beta2 10, sigma near 5), one chain was fully refinement-exhausted, and they sat 270–27,700 nats above the healthy chains. R-hat 1.6–2.8.
    - seeds_centered 0/3, **silent funnel**. A `sigma` neck-sticking chain (per-chain ESS 6–7, R-hat 1.02–1.07) with zero warmup and retained divergences, because refinement absorbs the energy error.
    - kilpisjarvi 2/3. 12–20 % depth caps on a corr-1.0000 ridge; seed 461462 had one chain at a 5–10x smaller warmup step that covered 1.3 % of the ridge variance (R-hat 1.45).
    - kidscore_interaction 2/3. R-hat 1.0117, correlation-slowed.
    - grsm 2/3. `lambda_adj` per-chain ESS 14.
  - Borderlines:
    - radon and grsm: the slowest coordinate on 6/6 cells was a global coupled to hundreds of locals.
    - sblri: the Stan regularisation floor makes installed variance 12x true on variance-1e-6 coordinates.
    - sat: max-of-672 R-hat near 1.008, a gate artefact.
  - Post-hoc descriptive: per-chain step collapse outside the funnel (low_dim_gauss_mix 0.014x the median step, 5.2x warmup cost) with the gates intact.
- Diagnostics: `artifacts/results-table.md` (all cells and labels), `artifacts/summary.json`, `artifacts/cells/*.json`, `artifacts/selection.json`, `artifacts/compile-status.json`, `artifacts/posthoc-descriptive.{md,json}` (post-hoc), `artifacts/{run-log,analyze-log,prepare-log}.txt`, `artifacts/measured_on.json`. Raw draws ignored.
- Artifacts: `STUDIES/posteriordb_breadth_v1/{PREREGISTRATION.md,protocol.json,README.md,LEDGER-ENTRY.md,Cargo.toml,Cargo.lock,src/main.rs,run_breadth.py,select_posteriors.py,posthoc_descriptive.py,checksums.py,CHECKSUMS.sha256,artifacts/}`.
- Conclusion:
  - Supported: the shipped defaults generalise to unseen reference-draw posteriordb posteriors with no bias flag. The prior worry that 17-model tuning overfit is not borne out on what posteriordb can test with references.
  - Not supported: robustness on the absent families. Two new failure classes are both detectable without a sampler change: a cross-chain energy gap above 200 nats for every corner trap, and a refined-leaf or "would-diverge" signal for the silent funnel.
  - No default change, as preregistered.
- Next decision:
  1. Prioritise, in order: corner traps (open questions 6/7, `ChainDisagreement` as an energy warning); a silent-funnel diagnostic (open question 3); global-to-local coupling beyond state space (open question 5); ridge depth cap (open question 2); late typical-set arrival contaminating the last metric window (open question 3, cost only).
  2. v7 breadth candidates by the frozen rule: GLMM_Poisson, seeds_centered, kilpisjarvi, science_irt grsm, radon_all hierarchical_intercept_centered (alternate kidscore_interaction). Three need their own reference runs.
  3. Measure whether CmdStan shares the GLMM corner traps from identical uniform(-2, 2) starts before attributing them to oWALNUTS.
