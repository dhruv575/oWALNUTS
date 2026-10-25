# Open questions (as of 2026-10-25)

Ordered by expected value. Each names the evidence that opened it. Closed
items keep their number so that study documents that cite "open question n"
still resolve; new items from the WP41–WP55 round start at 11.

1. **The step the GP targets need is per-model, not a statistic.** WP40 and
   its two addenda (2026-09-06, 2026-09-07) showed that the healthy-model
   warmup gap and the GP-target lead share one cause: the acceptance-0.8
   fixed point sits above the step that `gp_pois_regr` and `accel_gp`'s
   slowest coordinate needs, and the crash-driven step cut is what puts the
   shipped sampler under it. Every statistic-side fix (skip, floor, higher
   target, descent bound, NUTS initial phase) moves both GP models to the
   wrong side of that step. Closed as a step-statistic line. The metric on
   the slowest coordinate has now been measured with a dense metric and does
   not separate them either (item 11).
2. **Closed (WP48, WP51): `diamonds` at the depth-10 cap is a metric
   problem.** The diagonal runs at step 0.0036 with 10 % depth caps. The
   fixed dense warmup (`PerTransition` seeding, Stan regularisation,
   symmetrised precision) is 98.7x the diagonal per gradient on fresh seeds,
   at step 0.278, zero caps and condition number 2.7e5 -> 17.6
   (`STUDIES/dense_metric_confirmation_v1`; 65.7x post hoc in
   `STUDIES/dense_metric_posteriordb_v1`). Those settings are now the
   `Metric::dense()` warmup defaults. Dense is still opt-in: WP48 found no
   `auto` rule from dimension and `max|corr|` that selects every winner and
   no loser.
3. **Closed as a default-change line (WP42): `delta = 0.5` is not the
   default.** At eight levels it is 1.385x funnel efficiency, but 0.936x over
   posteriordb (0.861x on the 14 healthy-ish models, seven models below
   0.85x) with 38 vs 41 gates; `delta = 0.75` is 0.995x on ordinary models
   and only 1.142x on the funnel (`STUDIES/delta_half_default_v1`).
   `delta = 0.5` stays the documented opt-in for funnel-like targets. The
   per-chain funnel step collapse that opened this item (WP28, WP32) did not
   reproduce at `delta = 1` on WP42's seeds (smallest final `h` 0.032, omega
   R-hat 1.003). WP49 then saw the default fail the funnel |z| check on 1 of
   12 seeds (z -4.21, `STUDIES/adaptive_delta_v1`). How often the default
   collapses or misses on the funnel needs more seeds before anything is
   designed around it.
4. **Closed as a warmup-statistic line (WP49): target-adaptive `delta`.** A
   rule driven by the warmup-window level-0 leaf-error tail does not qualify:
   the inverse-tail rule is 1.016x and the refined-fraction controller
   0.885x (`STUDIES/adaptive_delta_v1`). The tail that hurts (`accel_gp`) is
   invisible in warmup (q0.99 1.25 in the window vs 3.9 on the retained
   draws). `with_adaptive_delta` stays a research option. Fixed `delta = 2`
   is item 14.
5. **Global to path scale coupling on state-space and hierarchical targets**
   (WP4b, WP17, WP21, WP46, WP55): the arrowhead line is the best per-call
   mechanism in pilots and needs a six-global generalisation, Python
   exposure and a preregistered confirmation. sspd-10 remains unsolved by
   every Euclidean configuration. The same shape appears outside state
   space: on radon and grsm the slowest coordinate on 6/6 cells was a global
   coupled to hundreds of locals (`STUDIES/posteriordb_breadth_v1`), and
   centred radon was wrong on 3/3 seeds (max |z| up to 3.33, `beta[1]` ESS
   232–389) with almost no refinement (`STUDIES/silent_funnel_diagnostic_v1`).
