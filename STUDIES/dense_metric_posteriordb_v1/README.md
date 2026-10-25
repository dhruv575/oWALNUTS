# WP48 — dense metric on posteriordb (`dense_metric_posteriordb_v1`)

## Verdict

**The shipped `Metric::dense()` is broken and must not be documented as a
setting to use; once its defects are fixed, a dense metric is a large win on
correlated linear-Gaussian posteriors and fixes the `diamonds` depth-cap
problem, but no preregistered `auto` rule separates winners from losers.**

- The literal shipped path (`Metric::dense()` + `Adaptation::default()`)
  could not run a default-length run at all (an admission defect, fixed here),
  and once it ran it passed 17/51 gate cells against the diagonal's 42/51 at
  **0.08x** the diagonal's min-bulk-ESS per gradient (geomean over 17 models).
  Cause: every dense warmup transition reused one RNG stream (finding 4 of the
  preregistration).
- With fresh per-transition seeding (`dense-seeded`, opt-in) the frozen D1
  rule says **supported**: `diamonds` 9.0x, `gp_pois_regr` 4.2x, `accel_gp`
  1.6x per gradient with gates >= diag on all three. The `accel_gp` pass is
  vacuous: both arms pass 0/3 gates.
- With fresh seeding and Stan's regularisation (`dense-stan`, opt-in) the
  geomean is **2.59x** with 42/51 gates (= diag), up to 17x on `mesquite` and
  `nes2000`, but D1 is only *mixed* (`diamonds` 5.3x), because on the three
  target models a numerical defect installs an absolute ridge of 0.01–0.13
  (post-hoc finding 6). A post-hoc diagnostic with that defect fixed gives
  **`diamonds` 65.7x the diagonal per gradient, step 0.28 (diag 0.0033), zero
  depth caps, 0.54x CmdStan `dense_e`**.
- D2 (`d <= 100` and `max|corr| >= 0.6`) has false positives for every dense
  arm, so **no `auto` rule is recommended**. D3 (funnel) passes for
  `dense-seeded` and fails for `dense-stan` (one seed at z = -2.88).

The number that matters: the literal shipped `Metric::dense()` reaches 0.08x
the diagonal's ESS per gradient. Fixed (seeding + Stan regularisation +
symmetrised precision) it reaches 66x on `diamonds`.

## What was tested

Preregistration `PREREGISTRATION.md` and `protocol.json`, frozen and committed
at `f4eb98f5` before the first evidence cell. 17 posteriordb models x 4 arms x 3
seeds (148101–148103), 4 chains x 1,000/1,000, 4 threads, strictly sequential;
CmdStan 2.39.0 `metric=dense_e` on the three target models (3 seeds); Neal's
funnel for the three dense arms; a gradient/kernel cost decomposition.

| arm | what it is |
|---|---|
| `owalnuts-diag` | shipped default (`Metric::diagonal()`) |
| `owalnuts-dense` | `Metric::dense()` literally as shipped (legacy seeding, mean-variance shrinkage), plus the admission fix it needs to run |
| `owalnuts-dense-seeded` | + `DenseWarmupSeeding::PerTransition` (opt-in, new) |
| `owalnuts-dense-stan` | + `DenseMetricRegularization::Stan` (opt-in, new) |

## Defects found in the dense path

| # | defect | status |
|---|---|---|
| 5 | Under the default `Limits::admit_worst_case()` the retained phase re-checked the conservative 113M ceiling, so every `Metric::dense()` run with ~1,000 draws at depth 10 / 8 levels failed with "target-evaluation bound exceeds its resource limit" | fixed (admission only, draws unchanged); regression test in `tests/sampler_api.rs` |
| 4 | Dense warmup seeds each transition `splitmix64(seed ^ t ^ segment)` with `t == segment`: one RNG stream for all 1,000 warmup transitions; warmup is a deterministic map and the window covariances are estimated from it | opt-in `DenseWarmupSeeding::PerTransition`; default unchanged (`Legacy`) |
| 2 | The dense estimator shrinks every variance toward the *mean* variance (`s >= 0.05`) and caps the raw covariance condition at 1e6: not scale-free | opt-in `DenseMetricRegularization::Stan` |
| 6 (post hoc) | The candidate precision is inverted column by column and is not exactly symmetric; above a covariance condition of ~1e4 it fails `DenseMass::from_matrix`'s `64 eps` symmetry check, every retry escalates an absolute ridge, and 0.01–0.13 is installed (`diamonds`, `accel_gp`, `gp_pois_regr` under `dense-stan`; 139–142 failures per `diamonds` cell). Reproduced in Python (asymmetry 6,450 eps on the `diamonds` reference covariance) and by a Rust unit test | opt-in `WarmupConfig::with_dense_symmetrized_precision(true)`, added after the evidence run |

