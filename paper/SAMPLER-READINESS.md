# Sampler readiness: retained negative and development results

These studies extend the evidence ledger, not the existing 44-comparison figure
bundle. They do not establish an original algorithm contribution or profitability.

## Finite-resolution candidate: synthetic validation only

The exact-return target's tie pathology motivated a different observation
model: a joint latent log-price process observed through finite cells. Its
likelihood is a joint event probability bounded by one, so proper priors give
a finite positive posterior normalizer under the stated observation mechanism.
This argument does not establish that exchange transaction prices are rounded
measurements of a continuous latent price. Historical data semantics remain
an admission gate, and the former target's empirical claims do not transfer.

An independent analytic implementation and Stan autodiff agreed on sixteen
finite density/gradient fixtures through 503 dimensions. A T1 synthetic
posterior was compared with 74,311 independent prior-rejection draws. Both
NUTS and a separately implemented elliptical-slice/conditional-price method
passed its diagnostic and mean-agreement checks. This is a single reference
fixture, not simulation-based calibration.

On four deterministic stress fixtures (T=12 or 250, log-price cell widths
0.001 or 0.00001), NUTS passed all coordinate diagnostics. The first independent
method failed its rejection cap in fifteen of sixteen chains. A valid tighter
cell envelope removed these execution failures, but all four fits still failed
core-coordinate diagnostics. Separating scalar hyperparameter updates and
16-innovation elliptical blocks then passed three of four fits, including both
T250 cases. The narrow-cell T12 case still flags mu, log_sigma and z[11].
No mean discrepancy in the blocked comparison exceeded the fixed descriptive
threshold of four combined standard errors (maximum 3.900 across the panel).

This supplies limited independent-method support on two long synthetic
fixtures. It is not proof of general posterior fidelity, a fair efficiency
ranking, market calibration, decision value or profitability. The failures
remain in the denominator. Revisions used new declared seeds and did not extend
failed chains. These are exposed development cases, not untouched confirmation.

Sources: [model specification](../STUDIES/amm_accounting_v1/FINITE-RESOLUTION-MODEL.md),
[synthetic kernel checks](../STUDIES/amm_accounting_v1/PRICE-CELL-CONTRACT-RESULTS.md),
[blocked comparison](../STUDIES/amm_accounting_v1/evidence/price-cell-slice-v3-20261028/RESULTS.md),
[observation audit](../STUDIES/amm_accounting_v1/OBSERVATION-SEMANTICS.md).

## Warm-start effort tradeoff

The paired E72 study planned 12 monthly paths: three months, two external seed
replicates, and warm budgets K=400 and K=1600. Ten paths completed. Both January
K=1600 paths reached the declared one-hour limit and were not extended. Preserve
90 available scores out of 96 planned slots and 42 available pairs out of 48.

K=1600 reduced estimated log-density and PIT Monte Carlo error in all 42
available pairs. Absolute reference discrepancy improved in 28/42 log-density
and 30/42 PIT pairs. Completed paths cost approximately four times as much.
This supports a precision/cost tradeoff, with a material bounded-runtime failure;
it does not support universal accuracy improvement or real-time readiness.

Source: [E72 results](../STUDIES/warm_budget_factorial_v1/RESULTS.md), including
all-reference and reference-passing analyses and versioned archive verification.

## Specialized same-target transitions

The original augmented elliptical-slice specialist and its interwoven variant
completed all 192 chains across 24 fixed market windows. All 48 four-chain fits
failed at least one declared diagnostic gate. Scale and terminal-volatility
coordinates were flagged on all 24 windows for both methods. Interweaving
improved the mean-level coordinate substantially, but that improvement was
insufficient to establish full-posterior fidelity. Predictive agreement must
not override these flags; Monte Carlo errors can themselves be unreliable under
poor mixing.

Source: [market results](../STUDIES/market_uncertainty_v1/sv_hybrid/MARKET-RESULTS.md).

A subsequent fixed 16-state centered-path block update passed all 254 diagnostic
flags on one literal synthetic development fixture. Its predictive estimates
were compared with the preserved independent reference, with separate Monte
Carlo errors. This is developmental evidence only. The separately frozen
24-window market test completed: 10/24 fits passed all coordinate gates and
14 remained flagged, chiefly scale mixing. All 96 chains completed; maximum
absolute log-density discrepancy on the 22 passing references was 0.018963.
The substantial improvement remains insufficient for full posterior readiness.
See the [complete market results](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-MARKET-RESULTS.md).

