# silent_funnel_diagnostic_v1 (WP55): can existing telemetry warn about a silent funnel?

## Verdict

**Not supported. Nothing ships.** The rule fixed in advance flags a chain
whose retained refined-leaf rate R is above `T_R = 3 x` the negatives'
pooled median (0.00188), so `T_R = 0.00565`. At that threshold the warning
fires on **11 of 39 clean negative cells (specificity 0.718; the rule
needs >= 13/14 = 0.929)**. It catches 8 of 12 wrong positive cells
(sensitivity 0.667; the rule needs >= 0.75). The step-collapse candidate
(C_S) and the union (C_RS) also fail. The refined-leaf rate is high where
refinement is busy: the funnel and centred Eight Schools, but also the
clean `eight_schools_noncentered`, `one_comp_mm_elim_abs` and `garch11`.
It is low on the two positives the study was built around:
`seeds_centered` (cell median 0.0020) and radon centred (0.0012). The
statistic tracks how stiff the geometry is. It does not track whether the
draws are wrong.

The finding that matters more than the negative: **11 of 12 wrong positive
cells had zero retained divergences.** That covers all three funnel cells,
two of three centred Eight Schools cells, and every seeds_centered and radon
cell. WP44's chain warnings fired on 2 of 12. In every one of the 12 cells,
the house R-hat / bulk ESS / tail ESS gates did fail. So on these targets the
lost signal is the divergence count. The convergence diagnostics were not
lost.

