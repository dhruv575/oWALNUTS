# WP90: default-flip confirmation of `guard-0.01-0` (`trap_guard_confirmation_v1`)

Status: preregistered at `d71fc639` (harness `df1b9047`, base `main` `f5500db3`; smoke disclosed before the
freeze); executed 2026-10-26 21:11-22:49 UTC on the shared Linux box, lane 1 (cores 0-3), pinned,
co-tenanted; 564/564 cells completed, none rerun, no errors. Tables: `artifacts/results-table.md`;
machine-readable `artifacts/summary.json`; cells in `artifacts/cells/`.

## Verdict

**QUALIFIES by the frozen rules: R1-R8 all hold. `guard-0.01-0` (the WP67 trapped-chain restart rule at
step ratio 0.01, scored at the close of the first slow window) is proposed for the default flip** (the
`proposed_flip` text in `protocol.json`; the coordinator applies it). No default was changed by this study.

| rule | observed | held |
|---|---|---|
| R1 Part 1 passes guard >= defaults | 92 = 92 of 132 (equal on every model) | yes |
| R2 bit identity | 282/282 pairs: 268 unfired cells identical (chains and cell), 14 fired cells with every untouched chain identical; 0 errors | yes |
| R3 no new divergences | 0 models, 0 passing cells with more guard divergences | yes |
| R4 headline ESS/gradient guard/defaults >= 0.98 | geomean **1.0000** over 22 models; paired per-seed median 1.0000, bootstrap 95 % [1.0, 1.0]; only 2 of 132 pairs differ from 1 (0.979, 1.0025, the two fired cells) | yes |
| R5 funnel P5 within 2 s.e. of 0.04779 | 30/30 cells, P5 0.04579 +- 0.00159 (1.26 s.e. below exact; `diag` identical); **0 firings**; lowest healthy ratio 0.066 | yes |
| R6 SV trapped chains, guard | **0/480** (defaults 8/480 in 7 cells; WP89 8/480) | yes |
| R7 false firings over Parts 1-2 | 2 firings on Part 1 (both `kilpisjarvi`), 0 on the funnel; both satisfy the frozen T3 clause, so **0 false firings** by the frozen definition; see the caveat below | yes |
| R8 library integrity | fingerprint tests 3 + 3, `trapped_chain_restart` 5 passed; clippy clean on the library (all features) and the study crate; `git diff f5500db3 -- src tests Cargo.*` empty | yes |

Predictions: P3, P4, P5, P6, P7 held; **P1 and P2 did not**. P1 (any Part 1 firing on `lotka_volterra` or
`GLMM_Poisson`): the two firings were on `kilpisjarvi`, a model not named. P2 (defaults passes 98-112):
92, a seed effect that is identical in both arms (WP85's 105 on seeds 868501-868506 against 92 here; the
differences are on `one_comp` 4 -> 1, `lotka_volterra` 6 -> 4, `seeds_centered` 2 -> 0, `grsm_irt` 6 -> 4,
`kilpisjarvi` 5 -> 4, `gp_pois_regr`, `hmm_drive_0`, `accel_gp` each one fewer).

## The one caveat the rules did not anticipate (read before applying the flip)

Both Part 1 firings (`kilpisjarvi` 9050101 chain 1 at ratio 0.0092, 9050106 chain 0 at ratio 0.0063; a
3-dimensional near-Gaussian regression with a strongly correlated intercept and slope) are **true
firings by the frozen T3 clause** but not by the spirit of WP69's definition:

- At the defaults both chains recovered on their own: end-of-warmup steps 0.0030 / 0.0043 against their
  siblings' 0.0029-0.0116, retained medians at the mode (shift 0.12 / 0.11 reference SD), not named by
  the warnings. Under WP69's end-state definition (more than 3 reference SD off) they would have been
  false positives; WP89's near-traps satisfied the same T3 clause and escaped later too, which is why
  T3 was written, but there the chain was 1,000-7,000 nats *below* its siblings at transition 99.
- Here the fired chain was the **best-placed** chain at transition 99: log density -187 / -125 against a
  chain median of -558 / -609 (the siblings with large steps sat at -7,093 and -908, -5,631 and -981).
  On `kilpisjarvi` no chain is near the typical set (-98) at transition 99: the identity-metric warmup
  is slow on this model (every chain spends about 1M gradients in warmup; retained steps 0.003), and the
  chains' steps at the window close are dispersed over three orders of magnitude (ratios 0.006 to 72
  across the six defaults cells), so the chain-median step is a noisy reference there. T3 is
  satisfied because *every* chain is more than 3 IQR below the retained reference at that point, not
  because the fired chain was behind.
- The firings were harmless: the two cells fail the gates in both arms on the *other* chains (R-hat
  1.010 / 1.012 at the defaults, 1.011 / 1.013 with the guard, `RHat` warnings on chains 2 and 2, 3 in
  both arms), the untouched chains are bit-identical, cell gradients 0.991x and 1.027x, ESS per gradient
  1.0025x and 0.979x, the restarted chains ended at the mode (shift 0.08 / 0.04 SD, not warned) after
  abandoning 6,508 and 30,920 gradients. Over the 1,056 Part 1 chains the rate of such firings is 0.2 %.

The mechanical verdict stands: the rules were frozen, R7 holds as written, and the cost of the two firings
is nil. But the coordinator should apply the flip knowing that on a low-dimensional model with slow
identity-phase warmup the 0.01 rule can restart a chain that is merely the slowest of four equally
unadapted chains. The lowest healthy ratios elsewhere were `lotka_volterra` 0.025 (9050101, a chain the
warnings did not name, cell failing on chain 2), `earnings` 0.052, `eight_schools_centered` 0.25; funnel
0.066 (30 x 4 chains). A ratio of 0.01 therefore sits 2.5x below the lowest healthy chain seen on the 23
models of WP67, WP69, WP89 and WP90 outside `kilpisjarvi`, and 1.6x above `kilpisjarvi`'s two.

