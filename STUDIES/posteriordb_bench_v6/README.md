# posteriordb benchmark v6 — the current defaults pass 45/51 cells, but the preregistered release rule does not pass (WP35)

Status: preregistered validation committed at `7004b2f` before the first
evidence cell; executed 2026-09-04 on source commit `aa4510f`. All 153
posteriordb cell records and all three funnel cells are present. The fixed
protocol, predictions and release rule are in `PREREGISTRATION.md` and
`protocol.json`; full tables are in `artifacts/results-table.md`.

## Question

`posteriordb_bench_v5` validated the momentum-sum U-turn rule and Stan metric
regularisation, but WP33 subsequently made restart-from-best chain rescue the
default for multi-chain identity and diagonal runs. This study repeats v5 on
fresh seeds 90101–90103 against rerun CmdStan 2.39.0 and nutpie 0.16.8,
records every rescue, and asks whether the result can replace v5 as the 0.2.0
breadth headline.

## Verdict

**The current default passes 45/51 cells, against CmdStan's 34 and nutpie's
29, but the preregistered release rule does not pass.** Three gates improve
over v5's 42/51, there is no frozen oWALNUTS chain, and the funnel tail-mass
check is within |z| <= 2 on every seed. The rule nevertheless fails for two
independent reasons:

1. One passing `one_comp_mm_elim_abs` cell has max |z| **4.023** against the
   reference draws (seed 90103, parameters `V_m` -4.023 and `K_m` -4.008).
   No rescue fired in this cell, and the mean shifts are only 0.080 and 0.078
   reference standard deviations, so this is not evidence that rescue moved a
   mode; it still fails the frozen P2 threshold.
2. The `sblrc` oWALNUTS subprocess for seed 90101 exited without stderr or a
   raw result. It is an error cell and was not rerun. Consequently P3 and P4,
   which require all fixed 16 non-`arma11` models, are unevaluable: on the 15
   complete models the observed values are **0.848x CmdStan per gradient**
   (threshold 0.75) and **0.825x wall per gradient** (threshold 1.0).

P5, which was reported but not a release gate, also fails: oWALNUTS is
**0.996x nutpie ESS/s** over the 15 models complete on both sides. Wall
comparisons were made on a shared machine and changed much more than gradient
counts; the machine-independent oWALNUTS v6/v5 ESS-per-gradient geomean is
**1.075x**, with no model below 0.8x v5 among the 16 complete models.

The v5 headline therefore remains the last run admitted by its own release
rule. WP35 must be reported beside it as the full-current-default result; it
must not be rewritten as a successful confirmation.

## Headline

| arm | gates /51 | models 3/3 | bulk ESS/gradient vs CmdStan | bulk ESS/s vs CmdStan | wall/gradient vs CmdStan |
|---|---:|---:|---:|---:|---:|
| owalnuts-da, current defaults | **45** | **14** | 1.462 over 16 complete models; **0.848 over 15/16 fixed non-`arma11` models** | 1.865 | **0.825 on the fixed set** |
| CmdStan 2.39.0 | 34 | 10 | 1 | 1 | 1 |
| nutpie 0.16.8 | 29 | 8 | — | — | — |

The all-model 1.462x ratio is dominated by `arma11`: CmdStan again carries
stuck chains there. On the fixed ordinary-model set, the available 0.848x is
the relevant per-gradient picture and is consistent with v5/WP34.

Gate changes from v5 for oWALNUTS:

- `hmm_drive_0`: 2/3 -> **3/3**;
- `one_comp_mm_elim_abs`: 1/3 -> **3/3**;
- `accel_gp`: 0/3 -> **1/3**;
- `sblrc`: 3/3 -> **2/3** solely because seed 90101 is the process-error
  cell.

`arma11`, `lotka_volterra`, noncentered Eight Schools and `gp_pois_regr` are
3/3. Centered Eight Schools remains 0/3. CmdStan falls from 36 to 34 cells
and nutpie rises from 28 to 29 on their fresh seeds, illustrating the seed
noise that prevents attributing every v5/v6 difference to rescue.

## What chain rescue did

There are **30 restarts in 21 posteriordb cells across nine models**:
21 log-density and nine step-rule events. Twenty-six occur at transition 99,
two at 149, and two at 249. The complete event table, including source chain
and before/after step, is in `artifacts/results-table.md`.

- `arma11`: five restarts, including steps of 1e-38 to 1e-17; all three cells
  pass with no frozen chain.
- `lotka_volterra`: five restarts; all cells pass. Seed 90103's step-rule
  rescue escapes a poor chain but the cell still costs 176.6 seconds.
