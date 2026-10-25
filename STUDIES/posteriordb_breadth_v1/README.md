# posteriordb breadth v1 (WP46): the shipped defaults on posteriors never used before

## Verdict

**Mixed.** On the 14 unseen posteriordb posteriors that have reference draws,
the shipped 0.2.0 defaults pass **40 of 42 cells (95 %)**. That is higher
than v6's 45/51 (88 %) on the tuned set, and higher than the preregistered
32 (interval 28–36), so P1 failed in the optimistic direction. No passing
cell has max |z| > 4. The reference set is not a hard test, though: 22 of
the 30 eligible posteriors are ARM linear regressions, and posteriordb at
`28f8d3d` has **no reference draws for any of the families the question
named** (GLMMs, hierarchical logistic, survival, ordinal, hundreds of
parameters, new ARMA/GARCH variants).

On the gates-only tier, which covers those absent families without
reference draws, the defaults pass **8 of 15**. Two posteriors fail every
seed, each through a failure class that had not been recorded before:

- **Box-constraint corner traps** (`GLMM_Poisson`, 0/3). Four of 12 chains
  are held in the wide region that the uniform-prior boxes create, and three
  of them are pinned at the walls (alpha = -20, beta1/beta2 = 10, sigma near
  5). They sit 270 to 27,700 nats worse than the healthy chains, and R-hat
  reaches 1.6 to 2.8.
- **A silent funnel** (`seeds_centered`, 0/3). One chain per seed sticks in
  the neck of the funnel on `sigma` (per-chain ESS 6 to 33) with **zero
  divergences** in warmup and sampling. The usual warning signal never fires.

No default change follows from this study, as preregistered.

| quantity | value |
|---|---|
| reference tier, cells passed | **40 / 42** (P1 predicted 32, interval 28–36: **failed**, rate above v6) |
| gates-only tier, cells passed | **8 / 15** (P3 interval 7–13: **held**) |
| passing reference cells with max \|z\| > 4 | **0** (largest 2.79; failing kilpisjarvi cell 3.28) (P4: **held**) |
| process errors / timeouts | **0 / 57** (P5: **held**) |
| retained divergences, all 57 cells | **0** |
| predicted failing models (P2) | 3 of 5 failed (`kilpisjarvi`, `kidscore_interaction`, `seeds_centered`); `hmm_drive_1` and `logearn_logheight_male` passed 3/3; `GLMM_Poisson` and `grsm` failed unpredicted: **failed** |
| modal primary mechanism among failing reference cells (P6: depth cap) | only 2 failing reference cells (multimodality label, unclassified); **failed** |

Walls are contended. Ten agents shared 16 cores, and on Windows the owned
BridgeStan worker serialises every gradient call (`execution =
OwnedSerialised`, one effective replica of four requested). The walls are in
the tables, labelled, and are never used as evidence.

## Design in one paragraph

oWALNUTS only, at `Sampler` defaults with nothing overridden. This is the
post-WP36 default, which has **no chain rescue**; v6's 45/51 was measured
with `restart_from_best` on. Runs used 4 x 1,000/1,000, four threads, seeds
461461–461463, and a strictly sequential order. The house gates applied (rank
R-hat <= 1.01, bulk and tail ESS >= 400 on every gate parameter, zero retained
divergences), with a z for every reference parameter against posteriordb's
reference draws. The 14 reference-tier posteriors were chosen by a frozen
rule, applied before any sampling (`select_posteriors.py`). The rule takes
every eligible singleton family, then the two (or one) highest
reference-correlation-condition members of each multi-member family. The five
gates-only posteriors were fixed by family before sampling. All 19 compiled
with BridgeStan before the freeze (`artifacts/compile-status.json`). The
preregistration was committed at `2a5f8187` before the first evidence cell.

## Evidence

All 57 cells are in `artifacts/results-table.md` (per-cell step, step
spread, depth-cap fraction, refined-leaf fraction, invalid evaluations,
exhaustions, cross-chain disagreement, gradients, ESS/gradient, wall and
mechanical labels) and `artifacts/summary.json`. Per-cell JSON with
per-parameter statistics, per-chain warmup step traces, work totals and
starts is in `artifacts/cells/`. `artifacts/posthoc-descriptive.md` is a
post-hoc, descriptive table of step-collapsed chains and per-cell gradient
outliers. It was written after the cells were seen and is not a
preregistered statistic.

