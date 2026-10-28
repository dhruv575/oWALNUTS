# Bounded decision arithmetic and readiness contract

Draft before any E64 decision outcome calculation. E66 remains unchanged and
uninspected. The analytic fixtures and fixed literal timing measurements are
engineering inputs to this contract, not empirical evidence.

Use the exact existing t5 CDF backend and GH64/GH128 future-volatility rules.
Integrate exp(r) times each posterior draw's predictive CDF on [-log(1e10),0]
with SciPy quad_vec: max norm, epsabs=1e-8, epsrel=0, gk21, workers=1,
32MiB adaptive cache and subdivision limit512. The per-draw calculation retains
chain axes and permits direct functional-mean MCSE at the 24 reference spots.
There is no quantile-density division in this mean-functional MCSE.

The exact parameter-only split formula is in bounded_loss.split_points:
beta quantiles0/.1/.5/.9/1, closest negative beta, median beta plus/minus
0.1/1/10 times median conditional return scale, and a fixed geometric grid
-log(1e10)*10^-k for k1..10. Keep only strict interior points, deduplicate and
sort. This resolves narrow endpoint layers in deterministic fixtures; it does
not prove a universal quadrature error bound.

Require finite per-draw integrals in [0,1], successful outer integration with
estimated max-component error <=1e-8, and GH-rule mean agreement <=1e-8.
The primary mean uses GH128. Report the max per-draw GH difference as a diagnostic,
and whether the two GH means choose different actions. Also flag when distance
to c is no greater than the estimated outer error plus omitted-tail bound plus
GH mean difference. These flags describe numerical ambiguity, not certified
action accuracy. Only the omitted-domain contribution <=1e-10 is rigorous.

Saved t5 baselines use the same bounded-domain integration and split rule with
their exact frozen location/scale and no future-volatility mixture. They are
not refitted. Realized downside uses -expm1(r) only for nonpositive r, avoiding
positive-return overflow; conversion cost remains exactly0.0005.

Primary empirical comparison: per-month realized bounded decision cost of SV
versus EWMA. Secondary decision comparators: rolling t5, always retain and
always convert. Forecast mean squared-error comparisons versus both t5 controls
are secondary mechanism checks. Report all six comparisons per month (18 total),
with no familywise/pass-count claim. Three new frozen bootstrap seeds drive
10,000 paired circular resamples per month with24/48/96 blocks,48 primary.
Preserve full denominators, all daily/cumulative/leave-one-day-out summaries,
conversion rates and all numerical failures. No threshold or comparator tuning.

Use all4,368 exposed E64 origins and24 original references. Preserve1600
candidate and16000 reference draws; no thinning or new sampling. Candidate
functional arrays need be retained only at the24 predeclared reference ticks;
those exact arrays supply candidate MCSE without rerunning integration.

One local1600-draw literal completed both GH rules in3.07seconds; the matched
16000-draw literal took26.32seconds. Each rule made378CDF evaluations. These
single-process laptop measurements are sizing evidence only, not host throughput.
Both outputs are preserved under main target/bounded-loss-literal*-20261027.json.

Before historical arithmetic, run a separately frozen twelve-way literal
readiness under a600-second outer deadline,8GiB aggregate RSS and1GiB output.
Each shard must exercise the full1600/16000 shapes and recorded baseline path,
functional MCSE, fixed policy scores and complete/partial accounting fixtures.
No market loader or E66 inputs are allowed. Require source/runtime binding and
all process groups drained; preserve any failed readiness without silent retry.

Proposed production layout: twelve persistent one-core candidate shards by
canonical month-major index modulo12; drain; twelve reference shards with two
fixed reference origins each; drain; three monthly reports. Each candidate or
baseline forecast integral has a30-second arithmetic deadline, and each reference
integral has a120-second arithmetic deadline. These are not hard full-origin
deadlines: array persistence, precision, input reads and binding verification
are covered by the whole worker/phase envelope. Phases2700/600/120seconds within3600
internal/3720external,8GiB aggregate,1GiB per worker and1GiB output. Startup/JIT
is recorded outside individual-origin clocks but inside worker deadlines.
No shutdown action belongs in the experiment; host scheduling is parent-owned.
