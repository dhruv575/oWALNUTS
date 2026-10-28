# E67: bounded inventory decision diagnostic

The richer SV forecast did not demonstrate a decision-cost improvement over EWMA at the fixed conversion cost. April and May have slightly worse point estimates; June is slightly better but its primary interval touches zero and its 24-origin sensitivity crosses zero. Forecast squared-error point estimates improve in all six comparisons, yet that does not establish a better inventory decision. This is a retrospective diagnostic on already exposed E64 data, not fresh confirmation or profitability evidence.

All 4,368 origins, 13,104 forecast-arm slots, 24 reference computations and 27 execution jobs completed. Every planned comparison is retained below. No sampling, market acquisition, threshold tuning or outcome-selected follow-up occurred.

## Decision and target

At each origin an external endowment supplies one unit of a hypothetical spot-like asset indexed to BTC-PERPETUAL returns. This is not actual spot execution or perpetual margin/funding P&L, and the repeated endowment is not a self-financing portfolio.

For next log return R, retaining incurs bounded downside Y=max(1-exp(R),0), while converting incurs the fixed hypothetical friction c=0.0005 of initial notional. The decision retains when estimated E[Y] is at most c and converts otherwise, with ties retained. Y lies in [0,1], so the target and its squared-error proper score have finite moments even where exponential-price moments do not. Upside opportunity cost, actual fills, trading fees, adverse selection and inventory replenishment are outside this decision contract.

The frozen [proposal](PROPOSAL.md) reuses every E64 April/May/June posterior draw (4x400 per origin) and all 24 original long references (4x4000), plus unchanged rolling/EWMA t5 fits. The target is an empirical posterior-mixture mean; eight references per month do not establish whole-path posterior accuracy.

## Fixed policy comparisons

Positive advantage is control cost minus SV decision cost. Entries are multiplied by 1e6; they are cost fractions of endowed initial notional, not investment returns. EWMA is primary; the other three controls are secondary.

| Month | Control | Mean advantage x 1e6 | Primary 95% interval, 48-origin blocks x 1e6 |
|---|---|---:|---:|
| 2026-04 | ewma_t5 | -2.659 | [-16.597, 11.844] |
| 2026-04 | rolling_t5 | 3.930 | [-3.858, 13.225] |
| 2026-04 | always_retain | 426.545 | [325.163, 525.996] |
| 2026-04 | always_convert | 3.930 | [-3.858, 13.225] |
| 2026-05 | ewma_t5 | -0.936 | [-12.601, 10.696] |
| 2026-05 | rolling_t5 | 8.064 | [-5.977, 24.031] |
| 2026-05 | always_retain | 303.308 | [208.848, 399.081] |
| 2026-05 | always_convert | 8.064 | [-5.977, 24.031] |
| 2026-06 | ewma_t5 | 0.236 | [0.000, 0.818] |
| 2026-06 | rolling_t5 | 0.000 | [0.000, 0.000] |
| 2026-06 | always_retain | 891.194 | [663.396, 1141.270] |
| 2026-06 | always_convert | 0.000 | [0.000, 0.000] |

The strong improvement over always retaining does not establish incremental value over a cheap policy. Rolling t5 always converts in all three months, so its policy comparison equals always-convert. SV converts at every June origin, and EWMA differs at only three June origins: the narrow/touching-zero bootstrap result reflects nearly identical actions, not precise proof of a useful improvement.

## Fixed forecast comparisons

Positive advantage is baseline squared error minus SV squared error. Units below are multiplied by 1e9; these values must not be compared directly with the policy-cost table.

| Month | Baseline | Mean squared-error advantage x 1e9 | Primary 95% interval, 48-origin blocks x 1e9 |
|---|---|---:|---:|
| 2026-04 | ewma_t5 | 31.162 | [-5.189, 72.372] |
| 2026-04 | rolling_t5 | 63.453 | [-1.829, 135.935] |
| 2026-05 | ewma_t5 | 30.479 | [3.224, 60.517] |
| 2026-05 | rolling_t5 | 55.018 | [12.856, 104.304] |
| 2026-06 | ewma_t5 | 34.901 | [-75.538, 171.984] |
| 2026-06 | rolling_t5 | 192.559 | [55.742, 339.371] |

