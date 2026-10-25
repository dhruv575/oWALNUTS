# posteriordb benchmark v7 (WP56): the post-WP51–54 defaults on 17 house + 5 hard posteriors

## Verdict

**Mixed. The defaults at `f097391c` pass the most cells of any arm, 43/51 on
the house set and 6/15 on the five hard posteriors. CmdStan passes 34 + 7 and
nutpie 26 + 3. No passing cell disagrees with the reference draws. But the
preregistered v6 release rule does not pass, so v7 does not replace v5 as the
breadth headline.**

The rule fails for two reasons:

1. **P3 is unevaluable, and the value it would measure is below threshold.**
   The fixed-16 geomean of min-bulk-ESS per gradient against CmdStan is
   **0.708** on the 15 models complete on both sides. The threshold is 0.75.
   The 16th model, `lotka_volterra`, is incomplete because one CmdStan cell
   errored (the ODE step limit). A post-hoc sensitivity check uses CmdStan's
   two good `lotka_volterra` seeds; it gives 0.760 over 16, and it does not
   count.
2. **P4 fails: wall per gradient is 1.85x CmdStan.** We said before running
   that it would. On Windows, every oWALNUTS cell ran with
   `execution = OwnedSerialised` and one effective replica, so all native
   BridgeStan calls go through one thread (WP50C). Walls are also contended
   by sibling agents.

The secondary rule drops P4, but it fails on P3 alone.

**The number that matters: 43/51 house cells, against CmdStan's 34/51, at
0.71x CmdStan's ESS per gradient.** That ratio is lower than v6's 0.848. The
ESS-per-gradient losses concentrate on `accel_gp` (0.35x CmdStan),
`one_comp` (0.50x) and `hmm_drive_0` (0.66x).

| arm | house /51 | new five /15 | all /66 |
|---|---:|---:|---:|
| **oWALNUTS defaults @ `f097391c`** | **43** | **6** | **49** |
| CmdStan 2.39.0 | 34 | 7 | 41 |
| nutpie 0.16.8 | 26 | 3 | 29 |

| oWALNUTS / CmdStan, min bulk ESS per gradient | models | value |
|---|---:|---:|
| fixed 16 (house without `arma11`), P3 | 15 of 16 complete | **0.708** (unevaluable; threshold 0.75) |
| all 22 (reported) | 21 of 22 complete | **0.734** |
| all 17 house (reported) | 16 of 17 | 0.735 |
| wall per gradient, fixed 16 (P4, contended) | 15 | 1.849 |
| bulk ESS/s vs nutpie, house (reported, v6 P5) | 16 | 1.226 |

## What was tested

The commit under test is **`f097391c`**, the head of `main` after the
confirmation wave. Amendment A1 recorded it before any oWALNUTS cell. Against
the 0.2.0 tree (`457119f4`) it carries three default changes:

1. **WP52.** `Init::default()` is now `Init::best_of(16)`: the start is the
   best of 16 uniform(-2, 2) candidates per chain. The starts differ from
   0.2.0; the kernel does not.
2. **WP54.** `Tuning::default()` uses `NonfinitePositionPolicy::RejectLeaf`.
   It fired twice in 66 cells, both times during warmup of
   `hmm_drive_0` 560563, a passing cell. No retained transition was affected.
3. **WP51 follow-up.** The `Metric::dense()` facade now uses PerTransition
   seeding, Stan regularisation and symmetrised precision. This affects only
   the descriptive dense arm.

The diagonal kernel, `ALGORITHM_REVISION` and the fingerprints are unchanged.
Chain rescue stays off (WP36).

The protocol is the v6 protocol: posteriordb `28f8d3d`, 4 chains x
1,000/1,000, fresh seeds 560561–560563 shared by arm, ArviZ 0.23.4 gates
(rank R-hat <= 1.01, bulk and tail ESS >= 400 on every gate parameter, zero
retained divergences), and reference-mean z on the 18 posteriors that have
reference draws. Four of the new five (GLMM_Poisson, seeds_centered, grsm,
radon) have no reference draws. For those, every parameter-block coordinate
is gated and there is no z. The harness sets only the run shape and
`admit_worst_case`; every default comes from the commit and is recorded per
cell.