6. **Start rules (best-of-k)**: `hmm_drive_0`'s second-mode draw and
   `lotka_volterra`'s `rk45`-boundary starts decided gates by lottery (WP25,
   WP29, WP31). `Init::best_of(16)` (WP43) passed a preregistered
   default-flip confirmation (WP52, `STUDIES/init_rule_confirmation_v1`):
   1.254x ESS per gradient and 42 vs 42 gates. It is the default
   (`Init::default()`, `run_from_random_starts`). The gain is all `arma11` /
   `lotka_volterra` freezes; the other 14 models are 0.862x. Still open:
   - **Healthy-model cost.** The 0.862x is driven by one `earnings` warmup
     step collapse and centered eight schools; the other 12 models are 1.01x.
     Is it real or seed noise?
   - **Hidden modes.** Best-of-16 produced one hidden-mode `hmm_drive_0` cell:
     46 second-mode retained draws at rank R-hat 1.0087, which only
     `chain_warnings` caught. Pooled over WP43 and WP52 that is 1 for best-of-16
     against uniform's 0 (uniform had 1 *visible* failure instead).
   - **Two-mode bias.** On a symmetric 0.7/0.3 two-Gaussian target, best-of-16
     raises single-basin four-chain starts from 12.8 % to 22.7 % of seeds. No
     mode was hidden on the 3 sampled seeds, partly because warmup crosses an
     8-SD gap. The risk is lowered by warmup, not removed.

   The next step is a hidden-mode-gated study on `hmm_drive_0` with many seeds
   (it is cheap), comparing uniform, best-of-16 and best-of-4. An init-time
   ODE check was never tried.
7. **Chain-disagreement warning sensitivity** (WP36, WP44, WP52, WP55): the
   warning ships (`ChainWarning`, end-of-warmup and retained-draw telemetry;
   `STUDIES/chain_disagreement_warning_v1`). On the 60-cell screen the
   step and density checks had zero false positives and the R-hat check
   fired falsely only at R-hat 1.013 / 1.014, but sensitivity rests on one
   wrong-chain cell. WP52 adds that `chain_warnings` flagged every lost cell
   in both start arms and named the hidden-mode `hmm_drive_0` chain that
   R-hat missed. It is not a gate-failure detector: 3/10 on WP44's gate
   failures and 2/12 on WP55's silent-funnel cells. A targeted bad-start
   study (forced starts on `lotka_volterra` / `arma11`, the WP33 trap) is
   still needed, and emitting the warmup-end check while the run is going
   (the frozen-chain case is the one that times out) is untried. A narrowly
   scoped step-only rescue remains unmeasured.
8. **Windows native root cause** (WP35A, `bridgestan_lifetime_v1`,
   `bridgestan_owned_worker_v1`, WP50–WP50E): the heap corruption
   reproduced only with the full WinLibs mingw runtime (3/60, WP50B), and
   statically linking that runtime removed it in the stress gate (static
   0/360 vs dynamic 2/120, WP50C), where dropping the owned-worker
   serialisation was worth 3.2x (sblrc) / 4.0x (arK) contended sampling
   wall. The confirmatory gate (WP50D) was **not supported**: static DLLs
   1/1000, a sampler-reported nonfinite-position error and not a crash,
   against 4/300 crashes for dynamic DLLs. WP50E replayed that seed 6/6
   under both dispatches; under `RejectLeaf` it completes. The static-runtime
   dispatch is opt-in (`ReplicatedOptions::concurrent_if_static_runtime()`);
   the owned worker stays the default. Open: whether the coordinator accepts
   the WP50E dispatch-independent reading (static native-fault count 0/1000),
   a larger static gate before any default change, and MSVC.
9. **Reverse-coarsening cost on `accel_gp`** (WP34, WP39, WP39B, WP48): 54 %
   reverse-coarser stops and 0.47x CmdStan; not a truncation artefact, and
   not linear correlation either (a dense metric at condition number 18 is
   1.34x and still 0/3, WP48 post hoc). Its difficulty is unexplained.
10. **Paper-mode borderline omega R-hat at 4 x 50,000** (WP14, WP12): third
    sighting; a longer run or pooled delta would settle whether it is run
    length.
11. **GP-hyperparameter posteriors under the dense metric** (WP48, WP51): the
    fixed dense warmup does not rescue `gp_pois_regr` or `accel_gp`.
    `gp_pois_regr` goes 3/3 -> 0/3 gates: 1.73x per gradient, but at a
    quarter of the diagonal's gradients its min bulk ESS is 341–433, tail
    ESS 133–297 and R-hat on `rho` 1.010–1.015 (condition number 3–4).
    `accel_gp` is 0.38x, 0/3 against the diagonal's 1/3 (R-hat 1.05–1.06).
    Whether longer runs, or a metric aimed at the length-scale coordinate,
    fix either is unmeasured; see also items 1 and 9.