## Part 3: the SV model (efficacy)

Defaults: 8 trapped chains of 480 in 7 cells (9090127 c0, 9090129 c0 and c2, 9090132 c1, 9090134 c0,
9090155 c0, 9090178 c3, 9090201 c3), every one started at log_sigma 1.51-1.80, step at transition 99 1e-11
to 8e-8 (ratios 2e-8 to 1e-4), 798k-837k warmup gradients against a median of 170k, named by the
warnings (WP89's mechanism exactly). Guard: 13 firings on 13 chains (12 cells): the 8 traps plus 5
near-traps (9090143 c3, 9090158 c1, 9090160 c3, 9090161 c2, 9090166 c3; ratios 6.6e-4 to 6.2e-3, starts at
log_sigma 1.2-1.8, steps 3e-7 to 3e-6 at transition 99, 234k-821k warmup gradients at the defaults; all
escaped by the end at the defaults, one of them with a warning). Every firing carries the T3 signature;
every restarted chain ended at the mode; guard trapped 0/480; the guard arm spent 0.88x the defaults'
target calls over Part 3 (98.1M against 111.5M) because a restarted chain repeats 100 warmup transitions
instead of crawling for 900. Median cell wall 2.30 s against 2.28 s (pinned, co-tenanted). 108/108 unfired
cells bit-identical.

## Part 2: the funnel

30 seeds x 4 x 2,000/20,000: `guard` bit-identical to `diag` on 30/30 cells, 0 firings (lowest ratio at
the window close, transition 199: 0.066; the smoke seed had shown 0.055), pooled P5 0.04579 +- 0.00159
(exact 0.04779; 1.26 s.e. below; the largest single-seed |z| was 2.98), 58 divergences in both arms.

## Part 1: the 22 v7 posteriors

92 = 92 passes; every per-model pass count, divergence count and headline ratio equal between arms
except the two `kilpisjarvi` cells (ratios 0.979 and 1.0025, both failing the gates in both arms). Total
gradients 121.36M (defaults) vs 121.43M (guard); wall sums 2,422 s vs 2,472 s (co-tenanted; the per-model
wall-per-gradient geomean 1.022 is co-tenancy noise plus the guard's synchronisation point, WP69 measured
+1.15 % at 4 chains). Max |z| on passing reference cells 4.41 (`one_comp` 9050104, identical in both
arms; not a WP90 rule). Passes per model (defaults = guard): eight_schools_nc 6, eight_schools_c 0,
diamonds 6, earnings 6, mesquite 6, kidiq 6, sblrc 6, nes 6, arK 6, arma11 6, garch11 6, gp_pois_regr 5,
hmm_example 6, hmm_drive_0 5, one_comp 1, lotka_volterra 4, accel_gp 0, GLMM_Poisson 0, seeds_centered 0,
kilpisjarvi 4, grsm_irt 4, radon 3.

## Design (frozen at `d71fc639`)

`PREREGISTRATION.md` and `protocol.json`. Part 1: 22 v7 posteriors x 6 fresh seeds (9050101-9050106) x
{`defaults`, `guard-0.01-0`} at 4 x 1,000/1,000 (WP85's shape, gates and tiers; WP89's cell). Part 2: the
funnel at 30 fresh seeds (9080301-9080330). Part 3: the WP84 SV model at 120 fresh seeds (9090101-9090220),
WP89's cell and census with WP89's anchor frozen. Run order S, F, P; every cell once; no library change.
Smoke (seed 9059901) disclosed in `PREREGISTRATION.md`; `artifacts/smoke/`.

## Amendments and deviations

- None to the design, rules, seeds or predictions after the freeze.
- Analysis note: the box's `analyze` pass read no `environment.json` (the setup had written it into the
  repo's `artifacts/` rather than the lane's artifact root), so the box-side table reported R8 as
  unknown; the analysis was rerun unchanged on the laptop over the same cells with the box's
  `environment.json` in place (`artifacts/box-logs/` holds the test, clippy and diff logs it summarises).
  No cell, rule or definition changed.
- The run took 1 h 38 min of lane time against the 3 h budgeted (Part 1 1 h 24 min; WP85's 2.5 h for
  the same cells included the dense arm's heavier cells).

## Files

`PREREGISTRATION.md`, `protocol.json` (+ `make_protocol.py`), `run_study.py`, `checksums.py`,
`src/bin/{pdb_cell,sv_cell,funnel}.rs`, `models/data.json`, `box/*.sh`. `artifacts/cells/*.json` (564
cells; draws stripped), `artifacts/summary.json`, `artifacts/results-table.md`, `artifacts/run-log.txt`,
`artifacts/box-evidence-log.txt`, `artifacts/environment.json`, `artifacts/measured_on.json`,
`artifacts/models.sha256` (the 22 BridgeStan libraries, byte-identical to WP85's), `artifacts/box-logs/`,
`artifacts/draws-manifest.sha256` (504 `.npz` on the box, out of git), `artifacts/telemetry-manifest.sha256`
(240 SV telemetry files on the box, out of git), `artifacts/smoke/`, `CHECKSUMS.sha256`.

## Reproduce (on the box, lane 1)

```
bash box/setup.sh <bundle> wt/trap-guard-confirm f5500db3 <source repo>   # build, models, R8 checks
bash box/smoke.sh                                                           # non-evidence
nohup bash box/run_all.sh > logs/evidence.log 2>&1 &                        # resumable; never reruns a cell
bash box/post.sh                                                            # analyze, manifests, tarball
python checksums.py
```
