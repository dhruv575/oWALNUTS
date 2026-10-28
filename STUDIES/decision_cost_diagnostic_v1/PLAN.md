# E68: exposed-data decision-cost diagnostic

This is exploratory arithmetic on all 4,368 sealed E67 origins, selected after
seeing E67's near-universal conversion rates. It is not fresh confirmation.
No new posterior draws, market access, fitted parameters or changes to E67.

Before reading per-origin outcomes here, fix costs at 1, 2, 5, 10, 20, 50,
100 and 200 basis points of endowed notional. Retain when forecast bounded
downside mean <= cost; otherwise convert. Report every month, cost and arm,
with mean realized cost, conversion rate, disagreement with SV, and paired
advantage against EWMA, rolling t5, always-retain and always-convert. No chosen
winner, confidence intervals, tuning, or significance claims. Costs are
hypothetical sensitivity values, not estimates of execution costs.

Also verify the exact identity: integrating policy cost over c in [0,1]
gives m^2/2 + (1-m)y. Therefore baseline minus candidate integrated cost equals
half their squared-error difference. This exposes why an averaged decision
metric can simply restate forecast accuracy, rather than add economic evidence.

Verify each input row against E67's sealed ARTIFACTS.sha256 and require exact
month/tick/arm coverage, finite labels and means, successful source status and
agreement with stored original realized downside. Output source/input hashes.
Run fixed arithmetic on AWS with bounded memory; this tiny diagnostic cannot
productively saturate 16 cores. Do not repeat it merely to raise utilization.
Next research must define a self-financing decision and credible execution
contract before a fresh evaluation; do not optimize this cost grid for reuse.
