# WP75 `metric_autoselect_v1`: preregistration

Frozen 2026-10-26 and committed before the first evidence cell.
`protocol.json` is the machine-readable copy and takes precedence if the two
disagree.

## Question

Can the sampler choose dense or diagonal per run from a warmup-window
statistic fixed in advance, so that it keeps the dense metric's wins and never
loses a gate the diagonal passes?

**Background (WP48, WP51).** The dense metric, now the `Metric::dense()`
defaults, gives 3.21x the diagonal's geomean ESS per gradient over the 17
house models and 5–99x on the correlated regressions. It still failed as a
default, passing 40 gate cells against the diagonal's 43:

- gp_pois_regr dropped from 3/3 to 0/3. Its absolute bulk and tail ESS fell
  below 400 even though its per-gradient rate was higher.
- accel_gp dropped from 1/3 to 0/3, at 0.38x.
- eight_schools_centered passed 0/3 in both arms.

## What is built

The library commit is `090eaa20` on `wt/metric-autoselect`, on top of main
`94c35314`. It touches `src/walnutpie.rs` and adds `tests/metric_autoselect.rs`.

- **The flag.** `WarmupConfig::with_dense_auto_select(DenseAutoSelectConfig)`
  sits behind `research` and is off by default. It acts only in the dense
  adaptive facade. The diagonal and structured facades reject it.
- **Flag off.** No rendezvous is created and every driver is unchanged.
- **One run-level decision.** At the selection window close the chains meet
  once (this needs threads >= chains). Every chain computes the same decision
  from all chains' windows. It is recorded in `RunTelemetry::dense_auto_select`.
- **Tests** (`tests/metric_autoselect.rs`, plus a Jacobi eigenvalue unit
  test):
  - with the flag off, runs are bit-identical to the dense arm;
  - a correlated Gaussian takes the dense branch, with diagonal installs
    before the switch and dense installs after it;
  - an independent, badly scaled Gaussian takes the diagonal branch and
    recovers the scales;
  - every chain gets the same decision, and runs are deterministic;
  - invalid configurations are rejected: threads < chains, the diagonal
    facade, and a selection window beyond the schedule.
- **Local checks.** The full suite passes with and without `research`
  (including `kernel_fingerprint`), and clippy reports no warnings under
  `-D warnings`.

## Selection statistic, threshold and switch point

**Statistic.** It is computed at the close of slow window 2. Windows 1 and 2
are transitions 100–149 (50 draws per chain) and 150–249 (100 draws per
chain).

- **Pooled covariances.** `S_prev` and `S_cur` are the pooled within-chain
  covariances of windows 1 and 2: 200 and 400 draws over 4 chains.
- **Regularisation.** Stan's dense regularisation is applied to `S_prev`:
  `A = (n/(n+5)) S_prev + 1e-3 (5/(n+5)) I`, with `n = 200`. `D = diag(A)`
  and `A = L L^T`.
- **Two condition numbers.**
  - `kappa_diagonal = cond(D^-1/2 S_cur D^-1/2)`
  - `kappa_dense = cond(L^-1 S_cur L^-T)`

  Each is the ratio of the largest to the smallest eigenvalue.
- **Statistic.** `G = kappa_diagonal / kappa_dense`. It measures how much
  better the previous window's Stan-regularised dense estimate whitens the
  next window than the diagonal estimate does. This is the coordinator's
  "ratio of largest to smallest eigenvalue after Stan regularisation",
  measured out of window for both metrics.

**Threshold: dense iff `G >= 5`.** When either condition number is not
finite, or a pooled count is no more than `d`, the branch is diagonal.

The threshold was fixed from the recorded WP48 and WP51 data:

1. WP48's reference geometry gives `k = kappa_stan_diag_oracle /
   kappa_stan_dense_oracle` per model, the population version of `G`.
2. WP51's cells give the observed dense/diag ESS-per-gradient ratios.
3. A log-log fit over the 14 models that have both, excluding accel_gp where
   the gain did not transfer, gives `ratio = 0.707 k^0.473`.
4. The fitted ratio reaches 1.5 at `k = 4.91`. Keeping accel_gp in the fit
   gives 5.42.
5. The threshold is 5.

No seed from this study was used. WP48 and WP51 recorded no window
covariances, only scale-dependent pivot condition numbers, which do not
separate the models. So the statistic itself could not be computed on
recorded windows.

**Switch point.**

- The decision is made once, after transition 249, before slow window 2's
  metric install, and only during warmup.
- Windows 0 and 1 install the diagonal only.
- Windows 2, 3 and 4 install one family:
  - **dense branch:** the dense facade's Stan dense precision;
  - **diagonal branch:** the diagonal driver's Stan diagonal.
- Retained draws therefore come from one metric family.

The diagonal branch is the dense driver installing diagonal metrics. It is
statistically the diag arm but not bitwise, because the RNG stream layout
and coordinate path differ.

## Predicted branch per model

The predictions come from `artifacts/reference-prediction.json`. It holds
the median `G` over 200 resamples of unconstrained posteriordb reference
draws, with 4x50 previous and 4x100 current draws. Reference draws are
independent, so this is the optimistic case.

| model | reference G median [q10, q90] | predicted |
|---|---|---|
| eight_schools_noncentered | no parameter-block reference | **diag** (judgement: near-independent; WP48 corr. condition 2.0) |
| eight_schools_centered | 6.69 [4.76, 8.91] | **diag** (judgement: funnel warmup windows do not transfer) |
| diamonds | 5,990 | dense |
| earnings | 48.9 | dense |
| mesquite | 241 | dense |
| kidiq | 115 | dense |
| sblrc | 1.03 | diag |
| nes2000 | 167 | dense |
| arK | 61.6 | dense |
| arma11 | 1.14 | diag |
| garch11 | 4.95 [3.99, 6.02] | **diag** (judgement: autocorrelated in-run windows lower G) |
| gp_pois_regr | no parameter-block reference | **dense** (judgement: WP48 corr. condition 540, max abs corr 0.97) |
| hmm_example | 11.1 | dense |
| hmm_drive_0 | 0.98 | diag |
| one_comp | 2.79 | diag |
| lotka_volterra | 126 | dense |
| accel_gp | 44.9 [30.5, 59.7] | dense |

That is 10 dense and 7 diag. **Pa:** at least 45 of the 51 auto runs take
the predicted branch.

## Arms, blocks, seeds

**Arms.**

- `diag`: `Sampler::new()` defaults.
- `dense`: `.metric(Metric::dense())`.
- `auto`: `.metric(Metric::dense())` with `Adaptation::Custom(...)` built from:
  - `WarmupConfig::new(0.8)`
  - `.with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)`
  - `.with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)`
  - `.with_dense_auto_select(DenseAutoSelectConfig::default())`

All three run from one build with `research`, on the WP65 replicated
BridgeStan dispatch (4 replicas, 4 threads).

**Blocks.**

- **P:** 17 house models x 3 seeds (757501–757503) x 3 arms at
  4 x 1,000/1,000, with the v7 gates.
- **F:** funnel, 10 seeds (757401–757410) x 3 arms at 4 x 2,000/20,000.

**Execution.** Cells run strictly sequentially with a 2,700 s timeout and are
never rerun. An errored cell is a failed cell.

## Decision rules (PROPOSE as a default iff all hold)

- **R1.** auto's pass count is at least diag's on the same seeds, out of 51.
- **R2.** The geomean of auto/diag median ESS per gradient is at least 1.5.
- **R3.** No model is worse than 0.9x the diagonal. A model with an errored
  cell counts as failing.
- **R4.** No new divergences: for every model, auto's retained divergences
  summed over its seeds are no more than diag's.
- **F.** On the funnel, `|pooled P5(auto) − 0.0478|` is at most 1 between-seed
  s.e. over 10 seeds. A correct sampler fails this about 32 % of the time;
  that is recorded and the rule is not softened.
- **D.** Flag-off integrity:
  - the library diff from `94c35314` touches only `src/walnutpie.rs` and
    `tests/metric_autoselect.rs`;
  - `kernel_fingerprint` passes with and without `research`;
  - `tests/metric_autoselect.rs` passes.

Either way, the flag stays research-only. Any flip is the coordinator's
decision and is not applied here.

## Predictions

- **Predicted verdict: NOT PROPOSED, failing R1 and R3 (Pb).**
  - auto takes the dense branch on accel_gp, which was 0.38x and went from
    1/3 to 0/3 under dense in WP51. That breaks R3 and R1.
  - auto also takes the dense branch on gp_pois_regr, which went from 3/3 to
    0/3 under dense in WP51. That breaks R1.
- **R2 holds.** The predicted geomean auto/diag is about 2.5–3.
- **R4 holds.**
- **F holds.** The funnel takes the diagonal branch; the local smoke run gave
  G = 0.55.
- **Pc.** The dense arm replicates WP51, with dense/diag geomean >= 2.0.
- **Pd.** The funnel takes the diagonal branch on all 10 auto seeds.

## Machine and discipline

- **Machine.** AWS `owalnuts-bench` lane 3, with every build and cell under
  `taskset -c 8-11`, `RAYON_NUM_THREADS=4` and `OMP_NUM_THREADS=1`. Files
  live under `~/lanes/metric_autoselect_v1/`.
- **Co-tenancy.** Other lanes are active, so walls are "pinned, co-tenanted"
  and are not used in any rule.
- **Disclosed non-evidence runs.**
  - One local funnel smoke run: auto, seed 990675, 1,000/2,000.
  - On the box: the BridgeStan compile, and `run_study.py predict`, which uses
    reference draws only and does no sampling. Both ran before the
    predictions were written.
  - After the freeze, a pipeline check on seed 990675:
    - one kidiq cell per arm;
    - a plain-feature diag cell to compare draws hashes;
    - one funnel cell per arm.

    Its outputs are not committed.
- **Deviations.** Any deviation goes to `AMENDMENTS.md` before it takes
  effect.
