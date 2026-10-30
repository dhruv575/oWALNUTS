# Conditional reconsideration: screen fails

All 36 bounded jobs completed in 55.20 seconds; groups drained and source
dependencies remained unchanged. Candidate decision windows were audited.
Eleven unaffected candidate paths exactly match incumbent draws (bytewise),
target calls, retained/warmup work and metric updates. The one late-dense path
is kidiq seed 927100003; its mechanism was separately preflight-tested.

Each arm passes 11/12 diagnostic cells. GP seed 927100002 fails identically
across all three arms: R-hat 1.0135, tail ESS 331.6, bulk ESS 519.0, no
divergences. Every regression/time-series cell passes. Maximum normalized
reference-mean discrepancy across all cells is 2.482 using combined MCSE;
this is descriptive and does not override the diagnostic failure.

Median per-seed efficiency ratios (minimum bulk ESS / total target calls):

| Model | candidate / diagonal | candidate / existing auto2 | dense auto2 / candidate |
|---|---:|---:|---:|
| earnings | 1.000 | 1.000 | 1/3 / 1/3 |
| kidiq | 5.657 | 1.000 | 2/3 / 3/3 |
| garch11 | 1.000 | 1.000 | 1/3 / 1/3 |
| GP guard | 1.000 | 1.000 | 0/3 / 0/3 |

One kidiq seed gains about 5.49x versus auto2, but the frozen median-based
three-target geometric mean versus auto2 is 1.0, below 1.2. Do not replace
that estimand with a more favorable post-hoc mean. Overall verdict FAIL.
No production default change, no claim of substantive improvement; the opt-in
is research-only. Broad confirmation is not justified by this screen.

Fourteen research-feature metric/fingerprint tests and three no-feature
fingerprint tests pass. The complete 218-member archive includes source,
binary, preflight, tests, all runs, model/data and reference inputs, with
local and exact-version S3 restore verification receipts in archive/.

Next direction: reassess actual applications beyond four-parameter inference,
starting with whether a population pharmacokinetic model on the preserved
12-subject Theoph data earns its complexity against a linear population model.
First review identifiability, numerical conditioning and relevant baselines.
Any nonlinear inference experiment requires separately qualified references
and strong tuned samplers and approximations; a higher dimension alone is not
a use case, and clinical/decision-value claims remain unsupported. Preserve
the earlier patient-reference failures and every failed sampler improvement.
