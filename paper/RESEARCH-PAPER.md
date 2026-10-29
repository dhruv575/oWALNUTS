# Research paper: working manuscript and evidence contract

**Curvature/tuning extension (2026-10-29):** 144 calibration and 384 held-out
fits show roughly 2x lower fixed-budget WALNUTS kernel cost after tuning and
improved depth-limit qualification in the hardest case. The declared
multi-target speed advantage over tuned NUTS fails. In the hardest case,
WALNUTS uses approximately half the target calls, motivating an expensive-
likelihood hypothesis; an additive-cost projection is not measured evidence.
Exact reparameterization remains substantially cheaper. See the
[full extension](../STUDIES/curvature_scaling_v1/results-20261029/REPORT.md).

**Known-truth geometry screen (2026-10-29):** nine target geometries, 432
held-out fits, and a corrected 96-fit native follow-up identify a narrow
curved-target precision-per-draw lead. WALNUTS qualifies 8/8 seeds at 3,000
draws, versus 1/8, 5/8, and 6/8 for three NUTS configurations. Larger budgets
qualify all method ladders. Stronger native NUTS controls remove the clear
total-cost advantage; this is not an AMM or uniqueness result. See the
[full report](../STUDIES/geometry_precision_v1/results-20261029/REPORT.md),
including preserved adapter failures and warm-continuation negatives.

**Exploratory pivot screen (2026-10-29):** 400 independent synthetic replicates
across hierarchical A/B, revenue A/B, contextual bandits and inventory completed.
Hierarchical and inventory models improved on some simpler baselines, but Laplace
retained similar decision quality at much lower observed cost. No tested pivot
established a WALNUTS-specific advantage; inventory's strict posterior reference
qualification was poor. These are small, exploratory formulations, not general
domain-level impossibility results. See [the complete screen](../STUDIES/pivot_screen_v1/results-20261029/REPORT.md).

**Historical confirmation update (2026-10-29):** the 3,050-slot bounded-prior
September/October study has finished with verified archives. One missing primary
report and one NUTS diagnostic failure block formal confirmation. Descriptive
available-case gains over rolling t5 are positive with positive 98.75% lower
bounds in both months, but EWMA lower bounds cross zero at all three specified
block lengths. Qualified WALNUTS/NUTS predictive differences are small; complete
study-wide equivalence is not established. See the [final analysis and limitations](../STUDIES/bounded_confirmation_v1/final-analysis-20261029/REPORT.md).

**Model-admissibility warning (2026-10-28):** an exact-tie audit and analytical
derivation identify a potentially improper posterior for the current no-flow
SV target on repeated observations. This affects 155 January and 311 February
rolling windows, including February sentinel 577, and the repeated literal
fixture. The derivation needs independent mathematical review. Finite-chain
diagnostic passes on these inputs cannot establish posterior validity; prior
tables retain their historical numerical results with this additional limitation.
See [posterior propriety](../STUDIES/amm_accounting_v1/POSTERIOR-PROPRIETY.md).

A separate finite-price-cell candidate now has an analytic propriety argument
and synthetic implementation/reference checks, including independent-method
agreement on two T250 fixtures. One short synthetic fixture still fails the
independent sampler's diagnostics. This is a changed target with unresolved
market observation assumptions; it does not repair or inherit the old market
results. See [updated sampler readiness](SAMPLER-READINESS.md).

Status: manuscript preparation, not submission-ready. Required by Dhruv on
2026-10-28. Working title: **Fast Bayesian volatility updates: predictive gains,
decision sensitivity, and the limits of market-making evidence**.

## Bounded-prior development result (2026-10-28)

A separately specified bounded-volatility-prior candidate completed all 72 fixed
origin/cap cells (24 development origins, three caps), with both NUTS and WALNUTS
qualified in all 144 fits. Mean predictive log-score gains over rolling t5, EWMA
t5 and NIG AR1 were positive at every cap, but concentrated in December. At cap
1, January mean scores were worse than all three baselines, and rolling-t5 wins
occurred at only 9 of 24 origins. Sampler score differences were small relative
to model-versus-baseline differences. This supports implementation reliability
on this panel, not general predictive dominance or economic value. Full results,
denominators and limitations are in
[the development screen](../STUDIES/amm_accounting_v1/BOUNDED-MARKET-RESULTS.md).
Untouched confirmation, mathematical review and economic evaluation remain open.

## Research question

Can affordable repeated Bayesian posterior updates produce reliable predictive
quantities and improve economically specified market-making decisions beyond
strong inexpensive controls? What part of any improvement comes from the model,
and what part is enabled by the inference algorithm's cost and accuracy?

A model-versus-EWMA comparison does not identify a sampler advantage. The final
paper needs same-target inference comparisons at matched accuracy or matched
resource budgets, in addition to predictive and economic comparisons.

WALNUTS itself is established prior work: Bou-Rabee, Carpenter, Kleppe and Liu,
JMLR 27(113), 2026. That paper already includes stochastic-volatility experiments.
We must not claim originality for the base sampler or merely applying it to SV.
The working methods prose is in METHODS.md; novelty remains to be established
for our sequential workflow, validated implementation or application findings.

