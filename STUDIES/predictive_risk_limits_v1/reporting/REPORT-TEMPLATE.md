# E65: Retrospective predictive-return inventory-risk limits

Status: report structure prepared before terminal evidence. No interim outcomes
were inspected. Populate only from the verified, sealed campaign packet.

## Scope and completion

This reuses the already inspected E64 April, May and June 2026 panels. It is an
exploratory historical risk-limit comparison, not a fresh holdout, executable
quote test, dollar-loss estimate or profitability result.

Record all 4,368 origins, 13,104 arm-origin slots, 24 independent-reference
origins and 27 operational jobs. Distinguish numerical availability, complete
execution and complete denominator accounting. Preserve every failure.

## Twelve mandatory paired pinball comparisons

For each month, report both long and short risk against rolling Student-t5 and
EWMA Student-t5. Positive values mean baseline pinball loss minus SV loss.
Display every mean and primary 48-origin block interval; retain all 24/48/96
intervals, daily means and leave-one-day-out results in the evidence packet.
Do not select a winning side, baseline, month or block length.

## Limits and exceedances

Report each arm's mean limit, mean interval width, pinball mean, strict
exceedance count/rate and signed deviation from 5%. Report the prespecified
paired exceedance differences and intervals. Coverage alone does not establish
useful limits; the asymmetric pinball loss penalizes underprediction nineteen
times as much as equal-sized overprediction. Negative limits remain unchanged.

## Numerical agreement and reference precision

Audit both GH rules' root residuals, cross-CDF and normalized endpoint gates.
Retain all 24 reference comparisons and per-tail candidate-own/reference-own
quantile delta MCSE, including partial precision failures. Eight reference
spots per month cannot certify the entire path.

## Cost and interpretation

Report actual twelve-shard shared-host runtime, resource peaks and recorded
per-origin postprocessing costs. These measure quantile-only arithmetic on
cached draws, not a combined live inference/update/quote pipeline. Baseline
parameters were reused without optimization.

Long loss is minus log return; short loss is log return. These are finite-sample
log-return risk proxies. Student-t log returns do not justify finite expected
exponential-price loss or utility. No inference about fills, fees, adverse
selection, inventory policy or P&L follows from this study.

The three adjacent months and rolling windows remain dependent. Aggregate
origin-weighted means are descriptive; there is no pooled interval, familywise
success claim or independent-regime replication claim.

## Provenance

Record authorized manifest hash, source/readiness bindings, archive hash and
verified file count, bounded evidence inventory and raw artifact locations.
AWS lifecycle follows the user's preference to keep the host productive across
reviewed studies; no study-end shutdown is part of this experiment.