- `hmm_drive_0`: one log-density restart on every seed; all three cells pass.
  This is the intended robustness effect and the exact mode-hiding caveat:
  R-hat no longer carries the chain's original mode, so the rescue telemetry
  is part of the result.
- `kidiq`, `earnings`, `diamonds`, `sblrc` and `accel_gp`: 16 restarts,
  mostly log-density events on chains still moving during the first window.
  Two step rescues occur as late as transition 249 (`kidiq`, `earnings`).
  The broader run therefore confirms WP33's concern that a first-boundary
  density score fires on merely late chains, and shows that late step
  outliers also exist.

No restart fires on noncentered Eight Schools, `mesquite`, `nes2000`, `arK`,
`garch11`, `gp_pois_regr`, `hmm_example` or `one_comp`; their v6/v5
differences are seed noise and machine timing, not rescue.

## Funnel

At the complete sampler defaults:

| seed | P(omega < -5) | MCSE z | omega bulk ESS / R-hat | divergences | rescues |
|---|---:|---:|---|---:|---:|
| 90101 | 0.0373 | -1.04 | 388 / 1.003 | 0 | 3 |
| 90102 | 0.0498 | +0.25 | 539 / 1.009 | 0 | 1 |
| 90103 | 0.0671 | +1.69 | 356 / 1.004 | 2 | 0 |

P6 holds: every tail-mass |z| is below 2. The pooled batch-means estimate is
0.0514 (z +0.68). The defaults remain unbiased but not reliably efficient:
two seeds have omega bulk ESS below 400 and seed 90103 has two retained
divergences. This agrees with the existing README qualification that eight
levels fix the tail mass without fixing per-chain mixing.

## Preregistered predictions

| prediction | result | held |
|---|---|---|
| P1: oWALNUTS gates >= 42/51 | **45** | yes |
| P2: no passing oWALNUTS cell max \|z\| > 4 | `one_comp` 90103 = **4.023** | **no** |
| P3: fixed-16 ESS/gradient vs CmdStan >= 0.75 | 0.848 on 15; `sblrc` missing | unevaluable |
| P4: fixed-16 wall/gradient vs CmdStan <= 1.0 | 0.825 on 15; `sblrc` missing | unevaluable |
| P5: ESS/s vs nutpie >= 1.5 | **0.996** | no (reported, not release gate) |
| P6: funnel \|z\| <= 2 every seed | -1.04, +0.25, +1.69 | yes |
| P7: no frozen oWALNUTS chain | none | yes |

## Deviations and failures

- `sblrc` / oWALNUTS / 90101: the child process exited nonzero with no
  stderr and no raw JSON. The driver recorded an error cell. It was not rerun,
  per the rule that sampler failures are results.
- `lotka_volterra` / nutpie: seed 90101 completed and failed its divergence
  gate; the child then exited before writing 90102 or 90103. Both are
  `timeout_or_crash` cells and were not rerun. nutpie process failures on this
  model also occurred in earlier benchmark versions.
- The run compiled every model in this worktree before its first use; compile
  time is excluded from sampler wall time. The machine was shared, so wall and
  ESS/s are reported but gradient-normalised quantities drive interpretation.

## Next decision

1. Do not replace the release headline under this study's rule and do not
   rerun failed cells post hoc.
2. Preregister a paired chain-rescue refinement study: current rule versus a
   second-window or two-consecutive-boundary score, with a no-rescue control.
   The primary safety rows are `hmm_drive_0`, `kidiq`, `earnings`, `diamonds`
   and the funnel; reference z and the original-mode telemetry are gates.
3. Treat the `sblrc` subprocess exit as a separate reproducibility defect.
   Diagnose it with non-evidence seeds or a synthetic load/unload stress test
   before another breadth run.
4. The `delta` / reverse-coarsening line remains the next kernel-efficiency
   investigation, but it should not be mixed into the rescue-safety decision.

## Reproduce

```powershell
cd STUDIES/posteriordb_bench_v6
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray nutpie==0.16.8 cmdstanpy==1.3.0
git clone --filter=blob:none https://github.com/stan-dev/posteriordb.git posteriordb
git -C posteriordb checkout 28f8d3d6e975315f42aa274a8399f21e07a43b30
cargo +1.88.0-x86_64-pc-windows-gnu build --release --locked
.venv\Scripts\python.exe run_posteriordb.py run
.venv\Scripts\python.exe run_posteriordb.py checks
.venv\Scripts\python.exe run_posteriordb.py analyze
.venv\Scripts\python.exe checksums.py
```

Raw `artifacts/draws/*.npz` and CmdStan outputs are checksummed or reproducible
but uncommitted; cell metrics, logs, summary and tables are committed.
