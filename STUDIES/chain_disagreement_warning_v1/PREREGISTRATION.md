# chain_disagreement_warning_v1 — preregistration (WP44)

Frozen 2026-10-24 on `wt/chain-disagreement` before the first evidence cell.
`protocol.json` is the machine-readable copy; where they differ, `protocol.json`
governs.

## Question

`wiki/open-questions.md` item 7: automatic chain rescue is out of the
defaults (WP36). The allowed successor is an **observe-only warning**: at the
end of warmup and again on the retained draws, detect a chain that disagrees
with the others (collapsed step, a different mode, a far-lower log density)
and surface it in `Summary`, the `Posterior` API and the Python summary,
with the draws bit-identical to today. The study question is diagnostic
accuracy: on the 17-model posteriordb screen at the sampler defaults, does
the warning fire on exactly the cells where a chain is actually wrong and
stay silent elsewhere?

## Change under test (implemented before this preregistration, not yet evaluated)

* `walnutpie::ChainWindowSummary` (new) via `RunTelemetry::warmup_end()` —
  per chain, the median and IQR of the selected-state log density over the
  **last slow metric window** (transitions 450..950 at warmup 1,000) and the
  end-of-warmup step — and `RunTelemetry::sampling_end()` (the same over
  the retained transitions). Recording reads values every transition already
  computes; no RNG, no state change.
* `diagnostics::ChainWarning` (new): four checks, the WP33 rescue criteria
  with their thresholds plus `ChainDisagreement`:
  * **D1** end-of-warmup step < 0.1 x median end-of-warmup step over chains;
  * **D2** median over chains of the last-slow-window median log density
    minus the chain's median > 3 x the median over chains of the
    within-chain IQR;
  * **D3** the D2 rule on the retained draws;
  * **D4** `ChainDisagreement` (leave-one-chain-out rank R-hat on the
    unconstrained retained draws) names the chain.
  All need >= 3 chains and windows of >= 10 transitions; non-finite inputs
  skip a check. `Summary::chain_warnings`, `Posterior::chain_warnings()`,
  and the Python `SampleResult.chain_warnings()` / `summary_table()` carry
  them; `Summary` and the Python table print **one line per flagged chain** (format; the numbers are illustrative):

  ```
  warning: chain 3 disagrees with the other chains: end-of-warmup step 4.900e-3 < 0.1 x median step 0.099; last-warmup-window median log density -1.161e4 is 1.142e4 below the chains' median -188.400 (limit 10.500 = 3 x median IQR); retained-draw median log density ...; max R-hat 1.609 falls to 1.003 without this chain
  ```
* Draw neutrality is gated by the existing `tests/kernel_fingerprint.rs` and
  the full suite, and by `tests/chain_warnings.rs`, which checks that the
  warmup window equals the observe-only rescue's last-boundary score
  bit-for-bit and that observed and plain runs have equal draws.

## Protocol

* posteriordb `28f8d3d`, the 17 house-screen posteriors, BridgeStan 2.9.0
  without `STAN_THREADS`, `ReplicatedStanTarget`, four threads.
* One arm, the complete `owalnuts::sampler` defaults (the v5/v6 cell:
  `Init::uniform()` starts, 4 x 1,000 / 1,000, diagonal metric, dual
  averaging 0.8, `DEFAULT_CHAIN_RESCUE = None`). Nothing is configured for
  the checks.
* Seeds: screen 97461, 97462, 97463 (51 cells); extra positives
  `hmm_drive_0` and `lotka_volterra` at 97464–97468 (10 cells). Verified
  unused (see `protocol.json`).
* Order: screen models in listed order x seeds ascending, then the extra
  `hmm_drive_0` then `lotka_volterra` cells; strictly sequential; each cell is
  launched exactly once (create-new launch marker); timeout 2,700 s. Failures
  are results; cells without draws are reported and excluded from the
  confusion matrices.
* Gates (house): ArviZ 0.23.4 rank R-hat <= 1.01, bulk and tail ESS >= 400 on
  every reference parameter, zero retained divergences, finite draws, no
  sampler error.