A separately frozen fourfold-effort panel subsequently passed all 24 fits, with
735.90 seconds of campaign time versus 188.85 seconds. All paired density/PIT
MCSE estimates decreased, while absolute reference discrepancies improved in
17/24 and 18/24 pairs respectively. This establishes a diagnostic/cost result
on exposed windows, not universal predictive improvement or algorithm superiority.
See the [precision results](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-PRECISION-RESULTS.md).

The subsequent same-target NUTS panel passed all 24 fits with zero divergences
in 196.46 seconds, including per-fit compilation. Its median density MCSE was
0.001113 and maximum discrepancy on passing references was 0.003133, both lower
than the blocked specialist's aggregate metrics. This is negative evidence for
a specialist efficiency advantage on this workload, not a universal ranking or
a direct WALNUTS comparison. See the [baseline results](../STUDIES/market_uncertainty_v1/sv_hybrid/MARKET-REFERENCE-RESULTS.md).

Source: [block derivation and development](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-PATH.md)
and [fixed market plan](../STUDIES/market_uncertainty_v1/sv_hybrid/BLOCKED-MARKET-PLAN.md).

## Model-admissibility warning discovered after the diagnostic studies

The six-path compiled NUTS rolling comparator subsequently completed all paths
and 48 scores. Its path times were 1.33--2.93 times the corresponding WALNUTS
K400 times, but it restarted 1,000 warmup transitions on every update whereas
WALNUTS reused adaptation. None of its 48 retained update fits passed all 254
coordinate gates; ten divergences were recorded across completed updates.
This is numerical implementation evidence, not an accuracy-matched algorithm
claim. The [full result](../STUDIES/market_uncertainty_v1/sv_hybrid/ROLLING-MARKET-RESULTS.md)
retains paired scores, failures of diagnostic gates and the model limitation below.

The [exact-tie derivation](../STUDIES/amm_accounting_v1/POSTERIOR-PROPRIETY.md)
indicates that the current no-flow SV posterior is improper on repeated exact
observations despite proper priors. An audit found 155 affected January windows
and 311 February windows, including reference sentinel 577. The repeated
literal fixture is also affected. This mathematical derivation requires
independent review, but affected diagnostic passes must not be represented as
proper-posterior qualification. The historical flags and failure denominators
remain intact; model admissibility is an additional, separate requirement.

## Implications for the manuscript

A subsequent fixed candidate-budget study used four synthetic paths, each
with three successive shifts and 1,024 warm draws per chain. All twelve
warm/cold pairs passed every coordinate diagnostic, with zero retained
divergences or depth-limit hits. All 24 trace summaries were reproduced.
Three bounded latent-increment CDF functionals also passed diagnostics; the
largest warm/cold mean discrepancy was 2.593 combined MCSEs, and numerical
integration checks passed. Sampling costs remained mixed: wider-cell warm
updates took 10--11 seconds versus 13--14 for cold adaptation/sampling, while
narrow-cell warm updates took 20--21 versus about 11 seconds. Different draw
budgets and precision prevent a general efficiency claim. Shared static
initial states and development-exposed synthetic data limit generalization.
Evidence is in `STUDIES/amm_accounting_v1/evidence/price-cell-repeated-20261028`
and the corresponding `price-cell-repeated-predictive-20261028` directory.

An initial one-shift synthetic comparison used remapped static WALNUTS states
and fresh NUTS fits on identical declared targets. All four pairs passed
coordinate diagnostics, with zero retained divergences or depth saturation;
no coordinate mean difference exceeded four combined MCSEs. The 250-cell warm
routes took about 40 and 79 seconds versus 30 and 26 seconds for cold NUTS.
Timing scopes differ (cold includes compilation and serialization), and no
speed advantage is established. See the complete failure-preserving record in
`STUDIES/amm_accounting_v1/evidence/price-cell-warm-cold-20261028`.