Only May versus EWMA and May/June versus rolling have primary intervals strictly above zero. No primary result is upgraded using a favorable sensitivity interval. All frozen 24/48/96-origin intervals are retained in the three summaries. Serial dependence, overlapping estimation windows and adjacent months limit interpretation; block lengths do not guarantee robustness to longer dependence. No pooled confidence interval, multiplicity-adjusted win claim or qualification rule is used.

## Actions, levels and cost

| Month | Arm | Mean predicted downside | Mean realized decision cost | Conversion rate | Median postprocess seconds |
|---|---|---:|---:|---:|---:|
| 2026-04 | candidate | 0.00100681 | 0.00049607 | 96.46% | 6.513793 |
| 2026-04 | rolling_t5 | 0.00092790 | 0.00050000 | 100.00% | 0.005283 |
| 2026-04 | ewma_t5 | 0.00094125 | 0.00049341 | 87.78% | 0.004990 |
| 2026-05 | candidate | 0.00082858 | 0.00049194 | 93.15% | 6.367540 |
| 2026-05 | rolling_t5 | 0.00078608 | 0.00050000 | 100.00% | 0.005497 |
| 2026-05 | ewma_t5 | 0.00079155 | 0.00049100 | 85.08% | 0.004993 |
| 2026-06 | candidate | 0.00138901 | 0.00050000 | 100.00% | 6.467889 |
| 2026-06 | rolling_t5 | 0.00131370 | 0.00050000 | 100.00% | 0.005541 |
| 2026-06 | ewma_t5 | 0.00136166 | 0.00050024 | 99.79% | 0.005277 |

The fixed threshold produces high conversion rates, limiting discrimination between forecasting methods. It was not changed after observing these results. SV's roughly 6.4-6.5 seconds per origin is cached-draw bounded-loss integration on 12 concurrent one-core workers. Baseline integration takes roughly 0.005 seconds. This is postprocessing cost, not measured combined live inference/decision latency. Whole campaign wall time was 2,524.025 seconds, with sampled peak RSS of 5,354,422,272 bytes; no cost-benefit or deployability claim follows from the small policy differences.

## Numerical validity and reference precision

All 4,392 SV/reference integrations passed the declared gates. Maximum GH64/128 mean discrepancy was 8.674e-19, and maximum adaptive outer error estimate was 1.250e-9. There were no GH action disagreements or estimated threshold ambiguities. Integration uses E[Y]=integral exp(r)F(r)dr from minus infinity to zero; truncation below -log(1e10) has a rigorous omitted-tail bound of 1e-10. Adaptive quadrature error estimates and GH agreement are not certified bounds on total predictive error. Thus zero estimated ambiguity is not proof that every action is exact.

All 24 inherited E64 references pass their original diagnostic gates, and all candidate/reference functional MCSE outputs are available. Candidate-minus-reference mean differences range from -0.000024021 to 0.000016366. Maximum candidate-own MCSE is 0.000021169; maximum reference-own MCSE is 0.000007761. These are chain-aware MCSEs of the bounded mean functional, with no quantile-density division. They are descriptive spot checks and were not used to replace, extend or select runs.

The 30/120-second limits apply to candidate/reference integral arithmetic. File persistence and precision diagnostics remain bounded by the worker and campaign envelopes; these are not hard full-origin latency promises. Before production, deterministic fixtures and twelve concurrent full-size literal workloads passed, including narrow scales, broad volatility, boundedness, independent integral checks, policy ties and complete/missing accounting.

## Reproducibility and scope

A postsealed arithmetic audit independently reproduces all 18 comparison means from complete row records without rerunning scoring, integration or bootstrap. All 9,336 archived hashes were independently verified, and all 27 jobs exited zero with no remaining owned process.

- Full archive: `C:/dev/owalnuts/target/bounded-inventory-evidence-20261027.tar.gz`, 15,706,658 bytes.
- SHA256: `865e5a2836c566def85f5c8d120bd219ca4588ae4a6325745d118fb38f8bc964`.
- Verified expansion: `C:/dev/owalnuts/target/bounded-inventory-verified-20261027`.
- Bounded publication metadata and complete archive hash inventory: [evidence](evidence/).

The result separates forecast accuracy from a concrete bounded decision: better scores need not produce useful action improvements at a fixed threshold. It provides no evidence of executable AMM profit. Research stopped after this planned study, with artifacts preserved before AWS shutdown.
