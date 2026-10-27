# Fixed-budget warm precision diagnostic

2026-10-27. A diagnostic on reused WP96 synthetic data and references, with one
fresh paired sampler seed. This is not qualification, a default change, a
market-calibration test, an executable-quote test or deployment work.

WP96 found no qualifying fixed-window policy at K=200. Its frozen-kernel cost
did not rise after the regime shift, reference diagnostics were healthy, and
re-adaptation did not restore accuracy. Post-hoc analytic integration of future
innovation improved accuracy but did not make a policy qualify. This experiment
asks whether increasing a **fixed** number of retained transitions improves
functional precision enough to justify a fresh, broader study, and at what cost.
The Gaussian-chain MCSE diagnostic does not justify adaptive stopping; no
MCSE-based stopping or online budget selection is used here.

## Fixed execution

Six cells, one sampler seed **99271021**, 2,000 updates each:

| Lane | Affinity | Stream | Order |
|---|---|---|---|
| A | cores 0–3 | WP96 shift | K=200, then 400, then 800 |
| B | cores 4–7 | WP96 control | K=200, then 400, then 800 |

Use the **existing** WP96 binary, unchanged library and source at
`9210c9471b2eacc1e1528455720239863bae76f0`; do not rebuild or use current-main
defaults. The binary SHA256 is
`5cbfbe9b7ebbeec525cad92560612a37738a1368233baea6f8bea913d95fb3c8`.
Call its original `warm` mode with N=250, policy `frozen`, save interval 25.
Each cell performs the original 4x1,000/1,000 tick-0 fit and warning-based
initial chain selection, then carries state and frozen tuning as in WP96.
All costs and warnings are retained. The same seed pairs initialization across
K; later states differ, so draws are not treated as independent across arms or
as nested continuation budgets after every tick.

Both input streams and the reference draws are immutable WP96 artifacts. Verify
the binary, frozen source, protocol and data hashes before starting; exact
paths/hashes are in `protocol.json`. The seed audit searches main at
`551419373449338e9e6dbdc07ea3e14fa3646b63` before this plan exists: base seeds
99271021–99271024 and all warm per-chain derived seeds
`99271021*1000003 + 16*t + c`, t=1..2000,c=0..3, have no exact integer matches
in tracked Markdown, Python, Rust, JSON or JSONL files. Search includes a
superset of that derived range, 99271318800000–99271318899999. This is a
diagnostic seed, not a qualification seed.

## Resource and failure rules

The parent must acknowledge this plan before launch. WP97 has completed its
warm timing cells; its reference work continues on cores 8–15. Both studies
record shared-host co-tenancy. Do not infer isolated latency from these runs.
Each lane has four Rust threads; numerical thread pools are constrained to one.

Launch one durable supervisor with a **shared 60-minute hard sampling deadline**
and **1,000,000,000-byte output cap**. It records coordinator and cell PID,
commands, UTC start/end, exit status, affinity and source identity; refreshes
heartbeat status; and terminates its own process groups if either cap is hit.
Cells run once in the fixed lane order. Preserve started partial/failed cells;
do not rerun them or replace their outputs. Later unstarted cells remain in the
planned denominator as budget-missing. Supervisor interruption is recorded,
not silently resumed. Remote output is isolated under
`/home/ubuntu/lanes/warm_precision_diagnostic_v1`.

At prior WP96 costs, approximate warm time per lane is 4+8+17 minutes plus
initialization; the deadline controls actual execution. Raw compact output is
expected well below 100 MB; the cap is conservative. No new reference fits,
parameter variants, data variants or seed additions are authorized by this plan.

## Fixed analysis

Use all saved scored ticks 25,50,...,2000 (80 per cell; 480 planned warm rows),
split at tick 1000 into 40 ticks per half. Tick 0 is described separately and
does not enter accuracy or recurring-update latency. Reuse the corresponding
160 audited WP96 scored reference ticks, retaining their original selected
attempts and original chain identities. All missing/invalid warm or reference
rows count as failures; report availability explicitly.

On each set of compact draws `[mu, log_sigma, h_last]`, with rho=.95:

1. Original-noise quantiles: `h_next=mu+rho*(h_last-mu)+exp(log_sigma)*eps`,
   with the original WP96 `default_rng(9600000+tick)` matrix of shape
   `(4,20000)`, indexing original retained chain identities and the first K
   columns. Quantile sigma is `exp(h_next/2)` with NumPy's original linear
   sample quantile convention.
2. Analytic-mixture quantiles: invert
   `mean(Phi((h-mu-rho*(h_last-mu))/exp(log_sigma)))` at p=.5,.95 and map the
   root to `exp(h/2)`. Use a deterministic bracketing/root solve, finite-input
   validation and checked CDF residuals. There is no added future random draw.

Report original-noise arm versus original-noise reference, original-noise arm
versus analytic reference, and analytic arm versus analytic reference. The
second contrast separates reference-noise changes from arm-estimator changes.
The reference is still finite Monte Carlo output from the same sampler; analytic
integration does not turn it into exact posterior ground truth.

For each stream/K/half and estimator, report descriptive fraction within both
2% P50 / 5% P95 relative-error tolerances with the original WP96 stuck-chain
rule (absolute per-chain median difference >1 for log_sigma or >2 for h_last
from the corresponding reference median counts
as stuck). Report signed mean error, 5th/50th/95th error quantiles, absolute-error
median/p95, original quantile own-MCSE and analytic CDF/density own-MCSE,
retained divergences, chain selection, reference precision and missingness.
One seed cannot satisfy the multi-seed WP96 qualification rule, and descriptive
95% tick accuracy is not a qualification decision.

Own-MCSE uses ArviZ 0.23.4; analytic quantile relative MCSE is mean-CDF MCSE
divided by `q*f_scale(q)`, with `f_scale(q)=2*f_H(2log(q))/q`. It is an
asymptotic diagnostic, not a valid adaptive stopping guarantee. Preserve all
per-tick outputs and package/source/data identities.

Latency: report the original binary's complete target/remap/warm-refresh/state
wall for **all** 2,000 updates per cell (median, P95, P99, maximum), separately
from tick-0 fit and whole-process duration. Missing/error updates are infinite
for deadline summaries. Separately time original-noise and analytic-quantile
arithmetic for each saved scored tick on the same box, pinned to cores 0–3,
after **both new sampling lanes have drained**; no overlap with WP97's official
pooling analysis. This analysis has a separate five-minute cap, retains partial
results and changes no sampler settings. Record quantile arithmetic separately
from MCSE/diagnostic work. For saved ticks report sampler wall plus arithmetic
as a **sum of separately measured components**, not a fused online end-to-end
benchmark; no per-update CDF latency is claimed for unsaved ticks.

## Decision and scope

Use the fixed results to decide whether a higher fixed K and/or analytic
functional estimator merits fresh-seed qualification, or whether another
precision/equilibration diagnosis is needed. Do not change a default or label a
configuration practical merely because it is fast or its MCSE is small.
The same WP96 windows and references are reused after seeing their failures,
and only one new seed is sampled. Accuracy is checked every 25th update and
does not cover the first 24 post-shock ticks. The object is the posterior of a
250-return window under a specified SV model, not a full-history posterior,
return-risk calibration or trading profitability.