The kernel itself is correct: it runs in `z = L^T q` with an identity metric,
so drift, energy and the `MomentumSum` U-turn are exactly the dense-metric
quantities. `tests/kernel_fingerprint.rs` and every other test pass (241).

## Evidence (seed medians; full table `artifacts/results-table.md`)

Ratios are min-bulk-ESS per gradient against `owalnuts-diag`. Gates are out of 3 cells.

| model | d | diag gates | dense (literal) | dense-seeded | dense-stan | note |
|---|---:|---|---|---|---|---|
| eight_schools_noncentered | 10 | 3 | 0.13 (3) | 0.97 (3) | 0.85 (3) | independent posterior |
| eight_schools_centered | 10 | 0 | 0.07 (0) | 5.78 (0) | 2.40 (0) | funnel; all arms fail R-hat |
| **diamonds** | 26 | 3 | 3.14 (2) | **9.00 (3)** | 5.28 (3) | diag 10 % depth caps, h 0.0035 |
| earnings | 5 | 3 | 0.00 (0) | 0.31 (3) | **5.36 (3)** | scale floor hurts seeded |
| mesquite | 7 | 3 | 1.19 (3) | 7.77 (3) | **16.96 (3)** | |
| kidiq | 4 | 3 | 0.03 (0) | 0.21 (3) | **6.60 (3)** | scale floor hurts seeded |
| sblrc | 6 | 3 | 0.29 (0) | 0.38 (3) | 0.67 (3) | Stan's 1e-5 prior is the variance scale |
| nes2000 | 10 | 3 | 0.44 (2) | 3.20 (3) | **16.73 (3)** | |
| arK | 7 | 3 | 0.80 (3) | 5.01 (3) | **7.58 (3)** | |
| arma11 | 4 | 3 | 0.41 (2) | 0.86 (3) | 1.13 (3) | |
| garch11 | 4 | 3 | 0.00 (1) | 1.48 (3) | 1.45 (3) | |
| **gp_pois_regr** | 13 | 3 | 0.02 (0) | **4.18 (3)** | 2.47 (2) | |
| hmm_example | 4 | 3 | 0.15 (1) | 1.39 (3) | **3.04 (3)** | |
| hmm_drive_0 | 6 | 3 | 0.00 (0) | 0.70 (2) | 0.83 (3) | |
| one_comp | 4 | 1 | 0.12 (0; 1 timeout) | 1.98 (2) | 2.01 (3) | dense-stan 148103 passes with max abs z 4.69 |
| lotka_volterra | 8 | 2 (1 timeout) | 3 errors | 2.38 (1; 1 timeout) | 1.35 (1; 1 timeout) | seed 148101's starts stall every arm |
| **accel_gp** | 66 | 0 | 0.08 (0) | 1.60 (0) | 0.69 (0) | no arm passes |
| **geomean / total** | | **42** | **0.082 / 17** | **1.666 / 41** | **2.591 / 42** | |

Whitened condition number `kappa` (pooled retained covariance in each chain's
installed metric): `diamonds` diag 2.5e5, literal dense 1.1e5, seeded 1.4e3,
stan 1.2e4 (ridge), CmdStan dense_e 17, post-hoc stan-sym 19. Literal dense
has a larger `kappa` than diag on 14/17 models (e.g. 88 versus 2.1 on the
noncentered eight schools).

