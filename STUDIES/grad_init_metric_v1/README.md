# WP94: the gradient-scaled initial metric as a default-flip candidate (`grad_init_metric_v1`)

Status: preregistered at `e9578cc1` (library `d6985347` on base `main` `a042a728`; smoke disclosed before the
freeze); executed 2026-10-27 01:15-02:23 UTC on the shared Linux box, lanes 1-2 (cores 0-3 and 4-7, two cells
at a time), pinned, co-tenanted; 906/906 cells completed, none rerun, no errors. Tables:
`artifacts/results-table.md`; machine-readable `artifacts/summary.json`; cells in `artifacts/cells/`.

## Verdict

**DOES NOT QUALIFY by the frozen rules: R1, R3 and R6 fail; R2, R4, R5 and R7 hold.** The flag stays
research-only; no default changed. The candidate is a large net efficiency gain (R2 geomean **1.150**, paired
per-seed median 1.079 [1.037, 1.141]; warmup gradients 0.874x) that is bought with new multimodal failures on
five house models, and the cause-level fix alone leaves 4/480 SV chains trapped.

| rule | observed | held |
|---|---|---|
| R1 Part 1 passes gradinit >= defaults | **96 vs 101** of 132 (gradinit-noguard 96) | no |
| R2 headline ESS/gradient >= 0.98 | geomean **1.1500** over 22 models; paired median 1.0793, bootstrap 95 % [1.037, 1.141], range [0.002, 19.6] | yes |
| R3 warmup gradients reported; no model's gates drop | warmup-gradient geomean **0.874**; gates dropped on **6 models** (mesquite 6->5, gp_pois_regr 6->5, hmm_drive_0 6->4, one_comp 4->3, lotka_volterra 6->5, seeds_centered 1->0); gained on grsm_irt 5->6 and radon 1->2 | no |
| R4 no new divergences | 0 models, 0 passing cells (centered eight schools 4 -> 3) | yes |
| R5 funnel P5 within 2 s.e. | gradinit 0.04932 +- 0.00262 (z +0.58), diag 0.04747 +- 0.00200 (z -0.16); 0 firings | yes |
| R6 SV: noguard <= 1/480, gradinit 0/480 | **gradinit-noguard 4/480** (0.8 %); gradinit 0/480 with **4 guard firings** (the same 4 chains); defaults 0/480 with 15 firings | no |
| R7 library and flag-off integrity | fingerprints 3 + 3, `grad_init_metric` 6, `trapped_chain_restart` 8 passed; clippy clean on both crates; `custom_noop` bit-identical to `defaults` / `diag` on 4/4 smoke kinds | yes |

Predictions: P4, P5 (clause for the three ruled arms), P7 held; P1, P2, P3, P6 did not (details below).

## What the evidence says

**The mechanism is only half the story (R6).** With the gradient-scaled initial metric the healthy SV chains
are at step 0.065 at the first slow-window close instead of 4e-4 (median over 480 chains; the identity
metric is wrong by 10-150x on `z`), warmup costs 96k gradients per chain instead of 171k (0.56x; 47.9M
against 82.4M over the arm), and the median cell wall falls from 2.30 s to 1.65 s. The guard fired on 4
chains under `gradinit` instead of 15 under `defaults`: 11 of the 15 would-be traps and near-traps are gone at
the cause. But 4 remain: without the guard they are trapped (starts at log_sigma 1.47-1.98, step 7e-6 to
9e-16 at transition 99, 816k-876k warmup gradients, all four named by the warnings), with initial masses of
5,000-10,000 on `log_sigma` and 30-180 on the `z` block. The scaled metric does not make a stiff
high-sigma start's first transition acceptable on every seed; WP89's `nutpie_init` rate of 1/240 (0.4 %)
was the lucky half of this study's 4/480 (0.8 %). The guard catches all four (ratios 1e-4 to 2e-14 against a
chain median step of 0.04-0.08), so `gradinit` is 0/480; the rule asked the cause-level fix to do it alone.

**The house set loses more than it gains at the gates (R1, R3), for a reason the guard cannot cover.** Nine
cells changed their gate result: three gained (grsm_irt 9450105, radon 9450106, one_comp 9450102: R-hat
1.013 -> 1.006, 1.013 -> 1.007, tail ESS 313 -> 600) and six lost. Three of the six are mild (mesquite 9450104
R-hat 1.0065 -> 1.0129, gp_pois_regr 9450103 1.009 -> 1.0105, one_comp 9450104 / 9450105 tail ESS 1020 -> 274 and
520 -> 286). Three are chains that ended in the wrong place:

- `lotka_volterra` 9450105: R-hat 1.004 -> **2.30**, min bulk ESS 964 -> 5, chains 0 and 2 shifted, 936k
  gradients against 364k. At the defaults this seed is one of the three Part 1 guard firings (chain 0 restarted
  at ratio 0.0018 and the cell passed). Under `gradinit` **no Part 1 chain fired at all**: the scaled metric
  lifts the stuck chain's step above 1 % of the chain median without freeing it, so the step-ratio guard no
  longer sees it. Paired ratio 0.002.
- `hmm_drive_0` 9450101 / 9450102: R-hat 1.007 -> 1.53 and 1.003 -> 1.056, chains shifted (0; 1 and 2),
  `WarmupLogDensity` warnings. Paired ratios 0.003 and 0.015.
- `seeds_centered` 9450103: R-hat 1.003 -> 1.039, bulk ESS 576 -> 130.

Warned chains over the 132 cells: 19 (11 cells) at the defaults, 29 (18 cells) under `gradinit`. The initial
masses behind this are extreme on some models: kilpisjarvi 290 to 1e8, sblrc 245 to 2e6, GLMM 0.35 to 6e5,
grsm_irt 4e-5 to 2e3 (`artifacts/results-table.md`, per-model column): a gradient at a uniform(-2, 2) start is
a scale only when the start is near the typical set in that coordinate.

**Where it wins (R2).** The gain is real and large where the identity phase is expensive: radon 2.11 (warmup
gradients 0.49x), accel_gp 2.98, centered eight schools 1.63, grsm_irt 1.45 (0.71x), kidiq 1.34 (0.56x),
seeds 1.31, hmm_example 1.23, earnings 1.16, arma 1.11, gp_pois_regr 1.10, nes 1.10, mesquite 1.09, sblrc 1.09,
arK 1.04; neutral on garch 1.00, eight_schools_nc 0.99; losses on lotka 0.96, one_comp 0.93, hmm_drive_0 0.93,
kilpisjarvi 0.92 (warmup gradients 1.19x: its 1e8 masses cost), diamonds 0.89, GLMM 0.53 (warmup 0.70x but
retained ESS lower). Part 1 total gradients 120.7M against 122.3M (warmup 56.3M vs 58.0M); wall sums 2,062 s
against 2,673 s (co-tenanted; the per-model wall-per-gradient geomean is 1.01). `gradinit-noguard` is
bit-identical to `gradinit` on all 132 Part 1 cells (no firing) and on all 30 funnel cells.

