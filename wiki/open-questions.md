# Open questions (as of 2026-10-25)

Ordered by expected value. Each names the evidence that opened it. Closed
items keep their number so that study documents that cite "open question n"
still resolve; new items from the WP41–WP61 rounds start at 11.

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
   designed around it. posteriordb v7 had the funnel unbiased on all three
   seeds (z +1.69, -0.59, +0.84), with per-chain steps from 0.009 to 0.2.
   WP53 (`STUDIES/funnel_defaults_30seed_v1`, 30 fresh seeds) answered the
   frequency: the default misses |z| <= 2 on 4/30 seeds, all low, with mean
   z -0.42 and a pooled tail mass of 0.0458 against 0.0478; the misses are
   silent (no divergences, no `chain_warnings`, R-hat <= 1.008). The gate on
   three seeds is a lottery (about 35 % failure for the unchanged default);
   future funnel checks should pool tail mass over 12 or more seeds and
   count divergences. The 4-5 % tail deficit at the defaults is a new open
   item (why both `delta = 1` and `delta = 2` under-sample `omega < -5`).
   **Closed (WP66, WP68):** at 30 fresh seeds the deficit did not replicate
   (0.0465 ± 0.0017), none of three mechanisms (step adaptation, refinement
   ceiling, U-turn rule) is supported, and the default at 4 x 2,000/80,000
   over 30 seeds gives 0.0478 ± 0.0010, exactly the true value
   (`STUDIES/funnel_tail_deficit_v1`, `STUDIES/refinement_levels10_v1`).
   What remains on the funnel is divergences, not bias: ten refinement levels
   remove all of them (268 -> 0) with the tail unchanged, but failed the
   posteriordb rule (42 vs 44 passes, 0.824x) and stay an opt-in.
4. **Closed as a warmup-statistic line (WP49): target-adaptive `delta`.** A
   rule driven by the warmup-window level-0 leaf-error tail does not qualify:
   the inverse-tail rule is 1.016x and the refined-fraction controller
   0.885x (`STUDIES/adaptive_delta_v1`). The tail that hurts (`accel_gp`) is
   invisible in warmup (q0.99 1.25 in the window vs 3.9 on the retained
   draws). The study's `with_adaptive_delta` option is not in the library
   on `main`. Fixed `delta = 2` is item 14.
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
     A paired rerun on six suspect models (WP60,
     `STUDIES/start_rule_paired_v1`) puts best-of-16 at 1.061x uniform per
     gradient, so it is not the cause of the v6 -> v7 drop (item 20). It
     does cost gates there: 15/30 against 18/30.
   - **Hidden modes.** Best-of-16 produced one hidden-mode `hmm_drive_0` cell:
     46 second-mode retained draws at rank R-hat 1.0087, which only
     `chain_warnings` caught. Pooled over WP43 and WP52 that is 1 for best-of-16
     against uniform's 0 (uniform had 1 *visible* failure instead). In WP60,
     best-of-16 held one `hmm_drive_0` chain about 62 nats down in a second
     mode on 2 of 5 fresh seeds (per-chain ESS 7–14), and `chain_warnings`
     named it in both cells.
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
   scoped step-only rescue remains unmeasured. WP69
   (`STUDIES/trapped_chain_restart_confirmation_v1`) measured the step-only
   rescue: not proposed (false positives on recovering chains at step ratios
   0.024–0.031, a real trap missed at 0.111). It also found the warning
   silent on three 2-vs-2 splits of a two-mode target that R-hat > 1.01
   caught (6 of 12 split runs reported). WP74
   (`STUDIES/chain_disagreement_splits_v1`) added the pairwise-agreement
   cluster check (`ChainWarning::RHatCluster`, now shipped): 5/5 fresh split
   cells reported against 1/5 for the older checks, no finding on 43
   gate-passing posteriordb cells, no lost warning on 26 replays. Still
   open:
   - **Splits with no agreeing pair.** It misses WP69's 2-vs-2 cell 6903202:
     two chains crossed modes, so no pair of chains agrees (best pair R-hat
     1.025). Only R-hat > 1.01 reports it. A crossing-aware variant (pairwise
     R-hat on retained half-windows) is untested.
   - **Healthy-cell firings of the older checks.** Under the best-of-16
     default the step and warmup-density checks fired on 3 of 43
     gate-passing cells (`hmm_drive_0` 7402001 / 7402003, `lotka_volterra`
     7402001): transient warmup dips on chains that end within 0.2 reference
     SD. WP44 saw 0 of 60 under the old uniform starts. Their specificity at
     the current defaults needs its own count.
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
   a larger static gate before any default change, and MSVC. On Linux the
   question does not arise: WP65 (`STUDIES/bridgestan_linux_dispatch_v1`)
   qualified the concurrent-replica dispatch with 0/500 faults per path,
   bit-identical draws and 0.96x CmdStan wall per gradient, and showed the
   Windows 1.85x gap is the cost of serialising calls (3.46x on Linux).