**CmdStan `dense_e`** (3 seeds): `diamonds` 3/3, 20.6e-3 ESS/grad = 90x CmdStan
`diag_e` (v6) and 109x our diag; `accel_gp` 0/3 with 130–315 divergences per
seed (0.65x CmdStan `diag_e`); `gp_pois_regr` 0/3 (divergences), 1.9e-3.
Our best preregistered arm reaches 0.08x CmdStan `dense_e` on `diamonds`;
the post-hoc stan-sym arm 0.54x.

**Post-hoc diagnostic** (NOT evidence; run after all preregistered cells;
fresh seeds 148201–148203; `artifacts/posthoc/`): diag versus `dense-stan` +
symmetrised precision.

| model | diag gates | stan-sym gates | ratio | step diag -> stan-sym | kappa diag -> stan-sym |
|---|---|---|---:|---|---|
| diamonds | 3 | 3 | **65.7** | 0.0033 -> 0.283 | 2.7e5 -> 19 |
| gp_pois_regr | 2 | 2 | 1.94 | 0.030 -> 0.158 | 555 -> 3.5 |
| accel_gp | 0 | 0 | 1.34 | 0.0086 -> 0.052 | 1.1e3 -> 18 |

With a good dense metric (`kappa` 18) `accel_gp` still fails R-hat and
bulk ESS (1.027, 214): its difficulty is not linear correlation of the
slowest coordinate. This answers open questions 1 and 9 negatively for the
metric lever.

**Funnel** (|MCSE z| <= 2 gate): seeded -0.25, -1.27, -0.09 (pass); stan
-0.75, +1.12, **-2.88** (fail); literal dense: two seeds aborted with a
nonfinite target at transition 0, one z = -3.56. The fixed dense arms show
2–22 retained divergences per funnel cell.

**Cost** (contended micro-benchmarks, minima; `artifacts/overhead/`): sampler
overhead per gradient diag 0.40–0.77 us; dense-seeded/stan add 0.15–0.25 us at
d <= 13, 0.7 us at d = 26 and 2.6–2.8 us at d = 66. BridgeStan gradients cost
2.4 us (eight schools) to 600 us (`one_comp`), so the O(d^2) leapfrog is at most
~10 % of wall here; quiet-machine ESS/s geomeans (cost model) are seeded 1.67x
and stan 2.31x against ESS/gradient 1.67x and 2.59x. Contended walls are in the
table and are labelled.

## Predictions

| prediction | result |
|---|---|
| per-model ratio within 2x of the geometry formula | held 12/17 (seeded), 13/17 (stan); misses: centered eight schools, `gp_pois_regr`, `one_comp`, `lotka_volterra`, `accel_gp`, and stan `diamonds` (ridge defect) |
| literal dense < 1x on >= 12 models, gates <= diag everywhere | **held** (15/17) |
| P1 geomeans: stan >= 2.0, seeded 0.6–1.5, literal <= 0.7 | **failed** (2.59 / 1.67 / 0.08: seeded above range) |
| P2 seeded loses gates on earnings/kidiq/sblrc with worse kappa | **failed** (kappa worse on all three: 2.2e5, 7.6e3, 263 versus 1.2e4, 189, 62; but all 3/3 gates) |
| P3 diamonds: diag caps >= 5 %, h <= 0.006; stan zero caps, h >= 0.05; seeded between | **failed** (diag 10 %, 0.0035 and stan zero caps held; stan h 0.010 because of the ridge; seeded 0.030 not between) |
| P4 D1: literal not supported, seeded mixed, stan mixed (diamonds + accel_gp) | **failed** (literal held; seeded supported; stan diamonds only) |
| P5 no auto rule; sblrc a dense-stan false positive | **held** |
| P6 seeded and stan funnel |z| <= 2 | **failed** (stan seed 148103 -2.88) |
| P7 kernel overhead <= 0.5 us (d <= 10), <= 3 us (d = 66) | **held** |
| P8 CmdStan dense_e >= 20x diag_e on diamonds; stan 0.6–1.2x CmdStan dense_e | **failed** (90x held; 0.05x) |
| P9 stan kappa below diag where reference kappa >= 50 (bar sblrc); literal above on >= 12 | **failed** only on `lotka_volterra` (277 vs 272); literal above on 14 |

