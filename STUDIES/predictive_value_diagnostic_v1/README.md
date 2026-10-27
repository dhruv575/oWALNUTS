# Retrospective predictive value diagnostic

The current SV posterior has higher mean predictive log score than the established
NIG AR1 comparator on both inspected streams. Its advantage over the rolling t5
and EWMA t5 controls is much smaller, and every predeclared block-bootstrap
interval for those two comparisons includes zero. K200 warm inference closely
preserves the reference forecast scores and PITs on this panel. These results
support approximation fidelity; they do not establish a general predictive
advantage over strong cheap controls, independent market generalization, trading
profitability, or an AMM deployment decision.

This is an **amended, recovered analysis**. The original frozen full run failed
after 121/200 origins because Windows denied replacing a progress file. Its
separate summary retains 61 simulated and 60 real origins, 847 available forecasts
and 553 missing forecasts; full-panel means remain null. The separately reviewed
recovery computed exactly the remaining 79 origins, with no replacement sampling,
score-based continuation, changes to numerical formulas, or repeated completed
origins. Both attempts and their provenance remain in the evidence archive.

## Fixed panel and numerical accounting

Each stream contributes 100 next-return outcomes, ticks1..100. At tick t the
posterior sees y[:250+t] and scores y[250+t]. The full joint reference and three
separate K200 warm seeds are compared with all three frozen causal baselines.
No pooling, thinning, seed-density mixture or quantile inversion was used.
These are unpooled H1 K200 forecasts, not WP97's reweighted H10/H20 forecasts;
the return-distribution accuracy findings do not transfer to those pooled forecasts.

The recovered panel has 200/200 origins and 1400/1400 valid forecasts. All800
posterior forecasts meet the original GH64/128 log-density and PIT tolerances:
maximum absolute differences are 3.55e-15 nats and 4.44e-16. There are zero
baseline scale-floor hits and zero ineligible rolling-MLE starts. No numerical
missing cases or reference/seed/origin replacements occurred.

Chain-aware descriptive MCSEs retain chain/draw axes. Reference log-score MCSE
has median0.000593 and maximum0.007387 nats; warm has median0.005880 and
maximum0.102016. Reference PIT MCSE median/max is0.000128/0.000285; warm is
0.001309/0.002463. Short-chain estimates are diagnostics, not validated precision
guarantees or stopping criteria. Tiny quadrature differences do not eliminate
posterior Monte Carlo error or model error.

## All baseline comparisons

Higher log score is better. Units are nats per native log-return observation;
absolute density scores across the two streams are not directly comparable.
The intervals below are the fixed circular-block bootstrap 2.5/97.5 percentiles
(2000 replicates, paired origin vectors). They are descriptive sensitivity
intervals, not significance tests or qualification gates.

| Stream | Reference minus baseline | Mean | Block5 | Block10 | Block20 |
|---|---|---:|---|---|---|
| Sim | NIG AR1 | +0.071420 | [0.007254,0.138815] | [0.007426,0.135834] | [0.007043,0.145280] |
| Sim | Rolling t5 | +0.006122 | [-0.023914,0.041683] | [-0.024884,0.040341] | [-0.025392,0.045740] |
| Sim | EWMA t5 | +0.010173 | [-0.020600,0.050304] | [-0.020345,0.050812] | [-0.024871,0.056954] |
| Real | NIG AR1 | +0.221598 | [0.053881,0.494900] | [0.062057,0.460359] | [0.068598,0.451214] |
| Real | Rolling t5 | +0.004646 | [-0.039182,0.062188] | [-0.038054,0.056428] | [-0.037360,0.047676] |
| Real | EWMA t5 | +0.033357 | [-0.007243,0.079844] | [-0.007735,0.087808] | [-0.008647,0.090181] |

The reference mean log scores are3.682824(sim) and4.478504(real). Every baseline
and seed comparison, cumulative paired score and ten-origin block mean appears in
`artifacts/recovered-amended-summary.json`; no comparator or block length was
selected after observing results.