The study ran in two phases, because the commit was not known at the freeze.
The preregistration (`af2d364d`) froze everything except the oWALNUTS
commit. The CmdStan and nutpie arms then ran (02:44–04:32). Amendment A0
(`06502d19`) extended the hash wait at the coordinator's request, and A1
(`b2a278cc`) fixed `f097391c`. The oWALNUTS arm (06:03–07:24), the funnel row
and the dense arm followed, all strictly sequential with no reruns. Every one
of the 66 oWALNUTS cells completed: no error, no timeout, no frozen chain.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | oWALNUTS >= 42/51 house | **43** | **yes** |
| P2 | no passing oWALNUTS reference cell with max \|z\| > 4 | largest passing 3.82 (`one_comp` 560562) | **yes** |
| P3 | fixed-16 ESS/gradient vs CmdStan >= 0.75 | 0.708 on 15/16 (CmdStan `lotka_volterra` error) | **unevaluable**; value below threshold |
| P4 | fixed-16 wall/gradient vs CmdStan <= 1.0 | 1.849 on 15/16 | **unevaluable / no** (expected to fail) |
| P5 | oWALNUTS >= 6/15 on the new five | **6** (GLMM 0, seeds 0, kilpisjarvi 3, grsm 3, radon 0) | **yes**, at the threshold |
| P6 | `seeds_centered` 0/3 with zero retained divergences | 0/3, divergences 0, 0, 0 | **yes** |
| P7 | CmdStan >= 8/15 on the new five | 7 | **no** |
| P8 | funnel \|z\| <= 2 every seed | +1.69, -0.59, +0.84 | **yes** |

Release rule, primary (v6 verbatim): **not met**. All 153 house cells are
present, and P1, P2 and P8 hold, but P3 is unevaluable and P4 fails.
Secondary (without P4): **not met**, because P3 is unevaluable.

## Per-model gates (house)

| posterior | oWALNUTS | CmdStan | nutpie | oWALNUTS/CmdStan ESS/grad |
|---|---:|---:|---:|---:|
| eight_schools_noncentered | 3/3 | 2/3 | 0/3 | 1.02 |
| eight_schools_centered | 0/3 | 0/3 | 0/3 | 0.18 |
| diamonds | 3/3 | 3/3 | 0/3 | 0.88 |
| earnings logearn_interaction | 3/3 | 3/3 | 2/3 | 0.78 |
| mesquite logmesquite_logvash | 3/3 | 3/3 | 3/3 | 0.96 |
| kidiq kidscore_momhsiq | 3/3 | 3/3 | 3/3 | 0.88 |
| sblrc | 3/3 | 3/3 | 3/3 | 0.81 |
| nes2000 | 3/3 | 3/3 | 3/3 | 0.87 |
| arK | 3/3 | 3/3 | 3/3 | 0.85 |
| arma11 | 3/3 | 2/3 | 2/3 | 1.30 |
| garch11 | 3/3 | 3/3 | 3/3 | 0.96 |
| gp_pois_regr | 3/3 | 0/3 | 0/3 | 0.82 |
| hmm_example | 3/3 | 3/3 | 3/3 | 0.96 |
| hmm_drive_0 | 3/3 | 2/3 | 1/3 | 0.66 |
| one_comp_mm_elim_abs | 1/3 | 0/3 | 0/3 | 0.50 |
| lotka_volterra | 3/3 | 1/3 (+1 error) | crash x3 | (2.18 on 2 seeds) |
| accel_gp | 0/3 | 0/3 | 0/3 | 0.35 |

oWALNUTS fails on three posteriors:

- **centered Eight Schools.** R-hat 1.03–1.08 and bulk ESS 39–200 on `tau`;
  seed 560561 has 5 divergences. Every arm fails this one.
- **`one_comp`.** Two cells fail on tail ESS (394 and 146), and seed 560563
  also has R-hat 1.011.
- **`accel_gp`.** R-hat 1.012–1.031 and tail ESS 49–298, with steps near
  0.008.

Compared with v6, which had different seeds and chain rescue on:

- `accel_gp` falls from 1/3 to 0/3, and its ESS per gradient to 0.42x
  of v6;