12. **`lotka_volterra` stalls** (WP54 side finding, WP44, WP48, WP51): with
    the shipped sampler settings and `Init::uniform()` starts it stalls past
    900 s on 4 of 13 seeds and finishes with R-hat 1.04–1.59 on 3 more; the
    four timeouts happen under both nonfinite policies
    (`STUDIES/nonfinite_policy_requalification_v1`). Earlier studies lost
    single cells to the same timeout (WP44 seed 97464, WP48 seed 148101,
    WP51 seed 151302). Best-of-16 starts passed this model on every seed in
    WP43 (5/5) and WP52 (3/3); whether the new default start rule avoids the
    stall in general has not been studied.
13. **The per-gradient gap to nutpie on PyMC models** (WP47): nutpie gets
    1.6–2.4x more ESS per gradient than oWALNUTS on all three models of
    `STUDIES/python_callpath_v1` (the preregistered band was 0.6–1.6x; the
    observed 1.63–2.35x fell outside it). `from_pymc(gil_free=True)` reaches
    0.51–1.0x nutpie's ESS/s at one core. A kernel study of that gap was
    recommended and has not been run.
14. **Fixed `delta = 2`** (WP34, WP37A, WP49; pending WP53): WP37A did not
    qualify it (funnel gates F3 and F4 failed). As WP49's control it is
    1.141x over posteriordb with 43 gates (1.067x without two seed
    pathologies, matching WP34's 1.070x), but it triples funnel divergences
    (34 against the default's 11 over 12 seeds). WP53 is the pending
    decision.
15. **The silent funnel** (WP46, WP55): oWALNUTS can sample centred
    hierarchical funnels with zero divergences, because refinement absorbs
    the energy error. In WP55, 11 of 12 wrong positive cells had zero
    retained divergences, and all 12 failed the R-hat / ESS gates. The
    refined-leaf rate is not the warning (sensitivity 0.667, specificity
    0.718 against 0.75 and 0.929 required); nothing ships
    (`STUDIES/silent_funnel_diagnostic_v1`). A future instrument needs
    targeted neck-start positives (WP55's `seeds_centered` did not reproduce
    WP46's neck-stuck chain) and should test refined-leaf depth (post hoc
    AUC 0.84, not evidence) or per-chain scale-parameter ESS.
16. **`RejectLeaf` in practice** (WP38, WP54): `RejectLeaf` is the
    `sampler::Tuning` default (bit-identical on 73/73 completed-abort cells,
    75 vs 73 runs completed). The benefit rests on one non-fresh seed: no
    fresh cell hit the event. The rescue records no divergence, so it is now
    reported as a per-chain `chain_warnings` line (WP59). How often fresh
    targets hit the event, and whether a rescued run is ever wrong, is
    unmeasured.
17. **An absolute diagonal-metric floor sized to the smallest well-measured
    scale** (WP41): Stan's absolute `9.9e-6` installs 9.8–11.9x the
    posterior variance on `sblrc`'s coefficients, and removing it is 2.06x on
    `sblrc`, but the scale-free median anchor loses 0.61x on `kidiq`
    (`STUDIES/metric_regularisation_scalefree_v1`). A floor that keeps the
    first without the second is new and needs its own preregistration.
18. **Idle-machine thread scaling** (WP45): on the contended machine the
    driver is thread-count invariant and shows no internal contention. The
    one shared written line on the default path, the budget CAS, saturates
    at ~18 M CAS/s in a micro-bench; fix F1 was not merged
    (`STUDIES/thread_scaling_v1`). `RUN-QUIET.md` there is the idle-box rerun
    that would show whether it matters for sub-µs gradients.

Closed lines, so they are not reopened: reverse-coarsening as truncation
(WP34 to WP39B); coarsest-first reverse order (WP37B); Appendix C as the
default (WP22, WP23); full scale non-centering (WP17); chain rescue as a
default (WP36); warmup-schedule and step-statistic levers for the
healthy-model gap (WP40 and addenda); scale-free diagonal regularisation as
the default (WP41); a lower fixed `delta` as the default (WP42);
`Init::median_of` (WP43); an automatic dense switch from dimension and
`max|corr|` (WP48); a warmup-window leaf-error rule for `delta` (WP49); the
refined-leaf rate as a silent-funnel warning (WP55).