## Provisional abstract structure

Introduce the need to update latent-state uncertainty under streaming data.
Describe oWALNUTS and the exact algorithmic contribution only after checking its
relationship to prior samplers. Specify the robust stochastic-volatility model,
rolling-window target, computational budgets and approximation diagnostics.
Report historical predictive gains with period-level variation and strong
baselines. Report reference failures and negative decision results. Add a
self-financing AMM evaluation only once execution and costs are validated.
Conclude within the scope of the evidence, without a deployment claim.

This outline deliberately contains no invented numerical result or novelty claim.

## Evidence and claims matrix

| Claim | Existing evidence | Remaining limitation |
|---|---|---|
| Historical density value | E62 August; E64 April–June | Historical/project-access holdout; weaker gains over EWMA; no live execution |
| Tail-risk forecast value | E65 retrospective; E66 December–February | Mixed EWMA comparisons, descriptive intervals, two E66 reference failures |
| Repeated posterior fidelity | WP88 and subsequent K400/reference studies | Accuracy and long-horizon limitations; reference spots do not certify all origins |
| Larger independent-reference budget | E70: all 24 fixed E66 points, 4x retained draws | MCSE roughly halved but 22/24 still pass; one remaining precision failure and a different retained divergence |
| Bounded decision value | E67 | No convincing improvement over EWMA at the frozen cost |
| Sensitivity of actions to cost | E68 all fixed grid entries | Exploratory exposed-data analysis; cannot select cost and claim confirmation |
| Economically meaningful AMM performance | Not established | Self-financing accounting, fills, fees, slippage, latency, adverse selection and market data |
| Unique algorithm benefit | Not established by forecasting results | Same target/model, matched precision and resource comparisons, specialized baseline |

## Proposed sections

1. Introduction: specific contribution, research questions and claim boundaries.
2. Related work: adaptive MCMC, sequential/warm-start inference, SV forecasting,
   proper scoring, dependent-data uncertainty, AMM economics.
3. Algorithm: complete transition and adaptation specification, invariance
   argument, failure modes, complexity and reproducible implementation.
4. Statistical model and predictive functionals: latent-state innovation,
   posterior mixture, heavy-tail moment limitations and numerical integration.
5. Protocol: chronological information sets, data exposure, immutable plans,
   baseline selection, reference gates, complete denominators and compute costs.
6. Results: posterior fidelity; prediction; decision value, separately.
7. Ablations: algorithm versus model gains, warm versus refit, computational
   budgets, parameterization and specialized inference controls.
8. Limitations: reuse, temporal dependence, reference failures, model mismatch,
   execution counterfactuals and lack of profitability evidence where applicable.
9. Reproducibility: source revisions, environment identities, archive versions,
   file hashes and executable analysis commands.

## Submission readiness gates

The [sampler readiness supplement](SAMPLER-READINESS.md) retains the newer
warm-budget runtime failures, market diagnostic failures and narrowly scoped
blocked-path development evidence separately from the existing figure bundle.

The [accounting readiness supplement](ACCOUNTING-READINESS.md) records the fixed
observed mint/burn panel and its conditional integer reconstruction. It keeps
transport failures, unvalidated contract/token assumptions and economic
identification gaps separate from the sampler results.

The current reproducible table/figure bundle and its limitations are documented
in [README.md](README.md). It contains all 44 completed density, tail-loss and
bounded-decision comparisons; ongoing experiments are not silently included.

- A defensible original contribution relative to primary literature.
- Proofs or appropriately scoped empirical claims for algorithm correctness.
- No outcome-driven tuning presented as confirmation; all failures retained.
- Independently checkable tables/figures from immutable artifacts.
- Valid uncertainty treatment for the actual sampling and temporal dependence.
- Economic conclusions only from an explicit feasible decision/execution model.
- Same-model competitors and fair end-to-end costs for algorithm claims.
- Full manuscript, bibliography, limitations, appendices and artifact README.
- Venue formatting and a final technical/editorial review; preparation does not
  authorize submitting to a journal/conference or naming unconfirmed coauthors.

## Economic references checked during preparation

- Milionis, Moallemi, Roughgarden and Zhang, *Automated Market Making and
  Loss-Versus-Rebalancing*, arXiv:2208.06046v6 (2026 revision):
  https://arxiv.org/abs/2208.06046v6 . Separates market exposure from fees and
  arbitrage losses; its assumptions must not be silently imported into data.
- Milionis, Moallemi and Roughgarden, *Automated Market Making and Arbitrage
  Profits in the Presence of Fees*, arXiv:2305.14604:
  https://arxiv.org/abs/2305.14604 . Candidate for detailed methods review.

The [related-work draft](RELATED-WORK.md) records verified primary references for
WALNUTS, elliptical slice sampling and stochastic-volatility interweaving, and
separates existing methods from still-unproven contribution candidates. Sampler,
forecast and economic literature still require systematic review.