| model | tier | pass | notes |
|---|---|---|---|
| low_dim_gauss_mix | ref | 3/3 | seed 461462: one chain's step 0.0087 vs 0.61; warmup cost 5.2x the model median (post-hoc) |
| kilpisjarvi | ref | **2/3** | 12–20 % depth-capped on every seed; seed 461462 R-hat 1.45, bulk ESS 8 |
| gp_regr | ref | 3/3 | |
| hmm_drive_1 | ref | 3/3 | no mode lottery on three seeds; seed 461463 warmup cost 2.4x |
| sblri-blr | ref | 3/3 | Stan-regularisation floor dominates five beta coordinates (installed / empirical variance 12x) |
| logearn_logheight_male | ref | 3/3 | condition 5.4e4, no depth caps; 2.6–3.0 M gradients per cell |
| logearn_height_male | ref | 3/3 | seed 461463: one chain step 0.0033 vs 0.027 |
| kidscore_interaction | ref | **2/3** | seed 461461 R-hat 1.0117, ESS 703 |
| kidscore_mom_work, interaction_c2, logmesquite_logvas, mesquite, nes1996, nes1980 | ref | 3/3 each | clean |
| seeds_centered | gates | **0/3** | silent funnel on `sigma`, 0 divergences |
| GLMM_Poisson | gates | **0/3** | corner traps on the box bounds, one fully frozen chain |
| radon_all hierarchical_intercept_centered | gates | 3/3 | 391 parameters; all borderline (min bulk ESS 416–463 on `beta[1]`) |
| sat hier_2pl | gates | 3/3 | 672 parameters; borderline only through max R-hat 1.008–1.009 |
| science_irt grsm | gates | **2/3** | seed 461461 R-hat 1.016; `lambda_adj[1]` per-chain ESS 14 |

## Failure taxonomy

The frozen classifier flagged 25 cells: 9 failing and 16 borderline. The
borderline thresholds were R-hat > 1.005, minimum ESS < 600 or |z| > 3.
Each paragraph below gives the mechanical labels first and then the reading
from the telemetry. Where the two differ, both are stated.

**kilpisjarvi 461462 (fail; mechanical: multimodality, depth_cap,
metric_floor). Reading: depth cap plus per-chain step collapse on a
degenerate ridge, not multimodality.** The reference |corr(alpha, beta)| is
1.0000 (condition 1.7e5), from an uncentred year covariate. Chain 0's warmup
step stayed at 0.0005–0.0016 from transition 50 onward, while the other
chains reached 0.006–0.012. Its retained step is 0.0018 against 0.002–0.004
for the others, and it hit the depth-10 cap on 435 of 1,000 transitions. The
chain covered 1.3 % of the pooled alpha/beta variance (per-chain ESS 7).
Its displacement is 2.1 reference sd along the ridge, and its median energy
is only 1.8 nats above the others. The posterior is a unimodal Gaussian
ridge, so the "multimodality" label (disagreement without an energy gap)
here describes a chain stuck partway along a ridge it cannot traverse within
1,023 leapfrog steps. The metric_floor label fires because that chain's
retained variance on beta is 1/67,000 of its installed variance; this is the
same stuck chain, not the Stan floor.

**kilpisjarvi 461461, 461463 (borderline; depth_cap).** These pass with bulk
ESS 847 and 842 while 12 % and 13 % of retained transitions are capped. They
cost about 4.1 M gradients, 2.0e-4 ESS/gradient, the worst ratio among the
passing cells. This is the diamonds depth-cap class on a three-parameter
model.

**kidiq-kidscore_interaction 461461 (fail; unclassified_slow_mixing).**
R-hat 1.0117 on `beta[1]`, bulk ESS 703, chains agreeing to 0.17 sd, no caps
(depth 6–8), equal steps. Reference condition number 3.9e3 (interaction
without centring). Per-chain ESS is 106–208, and at that level a rank R-hat
just over 1.01 is gate noise on a correlation-slowed diagonal-metric target,
not a broken chain. **461463 (borderline)** is the same picture at R-hat
1.0057.

**earnings-logearn_logheight_male 461463, logearn_height_male 461462
(borderline; unclassified) and logearn_height_male 461461 (borderline;
metric_floor).** These are the same correlation-slowed regressions. All
pass with ESS 899–1,261 and R-hat 1.005–1.008. The metric_floor label on
461461 is one coordinate (beta[2], variance 8e-5) where the installed
variance is 2.9x the retained one. That chain's final step is 0.016 against 0.024–0.026 for the others.
Seed 461463, which is not flagged, has a chain whose final step fell to 0.12x
the median (installed / empirical 76x on beta[2]; its warmup step dipped to 2e-4 near
transition 200) and still passed.

