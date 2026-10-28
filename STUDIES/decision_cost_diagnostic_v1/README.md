# E68: exposed-data decision-cost diagnostic

The E67 policy comparison is sensitive to the hypothetical conversion cost.
At 10 basis points SV and EWMA disagree much more often, and the SV point
estimate is better in all three months. This is an exploratory observation,
not an independently confirmed advantage or a reason to choose that cost.

All 4,368 rows were verified against the sealed E67 file manifest. No rows,
model fits or forecasts were replaced. All eight costs fixed in PLAN.md are
reported below. Positive values mean EWMA realized cost minus SV cost, in
millionths of endowed initial notional; these are not portfolio returns.

| Cost (bps) | April advantage | May advantage | June advantage | April disagreements | May disagreements | June disagreements |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | -2.659 | -0.936 | 0.236 | 125 | 134 | 3 |
| 10 | 82.500 | 17.744 | 6.130 | 364 | 208 | 197 |
| 20 | -5.029 | 1.070 | 24.600 | 10 | 1 | 98 |
| 50 | 0 | 0 | 0 | 0 | 0 | 0 |
| 100 | 0 | 0 | 0 | 0 | 0 | 0 |
| 200 | 0 | 0 | 0 | 0 | 0 | 0 |

The complete JSON retains all arms, conversion rates, fixed controls and input
hashes. No inferential intervals or significance claims were planned here.
The 10-bps result was found after the original outcomes were known; it is not
a fresh test. An economically grounded cost must come from the execution
contract, not from the most attractive row of this table.

The integrated-cost check also confirms an important limitation: averaging
this policy's cost uniformly across all thresholds [0,1] yields exactly half
the squared-error improvement. It supplies no additional economic validation.

## Validation and interpretation

The three deterministic tests pass. AWS ran the sealed-row diagnostic using
system Python. A separate local run read the independently preserved archive:
source identity and all input hashes agree, all nonnumeric fields agree, and
the largest numerical difference is 1.0843e-19 (20 floating-point fields).
Differences are consistent with cross-platform elementary arithmetic rounding;
exact-byte output equality is not claimed. No sampling or integration was run.

E67's 12 numerical/reporting tests also pass in its existing pinned AWS Python
environment after the research branches were merged. The local default Python
passed 10 and failed two backend tests because Numba is absent; no dependency
was installed or scientific tolerance changed to hide this environment gap.

The next economic contract must include upside, self-financing inventory,
execution and costs. The repeated-endowment downside-only diagnostic cannot
establish an executable AMM strategy. Preserve this result as a diagnostic;
do not tune a strategy on it and then call this data a holdout.