- `one_comp` falls from 3/3 to 1/3;
- `hmm_drive_0` stays at 3/3, at 0.69x v6 ESS per gradient;
- `sblrc` rises from 2/3 to 3/3 (v6 lost one cell to a process error);
- `arma11` gains 3.3x.

Excluding `arma11`, the oWALNUTS v7/v6 ESS-per-gradient geomean over the
house models is **0.91**. These differences cannot be attributed to one
change: the seeds differ, rescue was removed in WP36, and the start rule
changed in WP52. WP52 itself measured best-of-16 at 0.862x uniform on its 14
non-lottery models.

## The five hard posteriors (WP46's v7 candidates)

| posterior | tier | oWALNUTS | CmdStan | nutpie | oWALNUTS failure |
|---|---|---:|---:|---:|---|
| GLMM_Poisson | gates-only | 0/3 | 0/3 | 0/3 | slow `sigma`: R-hat 1.05–1.36, bulk ESS 9–65 |
| seeds_centered | gates-only | 0/3 | 0/3 | 0/3 | slow `sigma`: R-hat 1.011–1.035, tail ESS 68–318, **0 divergences** |
| kilpisjarvi | reference | **3/3** | 3/3 | 0/3 | — (about 4.1 M gradients per cell; max \|z\| 1.77) |
| grsm_latent_reg_irt | gates-only | **3/3** | 3/3 | 3/3 | — (WP46: 2/3) |
| radon hier. intercept centered | gates-only | 0/3 | 1/3 | 0/3 | `beta[1]` bulk ESS 251–357; seed 560563 R-hat 1.016 |

Three readings, all descriptive:

- **The WP46 corner traps did not recur.** On GLMM_Poisson, no chain is
  frozen, there are no invalid-evaluation stops, and the cross-chain
  disagreement is 0.20–0.77 sd. WP46 saw wall-pinned chains 270–27,700 nats
  worse. oWALNUTS now fails the way CmdStan and nutpie fail, through slow
  `sigma` mixing. That is consistent with the best-of-16 start rule removing
  the bad starts. With different seeds, this study cannot prove it.
- **The "silent funnel" is a property of the posterior, not of oWALNUTS.**
  P6 held: `seeds_centered` is 0/3 with zero divergences. But CmdStan and
  nutpie also record zero retained divergences on all six of their cells,
  and fail on the same `sigma`. WP46's reading, that refinement suppresses
  the divergence warning, is not supported. At this run length plain NUTS
  gives no divergence signal here either. `chain_warnings` named a chain on
  two of the three oWALNUTS cells.
- **Radon `beta[1]`** sits below 400 bulk ESS for every arm in 8 of 9 cells.
  This is the global-to-local coupling WP46 named. WP46's 3/3 on radon was
  borderline (416–463), and on these seeds it falls just short.

## Funnel (P8)

Neal's 10-D funnel at the defaults, 4 x 2,000 / 20,000, seeds 560571–560573:

| seed | P(omega < -5) | MCSE z | omega bulk ESS / R-hat | divergences |
|---|---:|---:|---|---:|
| 560571 | 0.0646 | +1.69 | 523 / 1.010 | 1 |
| 560572 | 0.0435 | -0.59 | 498 / 1.004 | 0 |
| 560573 | 0.0540 | +0.84 | 569 / 1.005 | 5 |

The pooled batch-means estimate is 0.0540 (z +1.36). The tail mass is
unbiased on every seed. As in v6, per-chain steps spread widely (0.009 to
0.2) and two seeds have a few retained divergences.

## Descriptive dense arm (not a decision arm)

`Metric::dense()` at `f097391c`'s dense defaults (WP51 follow-up) ran on the
six correlated regressions WP48 named, with the same seeds:

| posterior | dense gates | defaults gates | dense / defaults ESS/grad | dense / CmdStan ESS/grad | dense max \|z\| |
|---|---:|---:|---:|---:|---:|
| diamonds | 3/3 | 3/3 | **67.5** | 59.6 | 3.05 |
| earnings | 3/3 | 3/3 | 6.4 | 5.0 | 1.58 |
| mesquite | 3/3 | 3/3 | 15.0 | 14.4 | 1.17 |
| kidiq | 3/3 | 3/3 | 6.6 | 5.8 | 2.25 |
| nes2000 | 3/3 | 3/3 | 16.0 | 13.9 | 1.74 |
| arK | 3/3 | 3/3 | 8.6 | 7.2 | 1.71 |
| **geomean** | **18/18** | 18/18 | **13.4x** | **11.7x** | — |