9. **Reverse-coarsening cost on `accel_gp`** (WP34, WP39, WP39B, WP48): 54 %
   reverse-coarser stops and 0.47x CmdStan; not a truncation artefact, and
   not linear correlation either (a dense metric at condition number 18 is
   1.34x and still 0/3, WP48 post hoc). Its difficulty is unexplained.
   WP70 (`STUDIES/accel_gp_gap_v1`, Linux, 3 seeds) measured 0.567x CmdStan
   and tested three mechanisms, none supported under its frozen criteria:
   reverse-check stops end 55 % of orbits but the median integration time is
   0.87x CmdStan's (cut orbits integrate 0.8–1.2 time units against 3.8–4.0
   for U-turn orbits, a split a median cannot see); depth-cap stops are
   0.0001; metric mismatch is 1.43x CmdStan's. No candidate qualifies:
   `max_depth 12` 0.084x, warmup 2,000 0.192x, `target_accept 0.95` 0.616x
   (it passes `accel_gp` 3/3 at 2.7x the ESS but 2.5x the gradients, 1.09x
   the default per gradient). Post hoc: a smaller adapted step means fewer
   reverse-check cuts and more ESS; a follow-up should preregister the cut
   share and a step-size dose design.
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
12. **`lotka_volterra`: the stall is gone; a secondary-mode trap remains**
    (WP54 side finding, WP57). With `Init::uniform()` starts the model
    stalled past 900 s on 4 of 13 seeds in WP54, under both nonfinite
    policies. WP57 (`STUDIES/lotka_volterra_stall_v1`) found **0/12 stalls at
    the new defaults** (best-of-16), against 4/4 on the WP54 stall seeds with
    uniform starts, all at the 1,200 s cap. The failure that remains is a
    trapped chain on 2 of 12 default seeds. It sits at log density about -430
    against -137, 139–162 reference SD off, with R-hat 1.59. 95–99.5 % of its
    transitions end refinement-exhausted and 6–43 % of its gradients are
    zero-density `rk45` failures. It is not depth caps (at most 6.4 %) and
    not per-call ODE cost. Neither `best_of(64)` (1/12 trapped, plus R-hat
    1.039 on another seed) nor an initial-phase depth cap (the same 2/12)
    fixes it. Open: the trap rate over many seeds, and the restart in
    item 19. WP67 (`STUDIES/trapped_chain_restart_v1`) detected both trapped
    chains by their first-slow-window step (0.1x the chain median; ratios
    0.0023 and 0.025 against a lowest healthy 0.388) and restarted them from
    an independent best-of-16 start: 0/48 trapped, no false positives over
    168 chains, unflagged runs bit-identical. Supported on two events; WP69
    is the confirmation (60 fresh seeds, 17-model breadth, a genuine
    second-mode arm where the rule must not fire, synchronisation cost).
    **WP69 result: not proposed.** 0/240 chains trapped on 60 fresh seeds
    (the trap rate is about 1 in 252 fresh chains), 3 of 5 flags across
    WP67 and WP69 fell on healthy or self-recovering chains, and one real
    trap sat at ratio 0.111, above the 0.1 cut. The restart stays a
    research-only flag; a two-signal rule is the only candidate worth a
    further study.