## When to use dense (answer to the question)

No `auto` rule: `max|corr| >= 0.6` selects 14 models including losers in every
arm (seeded: `earnings`, `kidiq`, `sblrc`, `lotka_volterra`; stan: `sblrc`,
`gp_pois_regr`, `lotka_volterra`, `accel_gp`), and dimension never binds below
66. A *documentation* rule is supported, conditional on the fixes: dense with
Stan regularisation is the advised metric for near-Gaussian regression and
autoregression posteriors with correlated or collinear coefficients
(`diamonds`, `mesquite`, `nes2000`, `kidiq`, `earnings`, `arK`: 5–66x). It is
not advised for funnels and hierarchical scale problems (eight schools, the
funnel), GP hyperparameter posteriors (`accel_gp`) or ODE models, and on
`sblrc`-like posteriors whose variances are of order 1e-5 Stan's absolute
prior is the binding floor.

## Recommendations

1. Do not advertise `Metric::dense()` until findings 4 and 6 are fixed; the
   admission fix (finding 5) should merge as is.
2. In the `sampler` facade, make `Metric::dense()` use
   `DenseWarmupSeeding::PerTransition`, `DenseMetricRegularization::Stan` and
   symmetrised precision (no fingerprint covers the adaptive dense path; the
   `walnutpie` defaults stay `Legacy`), **after** a preregistered 17-model
   confirmation of that combination (WP48b), which must also re-check the
   funnel (stan arm failed D3 here) and the funnel divergences.
3. Close open question 2 (`diamonds` is a metric problem: dense removes the
   depth cap) and narrow 1/9 (`accel_gp` is not fixed by a good dense metric).

## Deviations and anomalies

- Pre-freeze smoke tests on the non-evidence seed 1 exposed findings 4 and 5
  and led to the `dense-seeded` arm; both are declared in the preregistration.
- Seven cells are not `ok` and were not rerun: `lotka_volterra` seed 148101
  timed out (2,700 s) in diag, dense-seeded and dense-stan (the shared starts
  stall; open question 6), literal dense errored on all three
  `lotka_volterra` seeds ("current position is not evaluable", an ODE NaN),
  and literal dense `one_comp` 148101 timed out.
- The cost-decomposition harness aborted four dimensions when the literal
  dense arm failed on an iid Gaussian; it was made robust per arm and rerun for
  those dimensions only (`artifacts/overhead-log-2.txt`).
- The prediction scoring in `run_dense.py analyze` was added after the run
  phase (it scores frozen claims and decides nothing).
- BridgeStan libraries for 12 models were copied from sibling worktrees'
  completed builds of the same source and flags because compiling under
  contention stalled (`artifacts/library-provenance.json`); 5 were compiled here.
- Walls are contended (about ten agents on 16 cores; a `diamonds` diag cell took
  648–1,119 s against 87 s in v6) and are not used for any decision.

## Reproduce

```powershell
cd STUDIES/dense_metric_posteriordb_v1
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray nutpie==0.16.8 cmdstanpy==1.3.0
git clone --filter=blob:none https://github.com/stan-dev/posteriordb.git posteriordb
git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
cargo +1.88.0-x86_64-pc-windows-gnu build --release
.venv\Scripts\python.exe run_dense.py prepare
.venv\Scripts\python.exe run_dense.py run
.venv\Scripts\python.exe run_dense.py cmdstan
.venv\Scripts\python.exe run_dense.py checks
.venv\Scripts\python.exe run_dense.py overhead
.venv\Scripts\python.exe run_dense.py analyze
.venv\Scripts\python.exe run_dense.py posthoc
.venv\Scripts\python.exe run_dense.py posthoc-analyze
.venv\Scripts\python.exe checksums.py
```

Raw draws (`artifacts/draws/`, `artifacts/posthoc/draws/`) and CmdStan output
are uncommitted and checksummed.