On these six posteriors, the dense facade passes every cell at 13x the
diagonal default's ESS per gradient. Every z is under 3.1. On `diamonds` it
removes the depth-cap cost: 0.34–0.39 M gradients per cell against about 6.7 M.
This is what an opt-in `Metric::dense()` buys on correlated regressions. It
says nothing about dense as a default: WP51 found it not supported over all
17 posteriors, at 40 vs 43 gates with `gp_pois_regr` going from 3/3 to 0/3.

## Deviations and anomalies

- **Pre-freeze, the funnel seeds were replaced.** A driver smoke test ran the
  funnel at 560561–560563 on `457119f4`, and I saw the results. The funnel
  therefore uses 560571–560573, fixed before the freeze. No posteriordb cell
  ran early. See the PREREGISTRATION.
- **Amendments.** A0 extended the hash wait from 05:32 to 06:45, at the
  coordinator's request. A1 fixed `f097391c`, received at about 06:03. Both
  were committed before any oWALNUTS or funnel cell. A1 also added the
  `nonfinite_position_rejections` counter, which feeds no statistic.
- **CmdStan `lotka_volterra` 560562 errored.** `integrate_ode_rk45` hit
  max_num_steps and cmdstanpy raised. This is what makes P3 and P4
  unevaluable.
- **The nutpie `lotka_volterra` child panicked on seed 560561.** The panic
  was `Failed to constrain the parameters of the draw`, followed by a
  poisoned mutex, so 560562 and 560563 never ran. All three are recorded as
  `timeout_or_crash`, as in v6. None of these failures was rerun.
- **The nutpie libraries were prebuilt** with nutpie's own
  `bridgestan.compile_model(..., STAN_THREADS=true)` call and wrapped in the
  same `CompiledStanModel`. Compile time is excluded from wall, as in v6.
- **Walls are contended.** Up to seven agents shared 16 cores, and oWALNUTS
  ran through the Windows owned worker with one effective replica. The walls
  are in `artifacts/results-table.md` and drive no conclusion except P4.
- **Copied binaries.** The BridgeStan libraries were copied from sibling
  builds of the same posteriordb sources: WP48 for the 17, WP46 for the five.
  So were three CmdStan executables (WP48) and the posteriordb checkout
  (WP46, `28f8d3d`). Raw draws and CmdStan output are uncommitted.

## Recommendation

Change no default because of this study; it decides none. For the project
README:

- cite **43/51 house cells (CmdStan 34, nutpie 26) and 6/15 on the hard five
  (CmdStan 7, nutpie 3), with no passing reference cell above |z| 4**;
- say that the release rule did not pass;
- report ESS per gradient as **about 0.7x CmdStan**, not v6's 0.85x.

The dense facade can be documented as an opt-in for correlated regressions
(13x per gradient on six models, 18/18 gates). The `accel_gp` / `one_comp`
ESS-per-gradient drop against v6 should be investigated with a paired
uniform-vs-best_of(16) run on the same seeds before any further default
work.

## Reproduce

```
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray nutpie==0.16.8 cmdstanpy==1.3.0
# models/ and posteriordb/ copied as described above (posteriordb at 28f8d3d)
.venv/Scripts/python.exe -I prepare_competitors.py 4
.venv/Scripts/python.exe -I run_posteriordb.py run --arms=cmdstan,nutpie
# Phase 2: AMENDMENT-1.json committed; library source == f097391c
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
.venv/Scripts/python.exe -I run_posteriordb.py run --arms=owalnuts
.venv/Scripts/python.exe -I run_posteriordb.py checks
.venv/Scripts/python.exe -I run_posteriordb.py run --arms=owalnuts-dense
.venv/Scripts/python.exe -I run_posteriordb.py analyze
.venv/Scripts/python.exe -I checksums.py
```
