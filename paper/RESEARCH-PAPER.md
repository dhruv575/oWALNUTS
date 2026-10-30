# Research paper: working manuscript and evidence contract

**Practical ODE pilot (2026-10-29):** 117 corrected jobs completed after a
preserved forecast-solver failure and separately frozen log-state repair.
On the public nonlinear pharmacokinetic ODE fixture, WALNUTS qualifies 8/8 fresh
seeds versus tuned NUTS 7/8, with 1.65x matched kernel speedup (descriptive 95%
bootstrap interval 1.58–1.73; seven pairs) and 1.61x cold-total speedup. This
extends the evaluation-cost finding beyond the curved Gaussian construction,
but does not establish clinical or application value. The fixture's clinical
provenance is unverified. Laplace fails parameter-mean accuracy while meeting
the tested forecast tolerances. All three observed-subject nonlinear references
fail the frozen qualification gate, blocking patient matched-accuracy claims;
their numerical audits pass, and R-hat/ESS alone do not override those gates.
The exact linear-elimination controls have qualified references. No practical
success or uniqueness claim follows. See [conclusion and limitations](../STUDIES/pharma_ode_v1/results-20261029/corrected/CONCLUSION.md),
[full evidence tables](../STUDIES/pharma_ode_v1/results-20261029/corrected/REPORT.md)
and [existing pharmacometric methods](../STUDIES/pharma_ode_v1/RELATED-WORK.md).

**Measured likelihood-cost follow-up (2026-10-29):** the depth10 primary
screen fails its strict depth qualification, while a separately frozen depth11
follow-up qualifies all 8/8 fresh seeds per full-evaluator arm. On the controlled
2048-observation curved Gaussian posterior, WALNUTS is 1.93x faster than diagonal
NUTS and 2.56x faster than low-rank NUTS in native kernel time; total-time gains
are 1.82x/2.40x. This supports the proposed evaluation-cost mechanism. Analytic
collapse/reparameterization and exact IID draws remain far cheaper, so it does
not establish practical uniqueness or AMM success. See the
[primary and follow-up evidence](../STUDIES/likelihood_cost_v1/results-20261029/REPORT.md).

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

### Exploratory importance-correction follow-up (2026-10-29)

The public four-parameter ODE benchmark has Laplace tail-probability gaps up
to 0.104 against the qualified reference. A frozen defensive importance
proposal (equal Gaussian and Student-t mixture) was screened at four budgets.
The fresh-seed extension passed the prespecified functional error, precision,
weight and density-consistency gates in 5/8 runs at 65,536 draws and 7/8 at
262,144 draws. Median total worker time at the latter budget was 20.73 seconds.
The remaining failure exceeded the Monte Carlo precision limit while meeting
the reference-error gate. These exploratory results strengthen a cheap
competitor; they do not establish confirmatory reliability, a new matched
WALNUTS comparison, clinical decision value, or algorithmic uniqueness.
Patient reference qualification failures remain unchanged. Reproducible
protocol, results and verified archive receipts are in
`STUDIES/usefulness_search_v1/budget_extension` and `archive-budget-v1`.

An exploratory common-functional audit of the preserved public ODE validation
draws yields 6/8 WALNUTS and 7/8 NUTS passes. All WALNUTS runs meet the error
and diagnostic gates, but two miss precision; all NUTS runs meet error and
precision gates, but one fails diagnostics. This does not support an exclusive
WALNUTS advantage for the observed tail discrepancies. Details and authenticated
inputs are in `STUDIES/usefulness_search_v1/mcmc-audit01`.

A separate exposed-workload mechanism screen removed unused reverse-schedule
allocation in an isolated build. Across eight alternated-order pairs, median
baseline/candidate wall ratios were 1.053 (funnel), 0.971 (Gaussian), and 0.990
(Eight Schools), with matching draw fingerprints and target-call counts. The
change was not adopted; these short timings do not establish a substantive
algorithm improvement. Full logs are in `usefulness_search_v1/kernel_profile`.

A fresh-seed screen of later Hessian-based metric selection (window 3 versus
window 2 and diagonal, four models, three seeds, 36 fits) passes all statistical
diagnostics but fails its improvement rule. Median efficiency ratios versus
the existing automatic selector are 0.873 on earnings, 0.972 on kidiq, and
1.000 on garch11 (three-target geometric mean 0.947); the nonlinear GP control
remains diagonal. Gains versus plain diagonal (~5.5x on the regressions) do
not imply improvement over the stronger incumbent. An earlier 36-fit batch
was invalidated by a configuration bug and retained as administrative evidence.
The repaired protocol, results and full archive receipts are in
`STUDIES/usefulness_search_v1/late_metric`. No default change was made.

Conditional reconsideration of early diagonal metric choices also fails its
frozen improvement screen: 36 fresh-seed fits produce 11/12 diagnostic passes
per arm and one recovered dense choice on kidiq, but the median-based efficiency
geometric mean versus existing automatic selection is 1.0 (required 1.2).
Eleven unaffected paths match draws and work exactly. The common GP failure
is preserved. The research opt-in is not promoted; see
`STUDIES/usefulness_search_v1/reconsider/REPORT.md` and its verified archive.

A hierarchical PK preflight on all 12 Theoph subjects compared linear (43
unconstrained parameters) and nonlinear elimination (57). Of four starts per
model, two linear and one nonlinear fit qualified; false optimizer convergence
was rejected using gradient checks. Selected modes passed numerical audits.
On 24 observations withheld from fitting, exposed-data plug-in log-concentration
RMSE was 0.249 versus 0.535, favoring linear elimination. Parameter uncertainty
is omitted, so this is preliminary model evidence rather than posterior or
clinical validation. Full failures and reproducible artifacts are in
`STUDIES/usefulness_search_v1/population_pk`.

Population rate-order pilots subsequently exposed trapping in both tuned native
samplers. Adding an established involutive MH exchange freed both secondary-started
chains for WALNUTS and an independent fixed-kernel PyMC NUTS control, whereas plain
controls remained trapped. Worst R-hat fell from 1.742 to 1.062 and from 1.788 to
1.017 respectively; neither small pilot qualifies as a posterior reference.
The shared benefit is not evidence of WALNUTS uniqueness, and Python-versus-native
timings are not a fair efficiency comparison. Jacobian/known-mixture checks and
448-point density audits per engine passed. Full protocols, negative wrapper
preflights, numerical audits and private archive receipts are preserved in
`population_pk/EXCHANGE-REPORT.md`. Subsequent source inspection showed that the linear branch already used a
closed-form curve inside Stan; an earlier assumption about numerical ODE
overhead was incorrect. A separate C++ gradient reduces autodiff overhead.


A longer population follow-up qualified two independent exchange-augmented
NUTS references across 68 parameter/predictive functionals (worst R-hat 1.00069,
minimum bulk ESS 3820, maximum independent mean difference 2.078 combined MCSE).
The tested raw Laplace and adaptive importance proposals are inadequate: mean
errors reach 3.15 posterior SD, and final importance ESS is about 1--2. Posterior
prediction improves an exposed-data subject log score over raw Laplace by about
0.52 (descriptive subject-bootstrap interval roughly 0.15--0.82). This does not
establish independent predictive or clinical value. Crucially, matched native
NUTS yields about 1.38 times the minimum bulk ESS/second of WALNUTS on two fresh
seeds; both agree with the practical reference. Unvisited mode mass is not
bounded, and WALNUTS's unseparated callback errors remain a numerical limitation.
This candidate is therefore not a demonstrated WALNUTS advantage. Full negative
and positive evidence, source correction, protocols and verified archive receipts
are in `population_pk/QUALIFIED-REPORT.md`.