**sblri-blr 461462, 461463 (borderline; metric_floor).** This is a true
metric floor. The five beta coordinates have posterior variance about 1e-6.
Stan's regularisation adds 1e-3 x 5/(n+5), about 1e-5 at the last window,
so the installed variance is 11–14x the true one on every chain of every
seed. It passes (bulk ESS 665–831, step 0.21). This is WP27's sblrc
mechanism on the sibling data set, at a cost rather than a failure, and it is
shared by CmdStan, which uses the same regulariser.

**seeds_centered 461461, 461462, 461463 (fail x3; unclassified_slow_mixing).
Reading: a silent funnel, which is a new class.** This is a centred
binomial-logit random-intercept model with 21 groups. The worst parameter
on every seed is `sigma`: bulk ESS 272, 60 and 92, tail ESS 124, 15 and 26,
R-hat 1.020, 1.066 and 1.038. On 461462 and 461463 one chain has per-chain
ESS 6 and 7 and a lower chain mean of `sigma` (0.28 against 0.33 pooled),
with a wider energy IQR (17.8 against about 10). It has dropped into the neck
and stays there. Steps are equal across chains (0.12–0.26) and there are no
depth caps. **Retained and warmup divergences are zero on every seed.**
Refinement (refined-leaf fraction 0.4–1.0 %) absorbs the energy error that
would make NUTS diverge. The funnel is therefore sampled without the
divergence signal that tells a Stan user to reparameterise, and only the
`sigma` R-hat and tail ESS reveal it. Centred Eight Schools (v6 0/3) is the
known relative, but v6 recorded divergences there and the smoke test with
seed 1 recorded 2.

**GLMM_Poisson 461461, 461462, 461463 (fail x3; start_lottery plus
depth_cap / step_collapse / metric_floor / constraint_boundary). Reading:
box-constraint corner traps, which is a new class.** The model puts
`uniform` priors on box-bounded parameters (`alpha` in (-20, 20), the betas
in (-10, 10) or (-10, 20), `sigma` in (0, 5)), with 40 free year effects.
On every seed, 1–2 chains are held in a wide, poor region; three of the
four are pinned at the walls:

- **461463, chain 2:** `alpha` = -20.000, `beta1` = 9.99, `beta2` = 9.998,
  `sigma` = 3.2. Its median energy is 27,835 against about 100, all 1,000
  retained transitions are refinement-exhausted (a frozen chain), and there
  are 138,061 invalid evaluations.
- **461462, chain 0:** `alpha` = -19.975, `sigma` = 4.997, energy 1,291.
- **461462, chain 1:** `sigma` = 4.90, energy 360.
- **461461, chain 2:** not pinned, but wandering the wide region (`beta1`
  mean -5, sd 5.5; `sigma` 2.8), step 0.0022 against 0.12, 343 depth caps,
  energy 366.

Near a wall the logit Jacobian flattens the density along the bounded
coordinate, and the free year effects absorb the misfit. The chain sits in
a wide, bad, locally stable region. Starts are uniform(-2, 2) on the
unconstrained scale, so `alpha` starts anywhere in (-15, 15), and log-rates
of exp(15) are reachable. The healthy chains agree with each other to the
third decimal. The gap is detectable trivially: 270–27,700 nats in median
energy against healthy within-chain IQRs of 23–100.

**radon_all hierarchical_intercept_centered 461461–461463 (borderline;
unclassified).** All three pass, with minimum bulk ESS 416, 441 and 463,
always on `beta[1]`, the coefficient of the county-level log-uranium
covariate. That direction is confounded with the 386 county intercepts and
their mean. A diagonal metric cannot represent a global coupled to hundreds
of locals, so per-chain ESS on it is 78–157. This is the global-to-local
coupling of open question 5, met outside state-space models. The R-hat
borderlines (1.0075–1.0083) are on assorted `alpha[j]`.

**sat hier_2pl 461461–461463 (borderline; unclassified). Reading: a gate
artefact, not a sampler failure.** Every ESS is >= 1,763. The only trigger
is the maximum rank R-hat over 672 parameters (1.0077–1.0086, on assorted
`theta[j]`). The maximum of several hundred R-hats sits near 1.008 at this
run length even with no sampler problem, so the 1.005 borderline threshold
is not informative at this dimension.