**The funnel (R5, reported arms).** Fixed starts (`x = 0`, where the x-gradients vanish and the rule puts the
1e-20 floor on 9 of 10 coordinates): P5 0.0493 +- 0.0026 against `diag` 0.0475 +- 0.0020, 27 divergences
against 49, 134.6M calls against 130.1M (1.03x; the smoke's 3x at 200 warmup shrank to 3 % at 2,000),
median min bulk ESS 533 vs 499, 0 firings. With the sampler's own best-of-16 starts: `gradinit-best16`
0.0450 +- 0.0014 (z **-2.01**, just outside 2 s.e.; `diag-best16` 0.0501 +- 0.0018, z +1.31), 23 vs 65
divergences, 139.5M vs 136.4M calls. Not a rule; a second observation (with the mesquite / one_comp tail-ESS
drops) that the candidate reaches the tails slightly less often.

## Predictions

- P1 (defaults 88-100; gradinit within -3..+4): **not held**, 101 and 96 (-5).
- P2 (headline in [0.97, 1.08], paired median in [0.95, 1.10], no model below 0.85): **not held** on the
  first clause, geomean 1.150 (median 1.079 held); GLMM 0.53 is below 0.85.
- P3 (warmup-gradient geomean in [0.80, 1.02], no pass count drops): **not held** on the second clause
  (0.874 held; six models dropped).
- P4 (R4 holds; divergence totals equal on >= 18 models): **held** (21 equal).
- P5 (P5 within 2 s.e. on the three ruled arms, 0 firings): **held**; the reported `gradinit-best16` sits at
  -2.01 s.e.
- P6 (defaults 3-16 trapped with 6-16 firings; noguard 0-2; gradinit 0 with 0-3 firings): **not held**:
  defaults 0 trapped (the guard, now the default, removed them) with 15 firings, noguard 4, gradinit 0 with
  4 firings.
- P7: **held**.

## Design (frozen at `e9578cc1`)

`PREREGISTRATION.md` and `protocol.json`. Part 1: 22 v7 posteriors x 6 fresh seeds (9450101-9450106) x
{`defaults`, `gradinit`, `gradinit-noguard`} at 4 x 1,000/1,000 (WP85 / WP90's cell, gates and tiers).
Part 2: the funnel at 30 fresh seeds (9480301-9480330), five arms (the three ruled arms on the harness's
fixed starts, plus `diag-best16` / `gradinit-best16` on the sampler's own starts, reported). Part 3: the WP84
SV model at 120 fresh seeds (9490101-9490222 minus 9490211 / 9490212, which occur in an options_flow seed
audit), WP89's census with WP89's anchor. Two lanes by manifest position; every cell once. Smoke (seed
9459901) disclosed in `PREREGISTRATION.md`; `artifacts/smoke/`.

## The library change (`d6985347`, research feature, default off)

`WarmupConfig::with_initial_metric(InitialMetric::GradientScaled { lower, upper })`,
`InitialMetric::nutpie()` (1e-20, 1e20): per chain, once, in `ChainRun::start_from` after the start is
chosen and before the initial-step search, the diagonal the chain starts warmup with becomes
`mass_i = clamp(|g_i(start)|, lower, upper)` (1 where not finite): nutpie's `update_diag_grad` initial rule
(nuts-rs 0.17.3, `src/mass_matrix/adapt.rs` `Strategy::init`, `src/cpu_math.rs`
`array_update_var_inv_std_grad`: `variance_i = 1 / clamp(|g_i|, 1e-20, 1e20)`, non-finite -> 1; `|g|`, not
`g^2`). A restarted chain's replacement start is scaled the same way; a configured step search probes the
scaled metric per chain; one target evaluation per chain start is added to the admission bound; the dense,
structured and continuation facades reject it. `tests/grad_init_metric.rs` (flag off bit-identical, the
exact mass per coordinate, clamp bounds, 1- and 4-chain runs, admission, validation); the kernel
fingerprints are untouched. `b512856a` fixed two pre-existing `clippy --all-targets -D warnings` failures in
WP91's bench example and test. `CHANGELOG.md` [Unreleased] carries the entry.

## Amendments and deviations

- Before the freeze, because of the Windows smoke: the two `-best16` funnel arms (reported, not ruled) and
  the zero-gradient note in the preregistration. None to the design, rules, seeds or predictions after the
  freeze.
- The first box setup ran against the wrong checkout (the bundle's base `a042a728` was missing from the box's
  reference clone, so the fetch failed); it was rerun from a bundle based at `a49df8007` before the smoke and
  before any evidence cell (`artifacts/box-logs/setup-attempt1-wrong-checkout.log` is not kept; the
  successful `setup.log` is).
- The run took 1 h 8 min of two-lane time against the 3 h budgeted.
- The shared `/var/tmp/keep-alive` was removed at the end of post-processing as the lane protocol asks and
  restored a minute later because another lane's study was still listed as running.

## Files

`PREREGISTRATION.md`, `protocol.json` (+ `make_protocol.py`), `run_study.py`, `checksums.py`,
`src/bin/{pdb_cell,sv_cell,funnel}.rs`, `models/data.json`, `box/*.sh`. `artifacts/cells/*.json` (906 cells;
draws stripped), `artifacts/summary.json`, `artifacts/results-table.md`, `artifacts/run-log*.txt`,
`artifacts/box-evidence-log.txt`, `artifacts/environment.json`, `artifacts/measured_on-lane{0,1}.json`,
`artifacts/box-logs/`, `artifacts/draws-manifest.sha256` (906 `.npz` on the box, out of git),
`artifacts/telemetry-manifest.sha256` (360 SV telemetry files on the box, out of git), `artifacts/smoke/`,
`artifacts/models.sha256` (the 22 BridgeStan libraries, WP85's, byte-identical: `box-logs/wp85-models.sha256`),
`CHECKSUMS.sha256`.

## Reproduce (on the box, lanes 1-2)

```
bash box/setup.sh <bundle> wt/grad-init-metric a042a728 <source repo>   # build, models, R7 checks
bash box/smoke.sh                                                        # non-evidence
nohup bash box/run_all.sh > logs/evidence.log 2>&1 &                     # two lanes; resumable; never reruns a cell
bash box/post.sh                                                         # analyze, manifests, tarball
python checksums.py
```

## Next

The candidate is not dead: the gain where the identity phase is expensive is 1.3-3x, and the SV warmup
halves. What fails is the rule as stated, on two counts that a confirmation would have to fix first: (1) a
gradient at a uniform(-2, 2) start is not a scale when the start is far from the typical set in that
coordinate (masses of 1e5-1e8 on kilpisjarvi, sblrc, GLMM; the lotka / hmm_drive_0 chains that ended in
the wrong mode), so a bounded rule (a cap on the ratio to the median coordinate, or nutpie's `|g|` damped
toward 1) is the next candidate; (2) the step-ratio guard loses its signal under a scaled metric on
lotka_volterra (no firing on a cell that fires at the defaults and then fails), so any initial-metric
candidate must be paired with a guard whose signal survives it (WP90's suggested two-signal variant:
step ratio and log density below the chain median).
