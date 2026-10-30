# GP qualification repair and fresh workflow comparison

The native baseline is repairable without changing the model. Target acceptance.9 retains divergences on both calibration seeds for both metric modes. All four diagonal/low-rank configurations at.99 or.999 pass both seeds. The frozen calibration criterion selects low_rank,.99 at786.6 actual gradient calls per minimum bulkESS. This replaces the inadequate.8 default baseline for this target; earlier native failures must not be described as an inherent WALNUTS advantage.

Eight fresh paired seed sets use4 chains,1100 warmup,2000 retained draws with the selected native configuration and existing WALNUTS automatic adaptation. Initializers differ, so this compares workflows. Actual target calls include initialization/warmup and retained sampling; calibration cost is reported separately. Same accuracy gates and qualified reference, no discarded fits.

| Workflow | Qualified fits | Divergences total | Median minimum bulkESS | Median total gradient calls |
|---|---:|---:|---:|---:|
| low_rank | 8/8 | 0 | 840.7 | 658377 |
| walnuts_auto | 8/8 | 0 | 1646.5 | 1827198 |

WALNUTS/native minimum-bulkESS-per-total-call geometric ratio: **0.7001**, paired95% bootstrap interval **[0.6306,0.7770]**. Above1 favors WALNUTS. Frozen signal gate passed: **False**.

Native calibration expense: 25,398,846 actual gradient calls across12 fits. This is not selectively charged to native for a steady-workflow claim; WALNUTS settings also benefited from earlier research. Post-import operation clocks are preserved but are not end-to-end timing and are not the primary gate.

All recorded functionals were independently replayed through the bulk/tailESS and rank R-hat computations; target/source/reference hashes match. Counter receipts and raw arrays remain archived. There is no default change, application-value result, uniqueness claim, or goal completion. The target has only11 observed counts and13 parameters, and model-rewrite and approximate-inference controls are not yet tested.

Next reviewed step: before any further GP superiority claim, give WALNUTS equal bounded calibration over metric and acceptance settings, then validate only the frozen selection on new seeds against this repaired native control. If the calibrated comparison remains negative, close this benchmark route rather than weakening reference or divergence gates. Centered GP/model rewrites and approximate controls remain necessary for practical usefulness even if a later sampler screen passes.
