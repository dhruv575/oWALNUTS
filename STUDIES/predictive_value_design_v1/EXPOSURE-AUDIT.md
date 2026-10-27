# Data exposure audit and next predictive-value design

Read-only source/history audit2026-10-27. No new forecasts, fitting, acquisition,
AWS calls, score calculation or outcome-selected windows. This is a design note,
not a preregistration authorizing execution. Paths below refer to repository main.

## The archived real tail is development data

WP97 `STUDIES/pool_confirm_v1/protocol.json` fixes N250, ticks0..100,
conditioning on first250+t returns. Its real file SHA256 is
6ba1ba429bc4dc742aeccf64f696d38e022b89e9e2597f096d721101c2908487.
The same682-value file is reused from WP88. Indexing matters: after conditioning
on350 observations, the next return is zero-based y[350]; after the already
available prediction targets through y[350], y[351:682] contains331 later values.
These may be unused by WP97, but are not a clean new holdout across this project.

`STUDIES/online_sv_quote_v2/real_data.py` reconstructs all682 values from the72
`prepared/originNN-neither.json` windows in
`STUDIES/market_uncertainty_v1/artifacts/sv-historical-rolling-v1/evidence.zip`.
Each window has256 values; windows advance6 half-hour observations and overlap250.
Their union covers every index0..681. Thus every proposed tail value was already
an input to previous posterior fits. The original training-origin timestamps span
2026-09-16 16:00 through2026-09-30 20:30UTC. These are label origin timestamps;
actual return availability follows the next bar and the archived timing convention.

The archive `prepare.py:36` specifies72 forecast origins from2026-09-22 00:00UTC
to2026-09-30 21:00UTC in3-hour steps. `report.py:41-60` matches those origins to
`log_bar_close_return` labels and scores forecasts. Relative to reconstructed
array start, these labels are indices256+6*i, i=0..71. Indices256..676 for i0..70
are inside the682-value file; last label682 is just beyond it. Of the proposed
y[351:682] tail,55 values (indices352,358,...,676) were already forecast labels.
The rest were still prior training inputs and exposed acquisition data.

The historical `RESULTS.md` states all72 evaluation origins had usable labels
and forecasts. Its archive entered history in commit79de971f on2026-10-04;
WP88 reconstruction appeared later in51daf883 on2026-10-26. Separately,
`artifacts/marked-sv-rolling-v1/RESULTS.md` documents reuse of all72 no-flow fits
and new pooled/marked-activity comparisons on that same history. This is direct
counterevidence to calling the later WP97 tail fresh, not merely failure to find
an exposure record. A retrospective tail screen remains useful if labeled so.

`artifacts/historical-september-acquisition-v1/RESULTS.md` archives1440 September
half-hour bars and explicitly labels September retrospective development, with
September22–30 already an exploratory evaluation segment. Do not relabel another
part of this acquisition as unseen merely because WP97 did not consume it.

October is not an automatically untouched replacement. The frozen protocol inside
`artifacts/sv-october-validation-terminal-v1/config-frozen.json` already declares
32 origins at3-hour spacing over October1–4 and64 fits; terminal `execution.json`
and `reports/` exist. Its own scope acknowledges prior live October receipt
observations. This audit did not read new per-origin outcomes or exhaust every
untracked external data source, so it cannot certify any existing October tail.

## What would count as a cleaner temporal holdout

Prefer a future acquisition window starting after the final predictive protocol
is committed, with an immutable cutoff and no access to its target labels until
forecast records are sealed. Historical context before the cutoff can initialize
the model; only causal data available at each origin may enter later updates.
Freeze instrument, bar construction, timestamps/receipt rules, missing-data policy,
training window, horizon, priors, K, backend, baseline settings, score definitions,
origin schedule, failure denominators, and analysis code before acquisition.
Maintain a data exposure manifest linking raw hashes, timestamps and all known
uses. A previously acquired later segment can only be called held out after a
separate comprehensive access/use audit, not this bounded scan.

Bar-close returns are not receipt-time midpoint returns, executable quotes,
option exposure or profits. The historical zero-publication-lag assumption must
not silently become a live-availability claim. Consecutive forecasts share inputs;
use time-block/stream uncertainty and retain all intended origins rather than iid
coverage confidence intervals or selecting only successful forecasts.

## Fresh synthetic stage if the retrospective screen warrants it

Generate new independent streams only after a separate plan freezes model,
metrics, sample count and seed namespace. Fresh sampler seeds on WP84 seed84084
are not fresh data. `online_sv_quote_v1/simulate.py` shows84084 and1100 returns
were reused by WP88/WP93/WP97. WP96 also deliberately reuses paired control/shock
realizations; its precision seed99271021 changed sampling, not the input stream.

A bounded candidate design is8 independent data replicates for each of two fixed
regimes (matched stationary SV and a predeclared shift), N250 initial context plus
250 forecast origins per replicate. Shared pre-shock innovations may pair regimes,
but replicates—not individual ticks—are the independent units. This is a design
proposal, not a chosen budget or seed allocation. Add a separate fixed
misspecification regime only if scientific purpose/budget is specified before
outcomes; do not choose cases after looking at errors. Freeze distinct data,
initialization, sampler and any predictive-noise seed namespaces; check exact
base/derived collisions against repository manifests. Keep truth inaccessible to
the forecasting algorithm and avoid using truth as a posterior draw reference.

Primary predictive-value comparison: full-return90% interval score against fixed
causal simple baselines on the same next-return observations. Report coverage,
width, lower/upper misses, PIT and conditional diagnostic plots as secondary;
predeclare any log-score integration and numerical checks if used. Prespecify
failure penalties/reporting and all planned origins. Do not optimize K, prior,
window or baseline smoothing on the evaluation trajectories. Distinguish model
misspecification from finite inference accuracy and from numerical quadrature.

## Minimal independent reference strategy

Predictive calibration uses realized next returns, not agreement with another
sampler. Independent posterior fits are a limited audit of inference error.
Before outcomes, choose a deterministic sentinel grid spanning startup, steady
state, immediate post-shift and late post-shift. A feasible initial audit is12
sentinels spread over fixed replicates/regimes; it cannot certify unreferenced
ticks. At these exact windows, run a separate established engine (e.g. validated
CmdStan or nutpie translation) with fresh independent chains and the identical
posterior target, not another warm oWALNUTS continuation. Recheck target/log-gradient
agreement and priors/parameterization before comparisons. Freeze draws, warmup,
reference diagnostic thresholds and any fixed bounded escalation in advance.

Audit globals mu/log_sigma/beta, h_last, and predictive CDF/quantile functionals;
record rank R-hat, bulk/tail ESS, retained divergences and MCSE. Predictive
innovation must not disguise slow latent/global mixing. Do not silently discard
flagged chains, substitute a conveniently passing reference, or remove failed
sentinels from denominators. Compare endpoints with uncertainty from both arms
and quadrature error; shared-model reference agreement is not calibration.

For matched synthetic data, use a separately designed posterior simulation-based
calibration study if parameter calibration is needed: replicate datasets, exact
conditioning targets, independently generated rank randomness and adequate
reference diagnostics. Fixed-truth coverage across one dependent stream is not
SBC. Independent reference audit and fresh realized-return score evaluation answer
different questions and should remain separate in the eventual report.
