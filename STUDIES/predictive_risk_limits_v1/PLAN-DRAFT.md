# Stored E64 predictive-return risk limits

Status: pre-outcome draft. This is retrospective exploratory reuse of E64's fully
inspected April/May/June2026 data, fits and posterior draws, not a fresh holdout,
confirmatory trading test or deployment qualification. No market acquisition,
new sampler draws, model tuning or outcome-selected origin subset is proposed.

## Fixed question and interpretation

Do full posterior predictive P5/P95 return limits improve realized pinball loss
and tail coverage versus the unchanged rolling250 and EWMA Student-t5 forecasts?
Use log-return inventory-risk proxies: long loss L=-r, limit Q95=-q05; short loss
L=r, limit Q95=q95. Score rho_.95(L-Q)=(.95-I[L<Q])*(L-Q), equivalently return
pinball at .05/.95. Underprediction receives19 times the marginal penalty of
same-size overprediction. Do not clip negative limits to zero. Strict exceedance
is r<q05 for long risk and r>q95 for short risk; report the signed exceedance-rate
minus.05 as well as counts. Exact equality is not an exceedance.

These are log-return risk limits, not dollar inventory losses, executable quotes,
fills, fees, inventory-control actions or P&L. Finite Student-t logreturns need
not have finite exponential price moments: conditional t5 tails already preclude
expected exp(r) loss/utility claims. Realized finite-label pinball is finite, and
the fixed finite stored-draw mixture has finite expected absolute logreturn;
no unproved integrability claim is made for the unrestricted posterior hierarchy.

## Fixed panels and artifacts

All3 mandatory E64 months and all4,368 origins remain: April1440, May1488,
June1440. Use every saved candidate draw, four chains x400 x4 float64 components
[mu,log_sigma,beta,h_last], with equal posterior weights and no thinning/pooling.
Use all24 original independent references, four chains x4000 x4, at their fixed
E64 ticks. Ops metadata inventory found4,368 candidate files (224,200,704 bytes)
and24 reference files (12,291,072 bytes) with those exact NPY schemas.

Original archive SHA256:
da1e3025d746e6b7984fef03c7bf55afeb6963274edba46f697aaac80c993f6d.
Bind exact per-file hashes and source records before use; parse the same bytes
that were hashed. Baseline distribution parameters are reused from E64's saved
per-origin fit records, never refitted or selected. Compute q_p=location+scale*
t5_ppf(p), p=.05,.95, using fixed SciPy t5 quantiles. Recover observed next-return
labels with the already frozen E64 causal acquisition mapping and validate its
sealed original bytes. No other period, asset or baseline is introduced.

## Unchanged numerical engine

Use the reviewed ConfiguredReturnCDF with explicit exact_t5 backend and all
stored draws, rho.95 and nu5. For each draw, predictive latent logvariance has
mean mu+.95*(h_last-mu), innovation SD exp(log_sigma); Student-t return location
is beta. Retain GH64 andGH128, chunk512 and64MiB cache per rule. Use a separately frozen explicit (.05,.95) root wrapper, without global mutation.
P50 is neither computed nor scored. A deterministic fixture must match the two
tail roots from the inherited (.05,.5,.95) method before outcome arithmetic.
No conditional-median shortcut or sampled future innovations.

Reuse dynamic bracketing (at most61 expansions) and Brent roots xtol=rtol=1e-12.
Require finite ordered roots and each rule's root CDF residual<=1e-8. Primary
reported roots are GH128. Preserve the existing numerical acceptance formulas:
max_p |F64(q128_p)-p|<=1e-6 and max_p|q64_p-q128_p|/(q128_.95-q128_.05)<=1e-6,
for p=.05,.95, with finite strictly positive denominator. These are the existing
one-direction cross-CDF check plus both rules' own residual checks; do not
silently introduce a different gate or reduce nodes to meet budget.