Bounding gradient-informed starting masses to [0.1,1000] also fails its frozen
78-cell mechanism screen. Its four-model efficiency statistic is 1.172 and SV
median warmup calls are 0.852 of default, but Lotka--Volterra loses a diagnostic
pass (3/4 versus 4/4) and the acceleration GP ratio is 0.788. An exact audit of
the failed Lotka seed shows bounded and unbounded samples/work are identical:
the bounds never activate. The discrepant chain moves within a separate basin
with a normal step; it is not a frozen-chain case and its probability cannot be
inferred from density height. This rejects the tested bound and does not justify
a stronger uncorrected rescue rule. Complete failures, controls, derivation and
archive receipts are in `usefulness_search_v1/bounded_init/REPORT.md`.

An exact sequential live-ensemble independence-MH prototype passes known-target
one-step stationarity and fixed-kernel integration checks but fails a fresh
128-job mixing screen. In one and eight dimensions, all-broad starts miss a
separated narrow region of probability 0.20; starts covering both regions
estimate its probability at roughly 0.34. Each configuration uses 16 independent
ensembles, with uncertainty computed across ensembles rather than coupled
walkers. Observed occupancy remains between one and three positive walkers;
the product target conditional on that restriction has probability 0.33697.
This supports a finite-run occupancy bottleneck, not mathematical nonergodicity.
An exposed Lotka replay improves departure from a discrepant density region,
but this does not override the failed known-target gate. The first replay's
incorrect starting-state assumption and all negative evidence are retained in
`usefulness_search_v1/ensemble_moves/REPORT.md`. Correct invariance alone does
not establish practical mixing or a novel sampler contribution.

A fixed proposal-bank diagnostic repairs that live-ensemble occupancy problem
when the two component centers are supplied. Across 128 fresh jobs, augmented
WALNUTS's positive-region probability RMSE is .033 and .039 in one and eight
dimensions, passing the limited mechanism gate. Yet importance sampling from
the identical fixed bank achieves .019 and .021 RMSE using 800 target evaluations
versus approximately 115000 and 154000 for augmented WALNUTS. Other functionals
are not uniformly dominated; all errors are retained. Oracle centers bypass
mode discovery, and no NUTS comparison or application claim is made. Correct
mechanics therefore does not establish a useful WALNUTS advantage. Protocols,
raw samples/weights and private archive receipts are in
`usefulness_search_v1/fixed_bank/REPORT.md`.

On the 11-point synthetic Poisson-GP benchmark, global unconstrained Laplace
and its defensive importance correction are inadequate: four importance runs
have ESS 2.95--91.96 from 32768 proposals and Pareto k .893--1.150. This gap
closes under a stronger conditional baseline. A conditional-Laplace grid over
two covariance parameters, mixed with the hyperprior and corrected by exact
joint importance weights, passes all four fresh 24-functional checks. ESS is
13281--13357 of 16384; maximum mean error is .031 reference SD and maximum
relative SD error is .0215. Numerical line-search and covariance-factor parity
failures were repaired without relaxing tolerances and are preserved. Per-run
cost includes 180224 factor evaluations and about 294000 conditional objective
evaluations, in addition to 16384 exact density evaluations. The result supports
limited approximation adequacy, not an actual application or a sampler speed
ranking. It removes failure of global Laplace as sufficient motivation for a
WALNUTS campaign on this benchmark; see `usefulness_search_v1/gp_count/REPORT.md`.

### Exposed metric-selection mechanism audit (2026-10-30)

Passive instrumentation reproduced all non-timing result fields in twelve
historical cells for each of two versions. The proposed explanation that one
nonlinear noise coordinate vetoed an otherwise linear coefficient block was
contradicted: coefficient force regressions themselves failed the gate. Offline
finite-difference probes (5,184 separately charged gradient evaluations) instead
found stable trace-normalized positive regression coefficient curvature across
recorded states, despite precision-scale changes up to a factor of 3,168.
The corresponding GP latent curvature changed substantially; several full
Hessians were indefinite. Blocks were identified by parameter names, so this
is mechanism diagnosis, not evidence for an automatic algorithm or speedup.
A prospective name-free stable-curvature selector requires analytic preflight
and fresh broad comparison before any usefulness claim. Earlier failed metric
screens remain failed. Initial temporary raw files were lost for an unknown
reason; the audit was reproduced from verified historical evidence, with exact
agreement to the surviving first analysis. This recovery is not independent
replication. The recovered 297-member archive passed exact-version restore and
member-hash verification. See STUDIES/usefulness_search_v1/metric_blocks/REPORT.md.

The subsequent name-free offline selector preflight recovered all six exposed
regression blocks and selected none in six GP/GARCH controls. An initial rule
incorrectly absorbed independent coordinates; a connected-graph requirement
repaired this analytic failure. Seven analytic and 120 permutation checks passed.
This is development evidence on exposed states, not fresh sampling validation.
Online timing, probe cost and posterior fidelity remain untested. Unit invariance
was checked only for exactly proportional curvature. Both versions are preserved
in the verified archive documented in metric_blocks/SELECTOR-REPORT.md.

A subsequent staged integration preflight discarded a diagonal pilot, estimated
curvature at sixteen states, and installed the inverse selector covariance as
momentum mass through the existing fixed-matrix interface. All eight fresh
Gaussian candidate replicates and sixteen diagonal/dense controls passed frozen
accuracy gates. Candidate maximum rank Rhat was 1.00173 and maximum mean error
.0287 target SD. Charged pilot and probe cost yields 68,259--80,921 target calls
on the correlated target, compared with 64,854--67,282 for full dense adaptation.
Thus the mechanism passes this limited correctness check but demonstrates no
advantage over full dense. Nonlinear and actual-model usefulness remain open;
the staged restart is not a validated single-run warmup policy. Raw evidence and
protocol are in metric_blocks/ONLINE-REPORT.md and its verified archive.

The subsequent four-model, four-seed development screen preserved four failed
earnings installations caused by antisymmetric inversion roundoff. A separately
specified symmetric-inverse repair passed all sixteen candidate accuracy gates.
For earnings the paired median minimum-bulk-ESS per total target call was 3.00
times full-dense adaptation, but the worst replicate achieved only .379 times;
three other models did not clear the continuation gate. Original controls were
reused in the repair and are not independent replication. Pilot and probe work
were charged. This is an exploratory signal requiring matched schedule ablation,
fresh uncertainty analysis and broader controls. The earnings model admits direct
Gaussian-regression posterior sampling, so this signal cannot establish an
application requiring WALNUTS. See metric_blocks/MODEL-REPORT.md; both original
and repaired raw evidence passed exact-version archive restore verification.

The earnings model admits a direct posterior sampler under its actual flat
priors. QR yields sigma squared inverse-gamma with shape (N-p-1)/2 and scale
SSE/2, followed by a conditional Gaussian coefficient draw. At 64 states the
unconstrained log-density differences agree with Stan within 8.53e-13 and scaled
gradients within 6.24e-11. Four fresh 32,768-draw replicates pass the frozen
reference and exact-moment gates. Generation takes .0029--.0043 seconds after
.00063 seconds of QR setup, with zero sampling-time target calls; imports and
diagnostics are excluded. This rules out that earnings model as an application
requiring expensive MCMC. Its adaptation results remain development evidence,
not practical superiority. See metric_blocks/DIRECT-REPORT.md and verified archive.

The subsequent matched sixteen-seed ablation rejects promotion: curvature passed
13/16 accuracy gates, fixed empirical and fixed diagonal each 15/16, and adaptive
dense and automatic adaptation each 16/16. All 96 jobs drained; schedule, cost and
durable-copy audits passed. The frozen all-pairs gate prohibits a qualified
aggregate efficiency interval after these failures. Post-hoc exact-covariance
conditioning exposes highly distorted pilot marginal variances, with condition
proxies up to 2.27e8 and worst coefficient bulk ESS 4.86. This does not establish
causality, but motivates testing full block shape with a common scale instead of
correlation-only reconstruction. It does not rehabilitate the failed candidate.
See metric_blocks/ABLATION-REPORT.md and the verified 427-member archive.