**science_irt grsm 461461 (fail; unclassified) and 461462 and 461463
(borderline).** The failing cell has R-hat 1.016 (`beta_free[2]`) with bulk
ESS 543 on `lambda_adj[1]`, and chain 2's ESS on `lambda_adj[1]` is 14. The
chain mean is unbiased (1.278 against 1.274 pooled, sd 0.10), so the chain is
slow rather than displaced. `lambda_adj` is the latent-regression
coefficient in `theta ~ normal(W * lambda_adj, 1)` for 392 persons. It is
the same global-coupled-to-many-locals direction as radon's `beta[1]`.
The borderline seeds have bulk ESS 715 and 528 on the same coordinate.

**Passing cells with hidden warmup cost (post-hoc, descriptive only).** Four
chains in four cells ended warmup with a final step below 0.2x their cell's
median. Two of those cells pass: `low_dim_gauss_mix` 461462 (0.014x, warmup
94 % of gradients, 5.2x the model's median gradients) and
`logearn_height_male` 461463 (0.12x). The other two are GLMM_Poisson
cells. In `low_dim_gauss_mix` the chain spent transitions 50–600 at step
1e-3 to 1e-4 before it reached the typical set. The late arrival inflated the
final metric window (installed variance 1.3e4x the retained one on one
coordinate), and the terminal step stayed small. This is the per-chain step
collapse of open question 3, seen outside the funnel at a cost rather than a
gate failure. `hmm_drive_1` 461463 paid a 2.4x warmup cost (100+
warmup depth caps on three chains) and passed.

### Mapping to `wiki/open-questions.md`

| cell(s) | primary reading | open question | new? |
|---|---|---|---|
| GLMM_Poisson x3 | box-constraint corner traps from bounded uniform priors and uniform(-2, 2) starts (three wall-pinned chains, one wandering); one frozen chain | 6 (start rules), 7 (observe-only rescue / `ChainDisagreement` warning would flag every case by energy) | **new mechanism**: not a mode lottery or ODE boundary; the traps are created by the constraint transform |
| seeds_centered x3 | silent funnel: neck-sticking chain on `sigma`, zero divergences | 3 (funnel per-chain behaviour) | **new diagnostic class**: refinement removes the divergence warning |
| kilpisjarvi 461462 | depth cap plus per-chain step collapse on a corr-1.0000 ridge (classifier: multimodality) | 2 (depth cap), 3 (per-chain step collapse) | no |
| kilpisjarvi 461461, 461463 | depth cap (12–13 %), passing | 2 | no |
| grsm 461461 (fail), 461462–3 | slow global coupled to 392 locals (`lambda_adj`) | 5 (global-to-path scale coupling), generalised | extends 5 beyond state space |
| radon_all x3 (borderline) | slow global `beta[1]` coupled to 386 intercepts | 5, generalised | extends 5 |
| kidscore_interaction 461461 (fail), 461463 | correlation-slowed diagonal metric; R-hat lottery at 1.01 | 1 (metric on the slowest coordinate) | no |
| earnings x3 (borderline) | correlation-slowed; one partial per-chain step collapse | 1, 3 | no |
| sblri x2 (borderline) | Stan regularisation floor on variance-1e-6 coordinates | none listed (WP27 mechanism; shared with CmdStan) | not new; not on the open list |
| sat hier_2pl x3 (borderline) | max-of-672 R-hat near 1.008; no sampler signal | none | benchmark-design note |
| low_dim_gauss_mix 461462, logearn_height_male 461463, hmm_drive_1 461463 (passing; post-hoc) | late typical-set arrival contaminates the last metric window; small terminal step; warmup cost | 3 | no |

Classes from the preregistered list that did **not** occur:

- **reference-draw disagreement:** no |z| > 4 anywhere; the largest was 3.28.
- **process error:** 0 of 57.
- **multimodality as a real cause:** `hmm_drive_1` showed no mode lottery,
  and the one multimodality label is the ridge-stuck kilpisjarvi chain.
- **constraint boundary as a stand-alone cause:** the only invalid-evaluation
  cell is the corner-trapped GLMM chain.
- **divergence:** zero retained divergences in all 57 cells.

## Predictions

| prediction | registered | observed | held |
|---|---|---|---|
| P1 reference passes | 32 of 42 (28–36), below 45/51 | **40 / 42**, 95 % > 88 % | **no** (optimistic miss) |
| P2 failing models | kilpisjarvi, hmm_drive_1, logearn_logheight_male, kidscore_interaction, seeds_centered fail; all others 3/3 | kilpisjarvi, kidscore_interaction, seeds_centered failed; hmm_drive_1 and logearn_logheight_male 3/3; GLMM_Poisson and grsm failed unpredicted | **no** |
| P2 mechanisms | kilpisjarvi depth cap; hmm_drive_1 lottery; seeds_centered divergence | kilpisjarvi depth cap (+ step collapse); seeds_centered **no** divergences (silent funnel) | partly |
| P3 gates-only passes | 10 of 15 (7–13) | **8 / 15** | yes |
| P4 passing reference cells \|z\| <= 4 | all | all (max 2.79) | yes |
| P5 no process errors | 57/57 ok | 57/57 ok | yes |
| P6 modal failing-reference mechanism | depth cap | 2 failing cells: multimodality label (the ridge-stuck chain) and unclassified | **no** |

## Prioritised new problems

1. **Corner traps from box-bounded uniform priors** (GLMM_Poisson, 3/3 seeds,
   four of 12 chains, one frozen). This is the most damaging failure seen and
   needs no sampler change to detect. A cross-chain energy check at the end
   of warmup flags every case by more than 200 nats (open questions 6 and
   7). Whether CmdStan suffers the same from Stan's identical starts is
   unmeasured here, since competitor reruns were out of scope.
2. **Silent funnels.** Refinement suppresses the divergence warning on
   centred hierarchical models (seeds_centered, 0 divergences, 0/3). Users
   lose Stan's main reparameterisation signal. A diagnostic that counts
   refined or energy-error-heavy leaves, or that reports a "would-have-
   diverged" rate, is the instrument (open question 3).
3. **Global-to-local coupling outside state space** (grsm `lambda_adj`,
   radon `beta[1]`). Open question 5's mechanism appears in IRT latent
   regression and county-level predictors. It is the lowest-ESS coordinate
   on 6 of 6 cells.
4. **Ridge depth cap and per-chain step collapse** (kilpisjarvi: 12–20 % caps
   on every seed and one stuck chain). This is the open question 2 class at
   three parameters, so it is cheap to study.
5. **Per-chain late typical-set arrival** contaminating the last metric
   window (low_dim_gauss_mix 5.2x warmup cost). This is the cost face of
   open question 3. It leaves the gates intact.

## Recommended v7 breadth candidates (frozen rule in `protocol.json`)

The rule ranks posteriors with a failing or borderline cell: new failure
class first, then open-question rank, then fewest passing seeds, at most one
per family. It selects:

1. `GLMM_Poisson_data-GLMM_Poisson_model` (new class, 0/3);
2. `seeds_data-seeds_centered_model` (new class, 0/3);
3. `kilpisjarvi_mod-kilpisjarvi` (open question 2, 2/3);
4. `science_irt-grsm_latent_reg_irt` (open question 5, 2/3);
5. `radon_all-radon_hierarchical_intercept_centered` (open question 5,
   3/3 borderline).

Three of the five have no posteriordb reference draws. A v7 benchmark would
need its own long reference runs for them, which is a v7 design task and not
done here. `kidscore_interaction` (2/3, unmapped) is the first alternate.

## Caveats and anomalies

- The reference tier is easy by construction of posteriordb's reference set.
  The 95 % figure does not mean the defaults are robust on unseen
  structures, and the gates-only tier is the more informative half.
- The gates-only tier has no reference, so a failing gates-only cell cannot
  be distinguished from a correctly sampled posterior with unusual
  geometry. For GLMM_Poisson and seeds_centered the cross-chain evidence
  (disagreeing chains, stuck chains) is unambiguous.
- The shipped default has no chain rescue (WP36). Whether `restart_from_best`
  would have repaired the GLMM corner traps was not tested.
- Every wall is contended and serialised through the Windows owned worker;
  radon_all cells took 707–1,150 s and sat cells 787–1,519 s. All 57 cells
  finished inside the 2,700 s timeout.
- `sat-hier_2pl` has two constant Cholesky-factor coordinates whose ArviZ
  statistics are undefined. They are listed per cell and ignored by the
  nan-ignoring minima, as in v6.
- `posthoc_descriptive.py` and its artifacts were written after the cells
  were seen. They are descriptive and change no verdict.

## Reproduce

```
uv venv --python 3.11.16 .venv && uv pip install --python .venv/Scripts/python.exe arviz==0.23.4 bridgestan==2.9.0 numpy==2.4.6 posteriordb==0.2.0 scipy==1.17.1 xarray==2026.9.0
git clone https://github.com/stan-dev/posteriordb posteriordb && git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
.venv/Scripts/python.exe -I select_posteriors.py
.venv/Scripts/python.exe -I run_breadth.py prepare
.venv/Scripts/python.exe -I run_breadth.py run
.venv/Scripts/python.exe -I run_breadth.py analyze
.venv/Scripts/python.exe -I posthoc_descriptive.py
```