13. **The per-gradient gap to nutpie on PyMC models** (WP47, WP58): nutpie
    gets 1.6–2.4x more ESS per gradient than oWALNUTS on all three models of
    `STUDIES/python_callpath_v1`. WP58 (`STUDIES/nutpie_per_gradient_gap_v1`)
    reproduced it (pooled 1.70x on the Python path, 1.64x on Rust) and
    decomposed it. Gradient accounting is 0.15 % of the gap and WALNUTS
    refinement 5–7 %. Warmup spend is 44 % (hier 83 %: 72 % of oWALNUTS's
    gradients are warmup, against nutpie's 49 %). nutpie's mass matrix,
    transplanted, closes 44 % (Python) / 60 % (Rust). So the cost is warmup
    spend and nutpie's gradient-informed diagonal metric, not the kernel. On
    eight schools the residual is mostly unexplained, and there nutpie
    diverges (0/3 gates; 0/9 on eight_nc and `gp_pois_regr`, where
    oWALNUTS passes 9/9). Open: an opt-in gradient-informed diagonal metric
    and faster early windows (non-rule follow-ups; the transplant lost gates
    on `gp_pois_regr` and `lotka_volterra`). The Python `init=None` default
    now follows the Rust best-of-16 rule, after `init=None` failed all 12
    Python `lotka_volterra` cells in WP58. WP71
    (`STUDIES/gradient_metric_v1`, Linux) ported nutpie's gradient-informed
    diagonal estimator (`s_i = sqrt(var(x_i)/var(g_i))` per slow window,
    same regularisation, flag `DiagonalMetricEstimator`, off): **not
    supported**, geomean 0.983 (0.844 without `hmm_drive_0`), passes 40 vs
    43, 3 new divergences on centred Eight Schools; the installed variances
    on correlated models came out 3–11x too small. The funnel improved
    (1.57x, divergences 9 -> 5). So the metric estimator is not the gap;
    nutpie's warmup schedule is the remaining candidate (WP73). WP73
    (`STUDIES/warmup_spend_v1`) then measured the spend: median warmup
    shares 0.524 (oWALNUTS), 0.508 (CmdStan), 0.523 (nutpie), so spend is
    not the gap either. What WP73 did find is that every sampler's
    1,000-transition warmup is longer than these models need: a
    500-transition warmup gave 1.32x ESS per total gradient with no gate
    lost (median model 1.25x). WP77 confirms it on fresh seeds. The nutpie
    gap on PyMC models (WP47, WP58) therefore remains unexplained by either
    half of the WP58 attribution.
14. **Fixed `delta = 2`** (WP34, WP37A, WP49, WP53): WP37A did not
    qualify it (funnel gates F3 and F4 failed). As WP49's control it is
    1.141x over posteriordb with 43 gates (1.067x without two seed
    pathologies, matching WP34's 1.070x). WP53 (30 seeds) found WP49's
    divergence tripling did not replicate (37 vs 43 at 20,000 draws), no
    seed beyond |z| 2, the same pooled tail deficit as the default, and
    0.94x the default's funnel ESS per gradient; its rule R2 passed, so the
    confirmation ran as WP63 (`STUDIES/delta2_default_confirmation_v1`,
    4 paired fresh seeds): paired geomean 0.896x, leave-one-seed-out
    minimum 0.860, funnel divergences 26 vs 5, and one passing `accel_gp`
    cell with |z| 5.07; the rule failed on four of six clauses, so
    `delta = 1` stays. The 1.07x (WP34) and 1.14x (WP49) gains did not
    replicate. Closed.
15. **The silent funnel** (WP46, WP55, WP56): oWALNUTS can sample centred
    hierarchical funnels with zero divergences. In WP55, 11 of 12 wrong
    positive cells had zero retained divergences, and all 12 failed the
    R-hat / ESS gates. WP46 attributed this to refinement absorbing the
    energy error. posteriordb v7 does not support that reading: CmdStan and
    nutpie also record zero retained divergences on all six of their
    `seeds_centered` cells and fail on the same `sigma`. At this run length
    plain NUTS gives no divergence signal there either. The
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
19. **Trapped-chain restart by the early step rule** (WP57, WP36). In WP57
    the WP44 step rule, applied at the end of the first warmup stage (S1),
    flagged 10/10 trapped or stalled `lotka_volterra` chains and 0 of 139
    healthy chains, within 0.7–4.5 % of the wall; the density rule there had
    26 false positives.
    `chain_warnings` named the trapped chain in 5/5 completed trapped cells.
    WP57's next step is to restart the flagged chain at the first slow-window
    boundary. The objection is WP36's. A restart copies another chain's
    state, so the independent-start reading of R-hat no longer holds, and
    `restart_from_best` overwrote mapped origins in four cells. WP36 could
    not bound the mode-destruction risk, and WP61 declined to recommend
    restoring rescue for that reason. This is the step-only rescue that
    item 7 lists as unmeasured. WP57 says it would need its own
    confirmation.
20. **The per-gradient release figure is seed-noisy** (WP56, WP60, WP61).
    posteriordb v7 (`STUDIES/posteriordb_bench_v7`) passed 43/51 house cells
    (CmdStan 34, nutpie 26) and 6/15 on the five hard posteriors (CmdStan 7,
    nutpie 3). It failed the v6 release rule on the per-gradient clause:
    0.708x CmdStan against 0.75, formally unevaluable because of one CmdStan
    `lotka_volterra` error. The wall clause failed too (1.85x, Windows
    owned worker). Paired reruns attribute the 0.848 -> 0.708 change neither
    to best-of-16 starts (1.061x) nor to rescue removal (1.023x), but to seed
    variation: the 3-seed geomean moves by about 0.1 between seed sets
    (`STUDIES/rescue_removal_paired_v1`). Open: a breadth headline with more
    seeds, or a seed interval, before a per-gradient threshold is used as a
    release gate. Also open: the v7 per-model losses on `accel_gp` (0.35x
    CmdStan), `one_comp` (0.50x) and `hmm_drive_0` (0.66x).

Closed lines, so they are not reopened: reverse-coarsening as truncation
(WP34 to WP39B); coarsest-first reverse order (WP37B); Appendix C as the
default (WP22, WP23); full scale non-centering (WP17); chain rescue as a
default (WP36); warmup-schedule and step-statistic levers for the
healthy-model gap (WP40 and addenda); scale-free diagonal regularisation as
the default (WP41); a lower fixed `delta` as the default (WP42);
`Init::median_of` (WP43); an automatic dense switch from dimension and
`max|corr|` (WP48); a warmup-window leaf-error rule for `delta` (WP49); the
refined-leaf rate as a silent-funnel warning (WP55); best-of-16 starts and
rescue removal as the cause of the v6 -> v7 per-gradient drop (WP60, WP61);
refinement as the cause of the nutpie gap (WP58).