A subsequent reconstruction-only preflight preserves full inverse-precision block
shape, fitting one positive scale per block instead of replacing each marginal
variance. All 47 analytic/exposed checks passed. The three previously failed
geometries show condition-proxy reductions of 2748--21056 times, but these are
neither mixing nor runtime improvements. A new sixteen-seed matched experiment
is frozen separately; the prior candidate remains failed. Broader nonconjugate
validation and useful-application evidence remain absent. See FULL-SHAPE-REPORT.md.

Metric adaptation is established prior art. Bales et al. (2019),
[Selecting the Metric in Hamiltonian Monte Carlo](https://arxiv.org/html/1905.11916v3),
already studies automatic selection and low-rank Hessian adaptation. Hird and
Livingstone (2025), [Quantifying the Effectiveness of Linear Preconditioning in
Markov Chain Monte Carlo](https://www.jmlr.org/papers/v26/23-1633.html), analyzes
several common preconditioners and limitations of diagonal scaling. Seyboldt,
Carlson and Carpenter (2026 preprint), [Preconditioning Hamiltonian Monte Carlo
by minimizing Fisher Divergence](https://arxiv.org/html/2603.18845v1), supplies
position/score-based dense and low-rank alternatives that remain relevant
comparison baselines. The repository's failed WP71 diagonal estimator screen is
not a test of those complete methods. These sources preclude a generic novelty
claim based solely on Hessian-informed selection or improved conditioning;
method-specific comparative evidence is still needed. See RELATED-WORK-AUDIT.md.

A standalone dense Fisher estimator implementation failed its numerical stress
preflight before any model comparison. Nine ill-conditioned Gaussian recovery
fixtures failed; three invalid/regularized-input checks passed. One returned
matrix had relative forward error .986 despite an equation residual1.23e-13.
These are failures of this implementation under the stated stress conditions,
not evidence against the published estimator or complete sampler. No baseline
performance claim follows. Raw matrices and unchanged thresholds are archived;
stable factor-based numerics and further verification remain required. The
concurrent full-shape validation protocol is unchanged. See FISHER-REPORT.md.

The reconstruction-only revision passed its fresh sixteen-seed matched gate:
all five arms met all accuracy requirements. Minimum bulk ESS per charged target
call improved by a geometric mean3.36 versus adaptive dense (paired-bootstrap
95% interval2.61--4.15) and8.29 versus fixed empirical covariance (5.46--13.57).
Worst adaptive-dense ratio remained .900. These intervals concern seed variation
on one model; they are not model-general uncertainty or end-to-end speedups.
The earlier failed candidate remains failed. Earnings has a direct sampler, so
this is mechanism evidence only. Broader nonconjugate controls, qualified strong
baselines and a distinct novel contribution remain outstanding. All96 jobs and
matched-schedule/cost audits passed; the423-member evidence archive was restored
and verified. See FULL-SHAPE-VALIDATION-REPORT.md.

## Broad fallback screen and collapsed proper-prior control (2026-10-30)

A frozen six-target, four-fresh-seed screen completed 96 supervised jobs. The
full-shape candidate with adaptive automatic fallback passed the continuation
gate on proper-prior Gaussian regression: geometric ESS/total-call ratios 15.40
against adaptive dense and 14.10 against automatic adaptation. All four runs of
all three arms passed that target. Sixteen fallback cells matched automatic
adaptation exactly except timing and charged probe cost. No paired accuracy
loss was observed against automatic adaptation; this small screen does not
establish noninferiority. Centered eight schools failed all arms despite a
qualified reference. General usefulness and strong-baseline comparison remain open.

A separately frozen model-specific control then integrated regression coefficients
analytically and log sigma by adaptive quadrature. Marginal moments qualified
against the reference, with numerical-range agreement within 1.52e-9 reference
SD and successful joint density/gradient parity. Integrations took ~13--14ms;
this is not a sampling-time comparison. No IID generator or rigorous tail bound
was qualified. The target therefore supplies mechanism evidence but a weak
application case for MCMC. See metric_blocks/BROAD-REPORT.md and protocols.
The 458-member screen and 14-member collapsed-control archives were independently
restored from exact private S3 versions and verified. Negative results remain.

## Stronger Fisher baseline and failed numerical implementations (2026-10-30)

QR/SVD and Newton-refined double-precision implementations each fail one of16
fixed algebra checks. Newton refinement misleadingly reduces equation residual
while producing .203 relative forward error. An80-digit implementation of the
same existing estimator passes all16 checks without relaxing thresholds.
These are implementation results, not failures of the published estimator.

A supplemental arm reuses24 broad-screen pilots and controls (not independent
replication), charging400 score evaluations and all fitting time. Candidate over
Fisher geometric ESS/total-call ratios are .809 ARMA,.980 arK,.977 proper-prior
regression and .672 GARCH. Fisher passes all four runs on each of those targets,
but fails two GP runs and all four centered eight-schools runs. No regression
advantage over this stronger estimator is demonstrated. Wall-time comparisons
against the expensive high-precision implementation cannot imply superiority
over an optimized Fisher implementation. All48 jobs and cost/hash audits pass.

A post-hoc leave-one-chain-out affine-score audit motivates a future reliability
gate; it supplies no independent validation. Worst directional predictive R2 is
positive for ARMA,arK,GARCH, negative for GP/eight schools and negative for one
successful regression Fisher pilot. A fresh comparison must test any combined
policy and charge all gate/probe costs. See FISHER-NUMERICS-REPORT.md and
LINEARITY-AUDIT-REPORT.md. All failures and source fixtures are preserved in
verified private archives. General improvement, novelty and application claims
remain open.

## Fresh cross-chain score-gated hybrid: failed continuation gate (2026-10-30)

A frozen16-fresh-seed, six-target, five-arm experiment completed672 bounded jobs
and480 matched sampler stages. Sources and targets were identical across four
chunks. The hybrid uses Fisher when every held-out chain has positive
worst-direction affine-score predictive R2; otherwise it uses the previous
stable-block/automatic policy. All pilot, score and curvature-probe calls are
charged. Hybrid outputs exactly reproduce their selected branch apart from timing.

The hybrid passes16/16 accuracy checks on five targets and0/16 on centered eight
schools, where all arms fail. No paired loss against automatic adaptation or v4
is observed; this does not prove noninferiority. Geometric ESS/total-call ratios
against automatic adaptation are1.241 [1.196,1.280] for ARMA and1.490 [1.320,1.661]
for GARCH. Intervals are exploratory per-target95% paired-seed bootstrap intervals.
Against dense adaptation, GARCH is1.057 [.927,1.177], inconclusive. Fisher passes
15/16 ARMA and13/16 GP compared with hybrid16/16; failed pairs receive no ratios.

The overall prespecified gate FAILS: proper-prior regression hybrid/Fisher is
.8066 [.6083,.9963], below the required .90 floor. Three score-gate rejections
fall back to v4 and cause the loss. The target and threshold are retained.
A cheap collapsed control already limits the regression application claim.
Component timing excludes worker startup/model loading, so no end-to-end runtime
claim is supported. High-precision Fisher also limits optimized-baseline timing
comparisons. Automatic metric selection and Fisher estimators are prior work
(Bales et al.,2019; Seyboldt et al.,2026); the gate's novelty is not established.

All four721-member archives were independently restored from exact private S3
versions and verified; redundant gzip reclamation has per-file audits. See
HYBRID-REPORT.md, HYBRID-TIMING-AUDIT.md, HYBRID-RELATED-WORK.md and the frozen
HYBRID-VALIDATION.md. Diagnose fallback scaling and compare established metric
selection criteria before another fresh study. General usefulness, application
value and manuscript completion remain unproven.

## Fallback scale diagnosis and exposed repair (2026-10-30)

A post-hoc audit of96 saved pilot cells evaluates an established Hessian/covariance
selection criterion on384 held-out-chain folds. It prefers Fisher in every GP
case, including three prior accuracy failures; this criterion alone does not
replace the reliability gate on these data. The implementation uses different
splits/candidates from Bales et al.(2019), not its full adaptation schedule.

The three regression fallbacks exhibit relative scale mismatch: reference-whitened
covariance condition proxies13.62,2.10,5.35 fall to1.27,1.19,1.08 when unchanged
stable-block shapes use Fisher-derived diagonal scales. A separately frozen
exposed repair runs those same three pilot/seed cells. All pass original accuracy
gates, with ESS/total-call ratios1.0445,1.1278,1.0534 against reused Fisher controls.
Ratios against the previous hybrid are7.11,1.67,3.10. This supports a scale mechanism
but is not independent validation, general improvement or an application claim.
The earlier fresh16-seed continuation gate remains FAILED.

The24-member audit and32-member repair archives were restored and verified.
Sampler schedules/costs/binary/durable hashes pass. The audit output scanner covered
only its monitor subdirectory; a separate whole-root audit verifies final output
below64MiB. Future harnesses must monitor the full worker root. No end-to-end
runtime claim is made. See FALLBACK-AUDIT-REPORT.md and SCALE-REPAIR-PREFLIGHT.md.

### Local validation environment after budget interruption (2026-10-30)

The AWS budget action interrupted the fresh scale-repair study; its incomplete
cloud cells are not incorporated as completed evidence. A local Ubuntu WSL
runtime was qualified against archive-verified Linux models and sampler: 64
analytic regression density/gradient checks passed, and an exposed pilot plus
automatic second stage reproduced all non-timing outputs exactly. Python and
runtime provenance differ; local observations and timings are not pooled with
EC2. A separate frozen protocol reserves fresh seeds 929600001--929600016.
The first two-seed chunk completed 84 supervised jobs, passed the evidence audit,
and was archived with member-by-member read-back verification. It selected no
scale-repaired block branch and therefore cannot validate the proposed repair.
All arms still fail the centered eight-schools accuracy gates. Aggregate
validation remains pending; no new application or novelty claim is supported.
See STUDIES/usefulness_search_v1/metric_blocks/LOCAL-RECOVERY-REPORT.md.

Local validation interim checkpoint: four of eight chunks now complete with
336 supervised jobs and 288 matched stages. The first fresh scale-repaired
fallback (regression seed 929600008) meets all accuracy gates, with ESS per total
target call ratios 6.664 against the old fallback and 1.026 against Fisher.
Its measured full invocation time is higher (1.486s versus 1.279s and 1.178s),
so the call-efficiency result must not be presented as lower elapsed time.
The full frozen comparison remains pending. SCORE-GATE-METHODS.md provides the
implemented worst-direction diagnostic's definition, exact-arithmetic affine
invariance argument and limitations; it offers no posterior-accuracy guarantee.

### Completed local scale-repair validation and negative outcome

All eight chunks completed (672 supervised jobs, 576 matched stages). The frozen
continuation criterion failed: GARCH candidate/Fisher ESS-per-call ratio was
0.801 [0.696, 0.908], below the 0.90 floor. There were no paired accuracy losses
against automatic, v4 or the old hybrid, and the candidate passed 16/16 seeds
on five targets, but all arms failed centered eight-schools. The repair was
selected twice on regression; its aggregate candidate/Fisher ratio there was
0.992 [0.977, 1.002]. This does not establish general usefulness. Operational
ESS/second against automatic adaptation was 0.708 on arK, 0.823 on ARMA, 0.751
on GARCH, 0.810 on GP-Poisson and 3.721 on the regression with a cheap collapsed
control. These times include supervised invocations and shared pilot, excluding
common diagnostics/controller IO. LOCAL-SCALED-REPORT.md gives all intervals,
branches, limitations and failure records; exact numeric archive replay passed.

A separate numerical preflight used float64 QR factors with an 80-digit small
matrix solve for the existing Fisher estimator. It passed all 16 original
stress checks and 24 saved-model comparisons against the full-sample oracle
(maximum whitened covariance error 1.624e-14). Geometric fitting-time gain was
4.467x across three alternating paired fits per cell. This is a representation
optimization, not a new estimator, fresh sampler validation or runtime speedup
for the complete algorithm. The failed local sampling gate is unchanged.

RELATED-WORK-CHECK.md records checked primary sources and a remaining comparator
gap: fixed dense Fisher in our staged schedule is not full published Fisher-HMC
adaptation. Native nutpie controls must be qualified before claiming practical
superiority. The current evidence does not support paper-readiness or uniqueness.

### Native baseline integration qualification

Pinned nutpie 0.16.11 now passes the same regression reference gates for native
covariance-diagonal, Fisher-diagonal and low-rank Fisher adaptation. This is
backend qualification on one exposed seed, not a comparative performance study.
The original nonthreaded Stan library was rejected before sampling; an exact
source rebuild with STAN_THREADS=true matched the original density and gradient
at 64 fixed points with zero observed difference. A subsequent result-format
integration error and the initial rejection are both archived. The successful
retry changes only serialization dispatch and retains all accuracy thresholds.
Minimum bulk ESS was 1898, 1372 and 8978, with zero retained divergences.
Full invocations were about 7.8 seconds, whereas sampling plus conversion was
about 0.15 seconds. Future engine comparisons must align timing scopes; those
numbers must not be mixed with WALNUTS timings of different scope. Complete
native target calls are not yet instrumented. Stronger six-target comparison,
application value and a substantive validated general improvement remain open.
See NUTPIE-NATIVE-REPORT.md for exact versions, failures, artifacts and bounds.

### Native cost accounting and model-build parity

A thin BridgeStan C-ABI counter now preserves exact retained native trajectories
for all three qualified regression controls. Explicit value/gradient/Hessian/HVP
checks, a failed-call check and 256 concurrent gradient calls pass. Observed
native gradient counts were 78822/70991/55355; warmup-plus-retained step totals
were 78778/70921/55286. Step diagnostics therefore omit gradient work and must
not be used as complete target-call counts. No value-only, Hessian or HVP calls
occurred in those sampling replays. This is exposed instrumentation qualification,
not comparative sampler evidence; future times must include counter overhead.

The remaining five threaded target builds also match the original density and
gradient at 64 saved-pilot points each with zero observed difference and matching
parameter names. All 20536 regular files of the reused BridgeStan release remain
byte-identical. Archives preserve source, binaries, raw parity evidence and
supervision. NATIVE-COMPARISON-SCREEN.md freezes the next stronger comparison
using actual evaluation counts and aligned post-import operation clocks. It has
not run and does not alter the previous failed continuation result. General
usefulness, application value and paper-readiness remain unproven.

### Native comparison execution update

The previously frozen native comparison has now begun. The six-target short
instrumentation qualification passed all 18 model/mode pairs with exact retained
trajectory parity. The first two fresh chunks completed 84 arm cells, with local
cost/schedule audits and archive read-back. The remaining two chunks are queued
or running; no four-seed efficiency conclusion is available yet.

An exposed full-budget ARMA diagnostic reproduced identical retained trajectories
with and without the counting wrapper in all three native modes. Divergence counts
of 2000, 4000 and 2000 matched the first chunk. This excludes that wrapper as the
cause in these replays; it does not establish a general sampler advantage. Native
default initialization and different adaptation schedules remain limitations.
Failed controls receive no efficiency credit. The frozen four-seed analysis must
finish before deciding whether a larger replication is warranted. No application
value or submission readiness is established by these interim results.

### Completed native comparison screen

All four frozen fresh-seed chunks completed: 168 arm cells, with four local
330-member archives passing read-back and cost/schedule audits. The independent
scalar replay verifies all qualification decisions, 44 paired ratio estimates,
and the final screen gate; bootstrap intervals are exploratory and were not
independently replayed. The prespecified promising-efficiency criterion FAILS.
There are no paired accuracy losses for fast scaled versus automatic WALNUTS.

For GARCH, fast scaled / automatic geometric ESS-per-gradient and post-import
ESS-per-second ratios are 1.611 and 1.404, but the ratios versus native diagonal
are 1.063 and 0.865; versus native draw-diagonal they are 1.192 and 1.070.
Neither native comparison meets the frozen 1.2 threshold in both measures.
Native low-rank qualifies only two GARCH seeds, so receives no paired ratio.
On arK and regression, native low-rank qualifies all four seeds and the candidate
ratios are respectively 0.412/0.361 and 0.413/0.258. ARMA and GP have no fully
qualified native arm, precluding a positive screen claim. All methods fail
centered eight schools. See metric_blocks/NATIVE-SCREEN-REPORT.md and its JSON.

This rejects promotion of the current policy on these exposed model families;
it does not show that every possible metric or WALNUTS improvement fails. The
next diagnostic should distinguish metric adaptation from kernel behavior,
with pinned native metric export/replay qualification before any transplant.
No default change, practical application, uniqueness or paper-readiness follows.

### Fixed-geometry diagnostic readiness

Native affine-map recovery now passes all24 chains across six targets with
held-out coordinate and gradient checks; these exposed short runs are not
posterior validation. Seventy-two target-gradient/kinetic convention checks and
five existing compiled dense-metric tests pass. A separate unpublished runner
accepts fixed per-chain dense momentum covariances and step sizes without
adaptation. Its analytic rotated-Gaussian preflight passes the fixed accuracy
criteria, four exact standalone-chain replays and two invalid-input checks.
Source, binary and failures are archived locally. No library default changed.
The runner uses sequential chains; its wall clock cannot be equated to native
four-core sampling. Matched-geometry comparisons and full cost accounting remain
pending, so no improvement or application claim follows from these checks.

### Matched-geometry exposed diagnostic

The first prefix qualification found native retained-step jitter and was
preserved as a failed fixed-step qualification. A separate no-jitter run passes
all six exact-prefix and continuation-call checks. At native-tuned fixed steps
and recovered per-chain geometry, qualified WALNUTS/native continuation ESS per
actual gradient ratios are .801 arK, .817 GARCH and .651 regression; full workflow
ratios including native pilot costs are .839, .859 and .699. Both methods fail
centered eight schools and GP-Poisson. ARMA fails reconstruction before transfer.
This one exposed seed does not isolate optimal tuning or prove general kernel
superiority. Wall times are incomparable because chain parallelism differs.
A bounded exposed step-size diagnostic is next; any signal needs fresh whole-
pilot validation. No practical success or production change is established.

### Exposed step-size ladder: no advancement

Twenty new bounded cells evaluated global native-step multipliers0.5,2,4,8 on
all five recoverable targets; multiplier1 reused the preserved baseline. No
factor met the frozen criterion for fresh replication. Core full-workflow
ESS/gradient geometric means versus native NUTS were .6621,.7958,.4955,.3375,
and .05384 for factors0.5,1,2,4,8. No paired baseline accuracy losses occurred,
but this is exposed tuning, not confirmation. The ladder is closed.

The initial exact settings-output audit failed because Rust JSON round-trips
changed some values by at most one float64 ULP. The original analyzer is
preserved. The administrative audit now allows one ULP only at that boundary;
requested settings and all statistical criteria remain unchanged. All raw
cells and the negative result are locally archived and read-back verified.
Next consider an observation-only exact duplicate-evaluation audit; no cache
improvement is assumed. Existing initial-evaluation caching is already present.

### Exact repeated-evaluation audit: no cache opportunity established

An observation-only exact-coordinate audit preserves draws and evaluation
counts in all10 enabled/disabled comparisons against the old runner. No repeated
finite coordinate evaluations or output-bit mismatches were observed. At the
original step size four targets have complete finite-call coverage; centered
eight schools exceeds the32768-position-per-chain cap. All factor4 stress cases
also exceed capacity, so no upper bound is claimed for unrecorded keys. The
frozen cache-experiment criterion fails. No caching change is implemented.
Two instrument unit tests cover signed zero, altered outputs, capacity and
nonfinite accounting. The local91-member evidence archive verifies. Next inspect
existing forward/refinement/reverse work counters; no optimization is assumed.

### Work-counter decomposition

All10 profiled replays preserve the old draws and actual call counts. Existing
initial/forward/reverse telemetry reconciles with the independent counter.
At factor1, qualified arK/regression/GARCH reverse-call fractions are5.045%,
6.420%,5.997%; forward calls not attached to built leaves are5.045%,6.423%,6.003%.
Holding observed draws fixed and removing both categories gives accounting-only
ESS/gradient ratios versus native NUTS of .891,.747,.928. These are not attainable
speedups or bounds on a changed algorithm. They indicate that removing these
categories alone cannot explain away the observed efficiency gap.
Factor4 places roughly60% of calls outside built-leaf forward work. Existing
U-turn and reverse-coarser policy studies already preserve negative broader
results. Next use a single-level/permissive-error ablation to separate active
refinement from remaining NUTS implementation differences; no default change
or improvement is inferred. The68-member local source/binary/evidence archive
passes read-back verification.

### Corrected refinement/error-threshold ablation

The initial setup confused the lower-level API's two refinement levels with
sampler::Tuning's eight-level default. Its15 cells and original protocol are
preserved. Ten additional cells establish exact8/1 baseline draw/call parity on
all five targets and complete the one-versus-eight,1-versus1000 factorial.
The easy analytic replay alone was insufficient to establish default identity.

At8/1000, continuation ESS/gradient versus baseline8/1 improves1.382x on arK,
1.457x on regression and1.241x on GARCH. Against native NUTS the ratios are
1.107,.949,1.014. One- and eight-level permissive runs are exactly identical on
these three qualified targets with no reverse calls: this does not demonstrate
beneficial within-orbit refinement. Eight schools and GP remain unqualified.
This exposed tuning lead needs fresh known-truth tail guards and cold-workflow
validation before any default recommendation. No application or novelty claim
follows; the original setup error and its correction remain in the evidence.

### Fresh permissive-error funnel guard (2026-10-30)

Following the corrected refinement factorial, a frozen known-truth guard compared max_error 1 and 1000 with the sampler facade's eight refinement levels, diagonal adaptation, 2,000 warmup and 20,000 retained draws in four chains. Four fresh seeds were used for a ten-dimensional centered funnel and its independent-Gaussian noncentered representation (16 fits). All eight Gaussian controls qualified. Neither threshold qualified on the centered funnel under the exact transformed-moment, tail-MCSE, diagnostic and depth-cap criteria.

For exact P(omega < -5)=0.04779035, default estimates were 0.0565875, 0.0462375, 0.051325 and 0.0388625; permissive estimates were 0.017225, 0, 0.004525 and 0. The fourth permissive run had raw-coordinate Rhat <=1.00372, bulk ESS >=667.84, tail ESS >=563.14 and zero divergences, but eight depth caps and no visits to this tail. Exact-moment checks rejected it. Default tail MCSE remained above the prespecified .005 limit. These results reject promoting the exposed permissive efficiency lead as a general default; they do not establish that the existing default solves the funnel at this budget.

The original strict JSON analysis writer could not serialize NaN diagnostics from constant tail indicators. Its immutable source is retained; a separately recorded output-only repair serializes nonfinite values as null after the unchanged failure gates. Independent replay verified 320 moment estimates, qualification decisions, call accounting, source hashes and process cleanup. Source, binary and raw draws are archived locally with member hash readback. See STUDIES/usefulness_search_v1/metric_blocks/FUNNEL-ERROR-GUARD-PROTOCOL.md, FUNNEL-ERROR-GUARD-REPORT.md and FUNNEL-ERROR-GUARD-INTERPRETATION.md. No production default, application claim or novelty claim is changed. Next distinguish adaptation selection from retained-transition behavior through an explicitly exploratory crossed fixed-geometry diagnostic.

### Crossed fixed-settings funnel diagnostic (2026-10-30)

A separately frozen exploratory 2x2 continuation design crossed default/permissive pilot settings with retained max_error 1/1000, using four exposed pilot seeds, common default-pilot endpoints and fresh chain seeds. Each of 16 fits ran 22,000 fixed-settings transitions, discarding 2,000 before the exact-moment analysis. All exported final steps matched warmup-end steps. Gaussian parity, analytic-gradient and change-of-variables tests, two Gaussian controls, two chain replays and invalid-metric rejection passed before sampling.

All eight retained-threshold-1000 continuations recorded zero visits to omega < -5, under either source of pilot settings. All eight threshold-1 continuations visited it, with estimates 0.0297125 to 0.0622875 against exact probability 0.04779035. None of the 16 fits met the full precision/diagnostic guard; every fit had depth caps including the fixed-settings discard, while all had zero divergences. This localizes the finite-run exploration failure to more than warmup alone. It does not establish stationary bias, a kernel defect, or a useful improvement. The independent replay verified 320 moments, qualification decisions, common starts, telemetry accounting and frozen source hashes. Pilot costs remain separately reported and no cold-workflow advantage is claimed. Source, binary, raw draws and verification are archived locally; the previous pilot archive remains a dependency. See FUNNEL-CROSS-PROTOCOL.md, FUNNEL-CROSS-REPORT.md and FUNNEL-CROSS-INTERPRETATION.md under STUDIES/usefulness_search_v1/metric_blocks.

The next proposed algorithm investigation is observable reuse under the actual trajectory-selection law. Recycling HMC/NUTS is prior work (Nishimura and Dunson, 2020, doi:10.1214/19-BA1171); its existence is not a novel contribution. Our outer biased-progressive selection differs from a simple normalized full-tree mixture, so any conditional estimator first requires a selection-recursion audit, invariant tests and iteration-level uncertainty analysis. No recycling implementation or gain is claimed here.

### Conditional-observable recycling prototype (2026-10-30)

An isolated research copy now carries conditional observable expectations through the existing trajectory-selection recursion. Inner merges use normalized joint-density weights; outer biased-progressive merges use min(1, W_new/W_old). Failed recursive subtrees are excluded, whereas a successfully built outer subtree is combined before the outer U-turn stop. The estimator includes the initial state. Under the existing kernel's invariance and selection-independent construction, conditional expectation preserves stationary observable means. This does not establish reduced long-run MSE, because the selected state controls subsequent transitions. Recycling itself is established prior work (Nishimura and Dunson, 2020), not a novel contribution.

The first build failed due to a generated-runner brace error. The first executable preflight preserved exact draws/work but failed dense-Gaussian second moments: it had observed internal whitened coordinates. Both failures are preserved. The corrected fixed-metric observer applies the actual Cholesky coordinate restoration before evaluating nonlinear observables. No statistical threshold changed. Three Rust tests passed (gradients/change of variables, enumerated selection-tree weights, dense-coordinate restoration). Original, observer-disabled and observer-enabled runs produced identical draws, target calls and every emitted work counter on rotated Gaussian, noncentered Gaussian and centered funnel. Across 96,000 observed transitions, one finite vector was recorded per transition. Both Gaussian controls passed the frozen convergence, health and exact-moment/tail tolerances. The funnel run establishes parity through difficult stop paths only, not qualified funnel accuracy.

Independent replay checked raw-output parity, conditional probability bounds, second-moment Jensen inequalities and unchanged production-source hashes. Source snapshots, original and corrected binaries, failed/passing evidence and provenance are archived locally. The implementation is a serial research recorder for fixed metrics, with allocations, locks, coordinate solves and storage costs. It is not a production change or a verified efficiency improvement. Replicated MSE-per-total-cost comparisons with independent stationary starts and a comparably recycled strong NUTS baseline remain required. See RECYCLING-AUDIT.md, RECYCLING-EXECUTION-AUDIT.md and RECYCLING-PREFLIGHT-REPORT.md under STUDIES/usefulness_search_v1/metric_blocks.

### Replicated recycling MSE and direct-cost screen (2026-10-30)

A frozen stationary-start screen ran 64 independent 1,000-transition replicates for each of rotated Gaussian, noncentered Gaussian and centered funnel, with fixed settings. Ordinary and conditional estimators shared exactly the same draws and emitted work counts. All 96 bounded sampling workers completed. Independent replay verified 192 paired estimate vectors, 88 coordinate/function-specific MSE ratios and 12 family ratios. Analytic truths covered means, second moments and probabilities below 0 and -2; the funnel mixture-tail truth was cross-checked with two quadrature tolerances and a probability-scale parameterization. Paired-replicate bootstrap intervals are exploratory, not multiplicity-adjusted confirmation.

Gaussian-family MSE ratios favored recycling by approximately 1.23-1.70, whereas the funnel ratios were only 1.02-1.04. However, resource-monitor elapsed time was dominated by its .1-second polling interval for these short jobs. We preserved its original advance flags without accepting them as a runtime conclusion. A separately frozen randomized direct-timing audit replayed every input pair three times, reproducing canonical outputs in all 288 runs. Total observed/original cost ratios were 1.360 [1.314,1.400], 1.726 [1.697,1.756] and 1.498 [1.468,1.534] respectively. Sampler-internal overhead was around 19-21%, while serialized output grew about fourfold. Timings include subprocess execution and file close, not a durable fsync guarantee.

Only the exposed rotated-Gaussian probability-below-minus-2 family retained a descriptive cost-adjusted lead: ratio 1.246 with conservative endpoint range [1.053,1.491]. This is not a calibrated joint confidence interval, an application result or superiority over comparably recycled native NUTS. Other families were around parity or lost efficiency; the funnel was approximately .68-.70 after direct cost adjustment. A general improvement claim for the full-recording prototype is rejected. Next investigate equally compact ordinary and conditional estimator outputs, preserving uncertainty information and exact chain parity, before fresh efficacy and strong-baseline validation. Evidence, timing limitations and the prospective timing correction are retained in RECYCLING-MSE-PROTOCOL.md, RECYCLING-MSE-TIMING-AUDIT.md, RECYCLING-MSE-REPORT.md, RECYCLING-MSE-TIMING-REPORT.md and RECYCLING-MSE-INTERPRETATION.md under STUDIES/usefulness_search_v1/metric_blocks. No production changes or goal completion.

### Compact observable output and fresh validation (2026-10-30)

A research-only compact collector now aggregates conditional observable vectors online into overall sums and consecutive blocks of 50 transitions, retaining final partial-block sizes. It no longer stores all conditional vectors in compact mode; the existing sampler still retains its ordinary draws internally. An equally compact ordinary control uses the unchanged production kernel. Both output the same estimator-summary schema and SHA256 of underlying f64 draw bits. Six tests per binary cover gradients, selection weights, coordinate restoration, partial blocks, empty-input and nonfinite-input rejection. Preflight verified 96 compact replays, three full-output exact replays and 48 original-kernel compact controls against preserved raw evidence.

Fresh validation used 64 independent stationary-start replicates per target, 1,000 transitions each, with 288 randomized direct timing executions and three additional full-output checks. The prespecified primary, rotated-Gaussian P(x<-2), failed: MSE ratio 1.293 [1.121,1.462], direct cost ratio 1.078, adjusted ratio 1.199 and descriptive endpoint range [.997,1.452]. Neither frozen lower-bound requirement was met. The noncentered Gaussian second-moment family was a secondary lead, with MSE ratio 1.653 [1.566,1.743], cost 1.142, and adjusted ratio 1.447 [1.349,1.555]. This secondary result does not replace the failed primary. The funnel remained less efficient, at adjusted family ratios .874-.924, so general replacement is rejected.

Preserving block summaries does not ensure calibrated uncertainty. Minimum empirical nominal-95% interval coverages over functionals were .906/.891 (ordinary/conditional) on rotated Gaussian, .828/.875 on noncentered Gaussian and .313/.297 on the centered funnel, each based on 64 runs. These are not simultaneous population coverage guarantees; the severe funnel undercoverage precludes using these short-run intervals for decisions. Independent replay verified summary reconstruction, draw/work hashes, analytic truths, MSE ratios, direct costs and coverage calculations. Sources, binaries and evidence are archived locally with member readback. No production behavior changed. See COMPACT-RECYCLING-PROTOCOL.md, COMPACT-RECYCLING-VALIDATION.md, COMPACT-VALIDATION-REPORT.md and COMPACT-VALIDATION-INTERPRETATION.md under STUDIES/usefulness_search_v1/metric_blocks.

Next qualify a comparably recycled native NUTS control under its actual tree selection and coordinate mappings, before new primary second-moment comparisons on fresh seeds and qualified nonanalytic posterior quantities. Cold adaptation cost, uncertainty calibration, native comparison and application relevance remain unresolved. No practical-superiority, novelty or goal-completion claim follows from this result.

Native recycling control qualification (2026-10-30): A source-isolated nuts-rs 0.18.3 observer passed exact pristine/disabled/enabled draw, progress and target-call parity across six target/adaptation configurations (120,000 transitions per arm). Four Gaussian configurations passed frozen known-truth checks; centered funnel retained 14/109 divergences and supplies parity evidence only. Failed workspace resolution and zero-gradient initialization attempts are preserved. This is a qualified comparator, not comparative efficacy or novelty evidence. Same-compiler compact-output controls and independent seeds are required next. See STUDIES/usefulness_search_v1/metric_blocks/NATIVE-RECYCLING-QUALIFICATION.md.

Independent recycled baseline screen (2026-10-30): Same-compiler compact drivers and 64 fresh replicates per target/arm reject the Gaussian recycling promotion. For noncentered second moments, recycled WAL improves its own ordinary baseline by 1.514x in replicated-MSE-times-process-cost efficiency, but recycled diagonal native NUTS is about 2.69x better despite paying for warmup while WAL uses uncharged fixed geometry. The WAL-favoring ratio is 0.372 with descriptive endpoint range 0.315-0.437, not a joint confidence interval. Ordinary diagonal native also wins (WAL ratio 0.551). Rotated-Gaussian recycled diagonal native wins all four functional families. No retained divergences or aggregate error z above 3.21, but block-MCSE coverage is not certified. The frozen analyzer's stricter ordinary-control gate discrepancy is documented and does not affect failure. No novel method or practical use case is established. See STUDIES/usefulness_search_v1/metric_blocks/RECYCLED-BASELINE-SCREEN-INTERPRETATION.md.

Curved recycling qualification (2026-10-30): Shared 24D all-pairs curvature-5 target drivers passed six pristine/disabled/enabled parity and compact/full replay configurations. Original-coordinate nonlinear observables were verified in direct and exact latent representations against two quadrature forms and independent exact samples. All latent controls passed frozen accuracy/diagnostic checks. Direct fixed WAL failed raw mixing thresholds (maximum Rhat 1.01647; minimum ESS about 201), diagonal native had three divergences, and low-rank native had zero; this is not an efficiency comparison. Existing curvature_scaling_v1 results already reject a broad speed claim and favor the exact transform. Cold-adaptation observer qualification is required before fresh efficacy research. See STUDIES/usefulness_search_v1/metric_blocks/BANANA-RECYCLING-RESULT.md.

Cold recycling observer qualification (2026-10-30): Isolated retained-phase control passes five pristine/disabled/enabled cases with exact retained draw hashes, emitted metadata/telemetry, final adaptation and actual target-call parity. Each observed chain records precisely 4,000 retained vectors after 1,000 discarded transitions; full/compact replay and both latent banana exact-truth controls pass. Warmup positions themselves were not recorded for parity. Severe funnel remains unqualified (Rhat 1.04861, minimum ESS about 116-122) despite zero divergences. Two setup/test failures are preserved. This enables a properly charged cold comparison but is not an efficacy or novelty claim. See STUDIES/usefulness_search_v1/metric_blocks/COLD-RECYCLING-RESULT.md.

Tuned curved cold recycling comparison (2026-10-30): Equal four-configuration calibration searches and 64 fresh validation replicates per selected arm reject promotion. Direct recycled WAL reduces second-moment MSE by 1.087x over its identically tuned ordinary control, but cost-adjusted efficiency is 0.984 (descriptive range 0.955-1.015), with no calibration-amortized gain. Direct native point errors are dominated by one retained replicate and yield inconclusive wide intervals; no outlier is removed. Exact-coordinate and independent-draw controls dominate. All arms have zero retained divergences, illustrating why this alone does not establish qualified inference. Eight backward-compatibility and nine full-output replays pass; source, calibration and validation evidence are archived locally. Instrumentation asymmetries and limited block-interval coverage are documented. See STUDIES/usefulness_search_v1/metric_blocks/CURVED-COLD-INTERPRETATION.md. This closes the curved recycling promotion branch without a practical-usefulness or novelty claim.

Allocation mechanism audit (2026-10-30): An isolated System-allocator counter preserves production trajectories, metadata, work and summaries on five cold cases. Existing state/workspace pooling is already present. Direct-diagonal banana makes 3.25 million gross allocation requests across four 1,000-warmup/4,000-retained chains. Exact-prefix comparisons estimate about147 marginal requests per retained draw and only28% fixed startup/warmup residual, with important storage-capacity caveats. These are allocation counts, not timing, live-memory or usefulness gains. Component attribution is required before proposing an optimization. See STUDIES/usefulness_search_v1/metric_blocks/ALLOCATION-AUDIT-RESULT.md.

### Momentum-sum allocation reuse: exact but slower (2026-10-30)

A scoped allocator audit attributed 65.47% of allocation requests on the direct 24-dimensional curved target to untraced subtree construction. A bounded thread-local pool for consumed momentum-sum vectors reduced total requests by 85.39% on this target and 30.12% on its reparameterized control. The isolated candidate passed 155 library tests (one existing ignored) and reproduced five qualification cases exactly. Twenty fresh four-chain seed sets on each of direct banana, latent banana and funnel also preserved all recorded draw hashes, summaries, tuning, telemetry and target calls exactly. Corrected whole-process timing ratios (original/candidate; geometric mean, paired 95% bootstrap interval) were 0.98474 [0.98049,0.98913], 0.98679 [0.96972,1.00632], and 0.97668 [0.96798,0.98475], respectively. Thus the candidate failed the frozen 1.05 lower-bound primary gate and is not promoted. The initial timed-wait harness quantized short runs; that attempt is preserved and excluded, with every pair repeated using blocking wait under the external bounded supervisor. This negative result separates allocation counts from speed or application value. Production remains unchanged. See STUDIES/usefulness_search_v1/metric_blocks/MOMENTUM-POOL-RESULT.md and the verified local momentum_pool_archive01 evidence; no off-device backup claim is made.

### Published two-stage splitting feasibility (2026-10-30)

We screened symmetric two-stage kick/drift compositions with coefficients b=(3-sqrt(3))/6 and b=0.1931833275037836, following the existing multi-stage HMC literature (Blanes, Casas and Sanz-Serna, DOI10.1137/130932740). This is not a novel integrator contribution. Eight leapfrog steps were compared with four two-stage steps at twice the step size, matching integration time and eight fresh gradient evaluations. Independent exact stationary phase points on Gaussian, two banana and funnel targets isolate numerical feasibility from cold-chain adaptation. Gradient, reversibility, Jacobian-volume and concatenated-leapfrog checks passed. The initial grid showed Gaussian gains but no qualifying curved-target advantage. A preregistered follow-up addressed a missing baseline-acceptance region:2048 calibration phase points per target selected a leapfrog step toward acceptance0.8, followed by16384 independent validation points. For banana curvature5, the primary BCSS/leapfrog accepted normalized squared-jump ratio was0.84068 [0.83249,0.84879] (paired95% bootstrap); curvature2 was0.78069 [0.77319,0.78835] and funnel0.99121 [0.98772,0.99461]. The minimum-norm coefficient was worse on both bananas. These fixed candidates fail the numerical advancement gate and were not integrated into WALNUTS. These one-proposal statistics do not establish ESS, posterior accuracy, application value or full sampler superiority. Sources, all phase points, failures, calibration curves and verified local archives are indexed by TWO-STAGE-RESULT.md and TWO-STAGE-CALIBRATED-RESULT.md in STUDIES/usefulness_search_v1/metric_blocks.

### Pilot-fitted triangular quadratic transport diagnostic (2026-10-30)

A fixed ridge-regularized triangular quadratic shear, following established transport-map preconditioning ideas (Parno and Marzouk, DOI10.1137/17M1134640), was fitted to400 saved pilot positions per model after affine whitening. It was assessed on8000 adjacent continuation positions from one exposed seed set, not fresh independent validation. The globally invertible map has a constant positive Jacobian determinant; inverse, finite-difference gradient and determinant checks passed. Among previously qualified native runs, candidate/affine Gaussian-score discrepancy ratios were1.988 for arK,1.279 for proper-prior regression and0.879 for GARCH. None meets the frozen0.8 advancement threshold. GP's0.348 ratio is excluded from advancement because the saved native run failed qualification (128 divergences, rank R-hat1.060); the centered eight-schools run also failed, and ARMA lacked the required qualification artifact. All targets and the initial missing-artifact failure remain preserved. A separate72-evaluation gradient audit found exact agreement with stored gradients at every checked position. This validates those storage checks, not posterior accuracy. Geometry scores do not establish ESS, full workflow speed or application value. No production change or novelty claim follows. See QUADRATIC-TRANSPORT-RESULT.md and quadratic_transport_archive01 in STUDIES/usefulness_search_v1/metric_blocks.

### GP native-baseline repair and fresh comparison (2026-10-30)

Previous native failures on the11-observation GP Poisson regression used target acceptance0.8. A frozen12-fit calibration crossed diagonal/low-rank adaptation with0.9,0.99,0.999 on two fresh seeds. Both0.9 modes retained divergences; all0.99/0.999 configurations passed both seeds. Low-rank0.99 minimized geometric actual gradient calls per minimum bulkESS among qualified configurations. Eight fresh paired whole-fit comparisons (four chains,1100 warmup,2000 retained draws) against the existing WALNUTS automatic workflow all passed the unchanged reference/diagnostic gates with zero retained divergences. WALNUTS/native minimum-bulkESS-per-total-gradient ratio was0.70013 [0.63062,0.77705] (geometric paired ratio,95% bootstrap); every pair favored the repaired native baseline. Thus default-native failures do not establish a WALNUTS robustness or efficiency advantage here. Initializers and implementation/compiler stacks differ; actual full-fit target calls are the primary metric, not elapsed end-to-end time. Native calibration cost25,398,846 gradients is separately reported rather than selectively charged to native, since WALNUTS settings also benefited from earlier research. Equal bounded WALNUTS metric/acceptance calibration and model-rewrite/approximation controls remain outstanding; this small exposed benchmark alone cannot establish an application. Sources, all28 fits, independent diagnostic replay and verified local archive are indexed by GP-REPAIR-COMPARISON-RESULT.md in STUDIES/usefulness_search_v1/metric_blocks.

### Equal-configuration WALNUTS GP calibration fails fresh all-fit gate (2026-10-30)

WALNUTS received six configurations (auto/dense metrics crossed with acceptance0.8,0.9,0.99) on two new calibration seeds, matching native's configuration/fit budget. Actual calibration calls were24,483,779 for WALNUTS versus25,398,846 for native. Dense0.9 was selected among settings qualifying both seeds, at474.29 gradients/minimum bulkESS; dense0.8 failed both calibration fits. An isolated acceptance-parameter driver passed exact original/omitted/explicit0.8 draw/call/divergence/revision replay for both metric modes. A missing research feature and an invalid shortened warmup schedule were repaired with failed attempts preserved. On eight further fresh seeds, selected WALNUTS and native low_rank0.99 each qualified7/8 fits, all with zero retained divergences. Native seed946500005 had rank R-hat1.01138; WALNUTS seed946500006 had minimum bulkESS321.95 and tailESS127.05, both for length scale rho. The frozen all-fit rule therefore withholds aggregate efficiency credit; no bad seed is dropped and calibration performance is not substituted for validation. This does not promote either workflow or establish usefulness. The earlier default-workflow comparison remains unchanged. All28 fits, diagnostic replay, source snapshots, binaries and failures are preserved in gp_wal_selected_archive01; see GP-WAL-SELECTED-RESULT.md in STUDIES/usefulness_search_v1/metric_blocks.

### Posthoc GP lower-tail transition diagnosis (2026-10-30)

All eight selected WALNUTS fits were replayed with read-only transition diagnostics; all draws, actual calls, divergences and algorithm revisions match exactly, and per-transition counts reconcile with retained telemetry. In failed seed946500006, chain index1 remained below its fit's empirical5% rho quantile for159 draws (retained indices309..467). This was not an unchanged-state freeze: the longest unchanged stretch was4 transitions. During the excursion146/159 transitions stopped at reverse-coarsening rejection, versus189/1841 elsewhere in the same chain. Mean built leaves fell from35.62 to10.59 and mean macro trajectory length from3.592 to1.068. The fixed step was0.1008508; dense-mass condition number2259.4. This posthoc endpoint-based association suggests a bottleneck but does not establish cause or justify deleting the reversibility check. The failed validation remains failed. A relevant new prior-art source is Tran, Kleppe and Bou-Rabee (2026), Locally adaptive step sizes for Hamiltonian Monte Carlo methods, arXiv:2610.16506, which studies alternative error measures for reversibility failures. Its public implementation is pinned at f2a90e06195f4a5f38cb017e16f7ff1136d5be58 for review, not executed. Next work must audit criterion/selection correctness and actual evaluation cost before fresh posterior testing. See GP-TAIL-REPLAY-RESULT.md and gp_tail_replay_archive01 in STUDIES/usefulness_search_v1/metric_blocks. No algorithm novelty or practical-usefulness result is established.

### RKNF reversible-leaf feasibility and independent tolerance tuning

An independent mathematical screen of the published symmetric embedded RKN flow-error criterion retained reverse-coarser rejection and counted every extra midpoint gradient. Matched-refinement-pressure calibration followed by 8192 fresh exact stationary phase points per target produced RKNF/endpoint-energy accepted-normalized-jump per call ratios of 0.7188 (Gaussian), 0.6004 (banana c5; 95% paired bootstrap interval [0.5919,0.6096]), and 0.7644 (funnel). A second frozen experiment gave both criteria nine tolerance candidates on 4096 independent calibration points and used 16384 fresh validation points. Ratios were 0.6666, 0.7015 [0.6979,0.7055], and 0.7284, respectively. Both advancement gates failed. Selected tolerances on banana and funnel were upper grid boundaries, so the negative claim is limited to the tested range and macro lengths. Reversibility checks passed; fewer reverse rejections did not compensate for gradient overhead. These leaf MH surrogate results do not establish full-chain ESS or practical application performance, and the criterion is prior art rather than a novel contribution. Evidence and source hashes are in RKNF-LEAF-RESULT.md and the locally verified 100-member rknf_archive01 (SHA256 838caee2c9fdb49e303e0c8ffeb850cf76030e753899c8b8f0eecac2555a48eb); no off-device archive claim is made.