At each of the24 fixed reference origins only, evaluate the existing predictive
CDF/density module at each distribution's own P5/P95. Preserve chain/draw axes.
Quantile delta MCSE is chain-aware MCSE of mean per-draw CDF contribution divided
by predictive density at that root. Report candidate-own and reference-own MCSE,
signed endpoint differences, and numerical availability separately. No new MCSE
gate, adaptive budget, reference replacement or origin dropping is allowed.

## Frozen decision summaries

Both long and short pinball endpoints are mandatory, separately reported per
month against both baselines; positive advantage means baseline loss minus SV
loss. Report all12 month/tail/baseline comparisons, with per-month paired circular
bootstrap intervals using10,000 draws and24/48/96-bar blocks,48 primary. Use one
fixed month-specific stream of bootstrap indices shared across every arm/tail;
ops reserves distinct seeds before any RNG consumption. No multiple-comparison
or family-wise success claim. Daily means, cumulative advantage and leave-one-day-
out means are fixed secondary summaries. No selected winning tail or baseline.

Report quantile levels/widths, pinball means, strict exceedance counts/rates and
signed differences from5%, plus paired exceedance differences with the same block
intervals. Coverage alone is insufficient: excessively broad limits can cover
while imposing unnecessary inventory constraints. Origin-weighted overall means
are descriptive only, with no pooled CI or independent-month meta-analysis.
Adjacent markets, cross-month initialization overlap and rolling250 windows
remain serial-dependence limitations. This reuse is also exposed to the prior
E64 model/result inspection; no fresh-market discovery language is appropriate.

Preserve all13,104 arm-origin slots and two tail endpoints each. Any missing
required quantile/score makes the corresponding full-panel comparison null;
retain available counts and explicit unavailable/interrupted/not-started rows.
Keep numerical failures, original baseline failures and reference precision
failures; no retries or changed tolerances. Reference precision failure need
not erase an otherwise valid candidate forecast/primary pinball score.

## Bounded existing-artifact compute queue

1. Source/schema/hash admission, then fixed literal full-size1600-draw candidate
   and16000-draw reference numerical timing/fixture check, no E64 values. Freeze
   exact process layout and resource caps before any stored-data arithmetic.
2. Twelve persistent one-core arithmetic shards on cores0 through11, BLAS threads1.
   Canonical month-major origin index modulo12 fixes assignment before outcomes.
   Quantiles and preserved baseline limits/labels have immutable per-origin rows.
3. Drain all candidate shards; use twelve one-core reference shards, canonical
   month-major reference index modulo12 (two each), including candidate/reference
   own-tail precision diagnostics.
4. Produce frozen monthly ledgers/summaries and descriptive aggregate, archive
   checked evidence, then hand the productive host to the next reviewed queue.

Proposed whole envelope3600seconds internal/3720external,8GiB sampled owned RSS,
1GiB output. Candidate phase 2700 seconds, including baseline/label checks inline;
reference/precision phase 600 seconds aggregate (60 seconds per reference origin),
report phase 120 seconds. Twelve concurrent literal full-size readiness shards
run under a separate 600-second engineering envelope before production admission.
Per-origin candidate numerical cap10seconds; no cap-based subset or reduced
precision. Existing E62 full-summary timing around.66seconds at1600 draws suggests
fixed parallel arithmetic may fit, but only the fixed literal readiness establishes
feasibility. If readiness cannot fit, record that and seek a separately reviewed
operational plan before touching E64 quantiles; do not silently extend budgets.

Parent owns AWS lifecycle. User's standing preference is to keep the host
productive across reviewed studies, not routinely stop it after this experiment.
No automatic study-end shutdown belongs in this runner. Process deadlines and
resource cleanup still apply to this bounded job.

Measured costs are quantile-only postprocessing of cached draws, not combined live
inference/update latency. Do not add archived inference timing and label that sum
a measured end-to-end refresh. No additional metrics beyond the frozen long/short
pinball, exceedances, limit levels/widths and diagnostic precision are introduced.