The practical case for paying the extra inference cost is therefore still weak:
the simpler rolling/EWMA t5 controls capture most of the observed score gain over
NIG. This study did not measure comparable baseline-versus-SV end-to-end latency,
so it cannot quantify a cost-adjusted advantage. Sampling, state maintenance and
integration costs must be justified by stronger incremental predictive evidence
before treating the heavier model as necessary.

## Warm approximation impact

| Stream/seed | Mean warm minus reference log score | Mean absolute log-score difference | Mean absolute PIT difference |
|---|---:|---:|---:|
| Sim971201 | -0.000538 | 0.004686 | 0.000919 |
| Sim971202 | +0.000909 | 0.005163 | 0.000971 |
| Sim971203 | +0.000249 | 0.004806 | 0.001116 |
| Real971301 | -0.001435 | 0.007699 | 0.001054 |
| Real971302 | +0.000137 | 0.007089 | 0.001067 |
| Real971303 | -0.001250 | 0.005785 | 0.000914 |

The exact decomposition is warm-minus-baseline = reference-minus-baseline plus
warm-minus-reference. A positive realized warm-reference score difference does
not indicate a better posterior. Three sampler seeds reuse the same outcomes;
they are not three independent forecast replications. All seed-specific paired
intervals, including intervals that exclude zero for some block choices, remain
in the fixed summary rather than being selected for a headline.

## PIT checks

| Stream/arm | PIT mean | Central90 count/100 | Below.05 / above.95 | Lag1 / lag5 PIT correlation |
|---|---:|---:|---|---|
| Sim reference | 0.46855 | 92 | 6 / 2 | -0.052 / 0.202 |
| Sim NIG | 0.48602 | 94 | 5 / 1 | -0.177 / 0.195 |
| Sim rolling t5 | 0.48674 | 93 | 5 / 2 | -0.092 / 0.189 |
| Sim EWMA t5 | 0.47221 | 88 | 8 / 4 | -0.027 / 0.201 |
| Real reference | 0.47848 | 93 | 5 / 2 | -0.330 / -0.037 |
| Real NIG | 0.45533 | 90 | 7 / 3 | -0.448 / -0.049 |
| Real rolling t5 | 0.46620 | 87 | 9 / 4 | -0.338 / -0.018 |
| Real EWMA t5 | 0.45629 | 93 | 5 / 2 | -0.320 / -0.037 |

Warm central90 counts are92/92/92(sim) and94/93/94(real), in seed order above.
All ten-bin PIT counts and warm diagnostics are retained in the summary. Real
PIT serial dependence remains visible; coverage near90% alone is not predictive
calibration or independent-uniformity evidence. No iid calibration p-values were
computed.

## Execution, provenance and limits

The fixed two-origin preflight passed. Its measured timing fixed a445-second
remaining full-run budget before the other198 origins were computed. The failed
attempt consumed136.828 processing seconds; the separate recovery used148.156
seconds within its remaining308.172-second allowance. The recovery supervisor
observed peak owned RSS278,761,472 bytes and no surviving owned processes. This
is artifact scoring cost, not sampler or end-to-end quote latency. All work was
local; no new AWS or sampler execution was required.

The prior streams and real-data tail were already inspected in earlier work.
Earlier positive SV/NIG interval-score evidence used a different target/window.
This study adds full-return scoring for the current target and its warm
approximation, not fresh market-value discovery. The real panel is a single
dependent historical stream. No data selection, economic losses, transaction
costs, inventory effects or executable AMM decisions are tested here.

Original source freeze: `FREEZE.json`. Separate recovery amendment:
`RECOVERY-FREEZE.json`, including its explicitly superseded pre-execution snapshot.
`RECOVERY-AUDIT.json` binds original outputs and inputs. Archive `artifacts/evidence.zip`
contains original-interrupted, amended-recovery and reporting-view trees, with
partial checkpoint history and exact provenance. Archive SHA256:
`06386cca30fa6f12288b4719d03c54b706d2ef853b86d2a1d748c524bbc2e165`.
`CHECKSUMS.sha256` binds the report and committed evidence. The original frozen
analysis is still recorded as failed; only the amended recovered panel is complete.