| quantity | value |
|---|---|
| cells | 54 / 54 run, 0 process errors; kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` throughout |
| negatives' pooled median R (all 168 chains of the 42 negatives-list cells, as frozen) | 0.00188, so **T_R = 0.00565** |
| negatives' pooled median S | 1.000, so **T_S = 3.000** |
| C_R (R > T_R), cell level | sensitivity **8/12 = 0.667**, specificity **28/39 = 0.718**: fails |
| C_R, model level | sensitivity 3/4, specificity 10/13 = 0.769: fails |
| C_S (S > T_S), cell level | sensitivity 4/12 = 0.333, specificity 37/39 = 0.949: fails |
| C_RS (either), cell level | 0.667 / 0.667: fails |
| WP44 `ChainWarning` alone, cell level | sensitivity 2/12 = 0.167, specificity 38/39 = 0.974 |
| wrong positive cells with 0 retained divergences | **11 / 12** |
| wrong positive cells failing R-hat or ESS gates | **12 / 12** |

The positives are `funnel10`, `eight_schools_centered`, `seeds_centered` and
`radon_all-radon_hierarchical_intercept_centered`. All 12 positive cells
were wrong. The negatives are the 14 house models that pass 3/3 in v6. Of
their 42 cells, 3 were wrong and are excluded as off-diagonal (see below).
Walls are contended (up to six agents on 16 cores, Windows owned BridgeStan
worker) and are not evidence.

## Predictions

| id | prediction | observed | held |
|---|---|---|---|
| P1 | pooled positive-chain median R >= T_R | 0.00584 vs 0.00565 | **held** (by 3 %) |
| P1b | each positive model's median chain R >= T_R | funnel 0.046, centred Eight Schools 0.093; seeds_centered **0.0020**, radon **0.0012** | **failed** |
| P2 | C_R sensitivity >= 3/4 and specificity >= 13/14 | cells 0.667 / 0.718; models 3/4 / 10/13 | **failed** |
| P3 | WP44 warnings alone catch <= 2 of 4 positive models | 1 (seeds_centered, R-hat check on 2 of 3 seeds) | held |
| P4 (mine) | C_R specificity < 13/14, so the rule fails | 0.718 | held |
| P4 (mine), second part | the stuck seeds_centered chain is the highest-R chain on >= 2 of 3 seeds | no chain stuck on these seeds (every chain within 0.17 ref sd); highest-R chain = furthest chain on 0/3 | **failed** (not testable as stated) |
| P5 (mine) | C_S fires on the funnel and not on seeds_centered | funnel 3/3 cells; seeds_centered 0/3 | held |

## What the statistics showed

**Refined-leaf rate (R).** The rate separates the two positives whose
pathology is *local stiffness*. Funnel chain rates were 0.01 to 0.84, and
centred Eight Schools chains reached up to 0.48. Every one of the 6 cells
fired. The cell maximum of the mean refinement level of refined leaves was 2.04
to 3.29 on those six cells. On every negative cell it was <= 1.09.

R does not separate the other two positives:

* **seeds_centered**: the cell maximum of R was 0.0063, 0.0104 and 0.0053.
  Two of three cells fired, and both only barely.
* **radon centred**: the cell maximum was 0.0025 to 0.0033, and no cell
  fired.

Five negative models have chains as high or higher:

* `eight_schools_noncentered`, 0.003 to 0.024; all 3 cells fired;
* `one_comp`, 0.010 to 0.034;
* `garch11`, up to 0.023, firing on 3 of 3;
* `hmm_example`, one chain at 0.0069;
* `lotka_volterra`, one chain at 0.0088.

`arK` and `hmm_drive_0` each have a single chain just above T_R. The
WP34 per-model refined fractions (eight_schools_noncentered 0.009,
one_comp 0.011, garch 0.005) predicted this, and it is why I forecast the
failure (P4).

**Seeds_centered did not reproduce WP46's stuck chain.** WP46 found a chain
with per-chain ESS 6 to 7 and a displaced `sigma` mean. On seeds
731401 to 731403 every chain is within 0.17 reference SD. The cells are
wrong only through the gates: `sigma` bulk ESS 268 to 361, R-hat 1.009 to
1.011, and max |z| <= 2.02. The silent funnel showed up here in its mild
form, slow mixing on `sigma` with no divergence. Its severe form, one chain
sticking in the neck, did not appear. Refinement was not busy in either
form: no chain went above 0.0104.

**Radon centred** is wrong on all three seeds. Max |z| is 3.33, 2.77 and
2.52 (on assorted `alpha[j]`), R-hat reaches 1.032, and bulk ESS on
`beta[1]` is 232 to 389. It records 9 to 11 *warmup* divergences per cell,
zero retained divergences, and almost no refinement. This is WP46's
global-to-local coupling (`beta[1]` against 386 intercepts). It is not a
funnel that refinement is absorbing, so no refinement statistic could see
it.

**Step collapse (S).** The cross-chain end-of-warmup step ratio is 1.00 at
the median on negatives (T_S = 3). It fires on every funnel cell (one chain
at h about 0.02 against about 0.1, open question 3) and on centred Eight
Schools 731403. It does not fire on seeds_centered or radon, whose steps are
equal across chains. It has two false positives: `arma11` 731401 (S 18.4,
the crawling chain that WP44's D1 also names) and `logearn_interaction`
731401 (S 3.7).

**WP44's warnings** fired on 3 of 54 cells:

* seeds_centered 731401 and 731403, through the R-hat check;
* `hmm_drive_0` 731401, the second-mode chain (114 ref SD off,
  off-diagonal, correctly named; that chain also has R = 0.48);
* `arma11` 731401, a step / warmup-density check on a clean cell.

**Post hoc, descriptive and not evidence** (`artifacts/posthoc.md`). The
rank AUC of the cell-maximum R against wrong/clean is 0.78. The best
achievable cut, 0.027, gives sensitivity 0.50 at specificity 1.00. The
mean level of refined leaves (depth given refinement) has AUC 0.84, and its
best cut of 1.034 gives 0.75 / 0.90. Neither reaches the rule even when
tuned on these data. Depth given refinement is the one lead worth a fresh
preregistration. It is still blind to the radon class.

## Off-diagonal cells (excluded from the confusion matrix)

* `hmm_drive_0` 731401: wrong, with the known second-mode lottery (R-hat
  1.20, one chain 114 ref SD off). WP44's D2 and D4 named the chain.
* `one_comp_mm_elim_abs` 731401 and 731403: wrong on tail ESS only (383,
  201), with no bias.

## Recommendation

* Ship nothing. No `ChainWarning` variant is added, the library is
  untouched, and the kernel revision and draws are unchanged by
  construction.
* For the docs: on centred hierarchical models, oWALNUTS can sample a
  funnel **without divergences**. That is 11 of 12 wrong cells here,
  including 2 of 3 centred Eight Schools cells. So "zero divergences" must
  not be read as "no funnel", and the R-hat / ESS gates are the check to
  trust. A sentence to this effect belongs next to the divergence count in
  the Python and Rust docs.
* A future silent-funnel instrument would need fresh preregistered seeds
  and a target set where the severe neck-sticking form occurs, such as
  forced neck starts on seeds_centered. The candidate is the refined-leaf
  *depth* (not rate) or a per-chain `sigma` ESS, not R.

## Design

See `PREREGISTRATION.md` and `protocol.json`, frozen at `e4d65d52`.
Amendment A1 (`980a1577`) moved the three radon cells to the end of the run
order, after the first nine cells and before any other. The reason was that
radon's CmdStan reference was still running. Nothing else changed.

* oWALNUTS at the shipped defaults, the WP44 cell verbatim: 4 x 1,000/1,000,
  `Init::uniform()`, no rescue, four threads, BridgeStan 2.9.0 without
  STAN_THREADS. The funnel used the house 10-D target with starts
  omega in {-3, -1, 1, 3}.
* Seeds 731401 to 731403, run strictly sequentially. Each cell was launched
  once (`artifacts/launches/`).
* References:
  * posteriordb `28f8d3d` for every negative and for centred Eight
    Schools;
  * exact values for the funnel (means 0, P(omega < -5) = 0.0478);
  * seeds_centered and radon, for which posteriordb has no reference draws:
    CmdStan 2.39.0 on the identical posterior written non-centred
    (`reference_models/`), 10 x 1,000 draws thinned from 10,000, adapt_delta
    0.95. Both were accepted. seeds: R-hat 1.0006, min bulk ESS 9,518, 0
    divergences. radon: 1.0014, 8,398, 0 (`artifacts/reference/*.json`).
* Compiled models were copied from sibling builds of the same source:
  15 from `dense-metric/.../dense_metric_posteriordb_v1/models/`, and
  seeds_centered and radon from
  `posteriordb-breadth/.../posteriordb_breadth_v1/models/`.

## Files

* `artifacts/results-table.md`: every cell, with per-chain R, refinement
  depth, end-of-warmup step and S, plus divergences, caps, WP44 checks and
  firing.
* `artifacts/summary.json`: thresholds, confusion matrices for every
  candidate and WP44, predictions, per-model statistics.
* `artifacts/cells/*.json`: per-cell gates, z, per-chain statistics
  including the warmup step trace every 25 transitions.
* `artifacts/posthoc.{md,json}`: post-hoc material, descriptive only.
* `artifacts/reference/`: the two CmdStan reference summaries and their
  logs.
* `artifacts/run-log*.txt`, `artifacts/analyze-log.txt`,
  `artifacts/measured_on.json`.
* `run-log.txt` covers the first launch. It ran the first nine cells and
  stopped before the radon reference existed.

Raw draws (`artifacts/raw/`) and the reference CSVs are ignored.

## Reproduce

```
uv venv --python 3.11.16 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray scipy cmdstanpy==1.3.0
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
MAKE=mingw32-make .venv/Scripts/python compile_refs.py seeds_ncp_reference radon_ncp_reference
.venv/Scripts/python make_reference.py seeds && .venv/Scripts/python make_reference.py radon
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_study.py run
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_study.py analyze
.venv/Scripts/python posthoc.py && .venv/Scripts/python checksums.py
```