The first native WALNUTS panel for the candidate finite-price-cell model
completed all four synthetic fixtures (27 or 503 dimensions). All 1,060
coordinate diagnostics passed, with zero retained divergences or depth-limit
hits. All-coordinate mean comparisons against NUTS and the independent
blocked-slice control had no absolute combined-MCSE discrepancy above four;
the short narrow-cell slice reference still failed three diagnostics. Original
reports incorrectly pooled warmup and retained diagnostic events; the saved
arrays were reanalyzed without resampling and both versions are preserved in
`STUDIES/amm_accounting_v1/evidence/price-cell-walnuts-20261028`.
This supports limited synthetic implementation agreement, not general fidelity,
market observation validity, warm-state correctness, or a speed advantage.

Keep posterior fidelity, prediction, decision value and profitability separate.
Report the runtime failures and diagnostic failures alongside favorable
development results. The current windows are development-exposed. Any final
comparative claim needs a declared evaluation design, fair computational costs,
and adequate references; any economic claim additionally needs feasible
execution and accounting. Established blocking and elliptical-slice techniques
are controls, not a claimed new inference algorithm.

A separate [tail analysis](../STUDIES/amm_accounting_v1/LOG-WEALTH-OBJECTIVE.md)
derives an obstruction to unbounded posterior-predictive log-wealth objectives
under the current log-normal innovation-scale prior. The derivation still needs
independent mathematical review. Passing sampler diagnostics would not resolve
this integrability issue; pointwise density/CDF evaluation and economic moment
existence are different requirements.

A separate bounded-innovation-scale candidate has a derived posterior-propriety
and absolute-logreturn-moment argument, still requiring independent mathematical
review. Its fixed nine-case synthetic panel qualified both NUTS and blocked
elliptical-slice diagnostics on six T=250 fits (distinct and exactly-two-zero
observations, three caps). All three all-zero T=12 stress comparisons failed
independent-reference qualification. At caps 1 and 2 NUTS also failed every
coordinate diagnostic and hit its depth limit 13,342 and 11,405 times. Zero
divergences did not imply adequate exploration. Full results are preserved in
`STUDIES/amm_accounting_v1/evidence/bounded-multi-20261028`.

Native WALNUTS density/gradient parity passed 108 deterministic bounded-target
cases, but WALNUTS sampling for that candidate is not yet qualified. The candidate
prior cap lacks empirical justification; synthetic successes do not resolve
that modeling choice or establish any economic claim.

An exact beta=exp(mean(h)/2)*b coordinate change subsequently passed 72 independent
autodiff checks and all three all-zero NUTS stress fits' physical diagnostics,
with zero retained divergences/depth hits at the same sampling budget. Raw-trace
diagnostics were reproduced locally. The cap-2 chains reached a much more extreme
latent-volatility region than the earlier failed methods. This supports a
coordinate-coupling diagnosis but still lacks a qualified independent reference;
see `STUDIES/amm_accounting_v1/evidence/bounded-rescaled-20261028`.

The first independent slice control in rescaled coordinates still failed
fourteen of fifteen physical diagnostics at every cap. A separately declared
Gaussian-reference recentering, chosen from an analytical linear tilt and
corrected by the exact density ratio, subsequently passed every physical
diagnostic at all three caps. Its maximum coordinate-mean discrepancies against
the frozen NUTS traces were 1.774/2.517/1.457 combined MCSEs. All failed and
successful chains are retained. This supplies limited independent support for
the three stress fits, without selecting a cap or implying market validity;
see `STUDIES/amm_accounting_v1/evidence/bounded-centered-slice-20261028`.

The first rescaled native WALNUTS panel completed four of nine fits and aborted
five on nonfinite callback evaluations. A captured finite proposal exposed
underflow in physical-scale reconstruction. A direct log-space formula passed
arbitrary-precision and independent Stan checks, followed by native parity.
Its separately seeded fixed nine-case WALNUTS follow-up passed every physical
diagnostic and all eighteen comparisons against the frozen NUTS/slice references,
with no divergences, retained depth hits or recoverable target failures. Maximum
mean discrepancies were 3.886 and 3.539 combined MCSEs against NUTS and slice.
Both failed and successful panels are preserved. This is limited synthetic
implementation evidence, not predictive value or a precision-matched speed claim;
see `STUDIES/amm_accounting_v1/evidence/bounded-logspace-walnuts-20261028`.
