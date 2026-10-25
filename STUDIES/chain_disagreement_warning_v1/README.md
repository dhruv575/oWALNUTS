# chain_disagreement_warning_v1 — observe-only chain-disagreement warning (WP44)

Status: preregistered diagnostic-accuracy study (`PREREGISTRATION.md`,
`protocol.json`, frozen at `4689bef9` together with the implementation and
before the first evidence cell). 61 cells launched exactly once 2026-10-24
17:47–20:53 local on `wt/chain-disagreement`, strictly sequential, on a
16-core machine shared with nine other agents (walls are contended). Kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`, unchanged. Per-cell
JSON: `artifacts/cells/`; every table: `artifacts/results-table.md`;
machine-readable: `artifacts/summary.json`; hashes: `CHECKSUMS.sha256`.

## Verdict

**Mixed: the preregistered rule ships candidate C1 (all four checks) as the
chain-disagreement warning under Rule B, but only specificity is well
measured.** Under the task-literal truth (any gate failure), C1's
sensitivity is 0.30 (3/10) and Rule A fails, as predicted. Under the
"a chain is actually wrong" truth (some chain's mean of some reference
parameter > 3 reference SD off), C1's specificity is **0.966 (57/59)** and
its sensitivity is 1/1. There was one wrong-chain cell in 60 valid cells,
so the sensitivity has no precision (95% interval 0.03–1). The run would
have had a second positive, a frozen `lotka_volterra` chain on seed 97464,
but that cell hit the 2,700 s cell timeout and produced no draws.

The one number: **zero false positives from the three telemetry checks
(D1–D3) in 60 cells**. Every false positive (2) comes from the
leave-one-chain-out R-hat (D4) on cells whose R-hat is barely above 1.01
(1.013, 1.014). On healthy chains the density gap peaked at 0.29 IQRs
against a 3-IQR limit, and the lowest step ratio was 0.28 against a 0.1
limit. The wrong chain was at 59 IQRs.

## What ships (unchanged since the frozen implementation)

* `walnutpie::ChainWindowSummary` via `RunTelemetry::warmup_end()` (last
  slow warmup window: median and IQR of the selected-state log density, plus
  the end-of-warmup step) and `RunTelemetry::sampling_end()` (the same over
  the retained draws). These are draw-neutral: the fingerprint tests and the
  full suite pass, and `tests/chain_warnings.rs` checks that the warmup
  window equals the observe-only rescue's last-boundary score bit for bit.
* `diagnostics::ChainWarning` with variants `WarmupStep`,
  `WarmupLogDensity`, `SampledLogDensity` and `RHat`.
  `ChainWarning::from_chains`, `ChainWarning::detect` and
  `ChainWarning::lines` produce them; they are carried in
  `Summary::chain_warnings` and returned by `Posterior::chain_warnings()`.
  Python exposes `SampleResult.chain_warnings()` (structured dicts), each
  chain dict's `warmup_end` / `sampling_end`, and the warning lines in
  `summary_table()` / `print(result)`.
* Warning text, one line per flagged chain, as printed on
  `lotka_volterra`/97467:

  ```
  warning: chain 3 disagrees with the other chains: last-warmup-window median log density -297.837 is 160.690 below the chains' median -137.146 (limit 8.147 = 3 x median IQR); max R-hat 1.221 falls to 1.004 without this chain
  ```

  The other finding forms are `end-of-warmup step <s> < 0.1 x median step
  <m>` and `retained-draw median log density <x> is <gap> below the chains'
  median <ref> (limit <t> = 3 x median IQR)`.

## Detectors and truths

The detectors use the frozen WP33 thresholds, need at least 3 chains and at
least 10 transitions per window, and skip any check whose inputs are not
finite.

* D1: the end-of-warmup step is below 0.1 x the median step.
* D2: the chain's median log density over the last slow window (450..950) is
  more than 3 x the median within-chain IQR below the chains' median.
* D3: the D2 rule applied to the retained draws.
* D4: `ChainDisagreement` on the unconstrained draws names the chain.

Candidates: C1 = D1–D4, C2 = D1+D3+D4, C3 = D3+D4, C4 = D1+D2,
C5 = D4.

Truths:

* T_gate: any house gate fails, or a pooled mean is > 3 ref SD off.
* T_wrong: some chain's mean is > 3 ref SD off.
* T_rhat: the R-hat gate fails, or T_wrong.

## Evidence (all 60 process-valid cells; screen-only is in the table file)

| truth | set | TP | FN | FP | TN | sensitivity | specificity | false positives |
|---|---|---:|---:|---:|---:|---:|---:|---|
| T_gate | C1 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | — |
| T_gate | D4 | 3 | 7 | 0 | 50 | 0.300 | 1.000 | — |
| T_gate | C4 (warmup end) | 1 | 9 | 0 | 50 | 0.100 | 1.000 | — |
| T_wrong | C1 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | centered Eight Schools 97461, `one_comp` 97461 (both D4) |
| T_wrong | D1 | 0 | 1 | 0 | 59 | 0.000 | 1.000 | — |
| T_wrong | D2 | 1 | 0 | 0 | 59 | 1.000 | 1.000 | — |
| T_wrong | D3 | 0 | 1 | 0 | 59 | 0.000 | 1.000 | — |
| T_wrong | D4 | 1 | 0 | 2 | 57 | 1.000 | 0.966 | as C1 |
| T_rhat | C1 | 3 | 5 | 0 | 52 | 0.375 | 1.000 | — |

Phase view, scored against T_wrong:

* Warmup end (D1+D2): sensitivity 1/1, specificity 1.000.
* Sampling end (D1+D3+D4): sensitivity 1/1, specificity 0.966.

False positives by model (T_wrong, C1): `eight_schools_centered` 1/3 and
`one_comp_mm_elim_abs` 1/3. Every other model has 0. Both cells have R-hat
just above 1.01 (1.013, 1.014), and leaving out one chain takes it to
1.006 and 1.005. The named chain is not off the reference: its largest
per-chain shift is 0.17 and 0.48 reference SD.

T_gate false negatives (C1), 7 in all: centered Eight Schools 97462/97463
(R-hat 1.08 and 1.10, divergences, no single chain responsible),
`one_comp` 97462/97463 (tail ESS only) and `accel_gp` x3 (R-hat about 1.06
and ESS, all chains alike). No chain-disagreement detector is designed for
these, and the R-hat/ESS gates already report them.

The one positive is `lotka_volterra` 97467, chain 3. At the end of warmup
it sat at median log density −297.8 against −137.1, a gap of 59 IQRs,
with a step of 0.0113 (0.114 x median, just above the 0.1 step limit). It
recorded 316 retained refinement exhaustions and left the bad region during
sampling. Its retained median recovered to −139.6 with an IQR of 156, so
**D3 missed it**. Its per-chain mean is 114 reference SD off and the cell
R-hat is 1.221. D2 (warmup end) and D4 (draws) named it. The chain named
is the wrong chain, and no other chain was named.

Exploratory sweep (reported only; it cannot ship): every warmup-phase
combination of step ratio 0.05–0.2 and 2–10 IQRs has T_wrong specificity
1.000 and catches the positive through D2. The retained-draw density rule
alone never catches it at any threshold tested.

## Predictions

| id | prediction | observed | result |
|---|---|---|---|
| P1 | C1 sensitivity vs T_gate 0.35 [0.15, 0.60] | 0.300 | held |
| P2 | C1 specificity vs T_gate 0.96 [0.90, 1] | 1.000 | held |
| P3 | C1 sensitivity vs T_wrong 0.95 [0.75, 1] | 1.000 (n = 1) | held, uninformative |
| P4 | C1 specificity vs T_wrong 0.94 [0.88, 1] | 0.966 | held |
| P5 | D3 specificity vs T_wrong 0.99 [0.97, 1] | 1.000 | held |
| P6 | D4 specificity vs T_gate 1.00 [0.98, 1] | 1.000 | held |
| P7 | no Rule A pass; C1 ships under Rule B | as predicted | held |
| P8 | Rust `ChainWarning` equals the Python recomputation on every valid cell | 60/60 | held |
| P9 | draws bit-identical (fingerprints and full suite) | all pass | held |

Two parts of the reasoning behind the predictions failed:

* **Positive count.** I expected 3–4 T_wrong positives (one-bad-chain rates
  from v5/WP33/WP36) and observed 1, plus 1 lost to the timeout. Over
  these 8 seeds no `arma11` chain crawled, `hmm_drive_0` never kept its
  second mode (0/8), and `lotka_volterra` froze 2 times in 8.
* **Warmup-end false positives.** I expected 1–3 (the WP36 `hmm_drive_0`
  transients and `arma11` slow steps) and observed 0.

## Caveats

* **Sensitivity is not measured.** One positive cannot tell 0.8 from 0.2.
  The decision rule (≥ 0.8 sensitivity) is met formally because 1/1 ≥ 0.8.
  I report this as a rule pass on a degenerate denominator, not as evidence
  that the warning catches wrong chains reliably. A powered sensitivity
  estimate needs targeted positives, for example forced bad starts on
  `lotka_volterra` and `arma11` or the WP33 trap target.
* **The timed-out cell (`lotka_volterra` 97464, 45 min contended)** was
  almost certainly a frozen chain (the WP24/WP33 signature). A frozen chain
  costs 25 minutes even on an uncontended machine, which is exactly when
  an end-of-warmup warning would help most. The check is printed after the
  run, though; streaming it to a progress callback is a separate change.
* **D4 is noisy at R-hat ≈ 1.01.** It names a "culprit" whenever removing
  one chain crosses the threshold, including on chains that are fine.
  Both D4 false positives are of this kind. The line therefore says
  "disagrees", not "is wrong", and the docs say so.
* The R-hat in D4 is computed on unconstrained draws, as users get it. The
  gate uses constrained reference parameters with ArviZ. The two maxima
  differ by at most 0.0013 and fall on the same side of 1.01 in every cell.
* Walls are contended. The 60 cells took 139 min of sampler wall and 47.6 M
  gradients.

## Deviations

* None to protocol. `prepare` was restarted once to compile in parallel
  (three BridgeStan builds at a time) before any cell ran. No evidence cell
  was affected or rerun.
* The Python test added with the implementation used 300 draws. On its
  Gaussian control, D4 fired on an R-hat of 1.011, the same noise mechanism
  as the two study false positives. The test now uses 1,000 draws
  (`d0556ada`). This was a test fix, not evidence.

## Reproduce

```
cd STUDIES/chain_disagreement_warning_v1
uv venv --python 3.11.16 .venv && VIRTUAL_ENV=$PWD/.venv uv pip install bridgestan==2.9.0 arviz==0.23.4 posteriordb numpy pandas xarray scipy
git clone --filter=blob:none https://github.com/stan-dev/posteriordb && (cd posteriordb && git checkout 28f8d3d)
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
MAKE=mingw32-make PYTHONIOENCODING=utf-8 .venv/Scripts/python run_study.py prepare
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_study.py run       # 61 cells, launch markers forbid relaunch
PYTHONIOENCODING=utf-8 .venv/Scripts/python run_study.py analyze
.venv/Scripts/python checksums.py
```