## Ground truths

* **T_gate** (task-literal): any gate fails, or a pooled reference-parameter
  mean is > 3 reference SD from the posteriordb reference mean.
* **T_wrong** (a chain is actually wrong): some chain's mean of some
  reference parameter is > 3 reference SD from the reference mean. The set of
  such chains is the chain-level truth.
* **T_rhat** (reported only): R-hat gate fails or T_wrong.

T_gate counts ESS-only and divergence-only failures (centered Eight Schools,
`accel_gp`, `one_comp`) in which no chain disagrees; no chain-disagreement
detector is designed to catch them, which is why T_wrong is preregistered
beside it.

## Decision rule (frozen)

Thresholds (from the task): specificity >= 0.9 on truth-negative cells and
sensitivity >= 0.8 on truth-positive cells, over all process-valid cells
(screen + extra; screen-only reported).

Candidates, in this order: C1 = D1+D2+D3+D4 (any fires), C2 = D1+D3+D4, C3 =
D3+D4, C4 = D1+D2 (warmup end only), C5 = D4.

1. **Rule A** (T_gate): the first candidate meeting both thresholds ships as
   a validated gate-failure detector.
2. Otherwise **Rule B** (T_wrong): the first candidate meeting both
   thresholds ships as the chain-disagreement warning, documented as
   covering one-wrong-chain failures only and not a substitute for the
   R-hat / ESS gates.
3. Otherwise no warning line ships: `ChainWindowSummary` and `ChainWarning`
   remain as draw-neutral data, `Summary` / Python print no new line, and the
   existing `ChainDisagreement` line is unchanged.

The shipped candidate's detectors are exactly the ones `ChainWarning::detect`
emits; any detector outside it is removed. An exploratory sweep (step ratio
0.05/0.1/0.2, 2/3/5/10 IQRs, per phase) is reported and cannot ship or move
the decision.

## Predictions (numeric, before any cell)

Prior evidence used: v5 (no-rescue defaults, 42/51; failures centered Eight
Schools 3, `accel_gp` 3, `one_comp` 2, `hmm_drive_0` 1), WP33 `da` and WP36
`observe` (draw-identical to defaults): frozen `lotka_volterra` about 4/18
seeds, `arma11` crawl about 4/18, retained `hmm_drive_0` second mode about
2/18; at WP36's last boundary the density rule fired on two passing
`hmm_drive_0` cells (warmup transients) and the step rule on passing `arma11`
cells.

| id | statement | point | interval |
|---|---|---:|---|
| P1 | C1 sensitivity vs T_gate (fails rule A) | 0.35 | 0.15–0.60 |
| P2 | C1 specificity vs T_gate | 0.96 | 0.90–1.00 |
| P3 | C1 sensitivity vs T_wrong | 0.95 | 0.75–1.00 |
| P4 | C1 specificity vs T_wrong | 0.94 | 0.88–1.00 |
| P5 | D3 specificity vs T_wrong | 0.99 | 0.97–1.00 |
| P6 | D4 specificity vs T_gate | 1.00 | 0.98–1.00 |
| P7 | no candidate meets rule A; C1 meets rule B and ships | — | — |
| P8 | Rust `ChainWarning` equals the Python recomputation on every valid cell | — | — |
| P9 | fingerprint tests and the full suite pass (draws bit-identical) | — | — |

Expected counts behind P1–P4: about 12 T_gate positives of 61 (about 4–5
catchable), about 3–4 T_wrong positives, 1–3 warmup-end false positives
(`hmm_drive_0` transients, `arma11` slow step), and D4 hits on R-hat-failing
cells without a wrong chain (centered Eight Schools) counting against
T_wrong specificity.

## Reporting

Every cell in `artifacts/results-table.md`; sensitivity, specificity and the
false-positive list by model for each detector, each candidate and each phase
(warmup end = D1+D2; sampling end = D1+D3+D4), screen-only and all cells;
chain-level agreement; the printed warning lines; contended walls labelled as
such.
