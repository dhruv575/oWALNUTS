# WP84 post hoc: quote error of the warm refresh vs the reference

**Post hoc, not preregistered; exploratory; informs the next study's rule.** Nothing here
changes the frozen WP84 result (`../README.md`): the preregistered rule was not met and the
README may not say "real-time". This re-analysis asks the question that rule did not: how far
is the *quote* a warm refresh produces from the quote the 4 x 20,000-draw reference produces,
in relative terms, and does it stay that way over 100 ticks. Script: `quote_error.py`
(reads the raw draws in `../artifacts/cells`, which are checksummed but not committed).
N = 250 only; the N = 1000 reference failed at admission, so N = 1000 appears in the latency
table only.

## Method

Per tick t = 1..100 and cell, h_next is rebuilt exactly as in `analyze.py` (same eps stream),
sigma_next = exp(h_next / 2), and its P5 / P50 / P95 / mean are compared with the reference's:
relative error = (arm - ref) / ref. The quote is a half-spread proportional to P50(sigma) and
a risk quote proportional to P95(sigma), so the P50 (P95) relative error *is* the spread
(risk-quote) error in basis points per unit of spread: 1 % = 100 bp. Pooled-across-chains
bulk ESS of h_next is `arviz.ess` (split chains, rank-normalised); the arm's own MCSE of
P50(sigma) is `arviz.mcse(method="quantile")` (Vehtari et al. 2021, from the ESS of the
indicator I(sigma <= q)), reported relative to P50. The reference floor is the reference's own
relative MCSE of the same quantities plus an empirical floor, the relative gap between two
independent halves of the reference chains.

**Reference cleaning (post hoc).** At ticks 21, 48, 53 and 87 one reference chain is frozen at a
point far outside the posterior (warmup step collapsed to 1e-6 to 1e-4, log density 2,000 to
5,000 below the other chains, log_sigma at +1.3 to +1.9 against a posterior of -1.85 +/- 0.3,
zero movement, zero divergences). oWALNUTS flagged each one in `ticks.jsonl`
(`WarmupStep { chain: c }`, `SampledLogDensity { chain: c }`, `RHatCluster`); the frozen
analysis did not act on the flags. The script drops exactly the flagged chain at those four
ticks (3 x 20,000 remain), nothing else. The same failure hits the refit arms (census below),
which are reported both as sampled (what a quote engine would have used) and with stuck ticks
removed (what a chain gate would pass). A chain counts as stuck when the median of its
log_sigma draws is more than 1.0 from the cleaned reference's median, or its median h_last
more than 2.0 away; every stuck chain seen sits 3 to 4 units away. The rule reproduces the
sampler's own flags on 100/100 reference ticks and 21/21 stuck oWALNUTS-refit ticks.

## Tables

### Reference floor (ref-N250, cleaned; 100 ticks)

| quantity | rel. MCSE median | rel. MCSE P95 | rel. MCSE max | half-ref gap median | half-ref gap P95 | half-ref gap max |
|---|---|---|---|---|---|---|
| sigma p5 | 0.20 % | 0.28 % | 0.47 % | 0.27 % | 0.68 % | 1.41 % |
| sigma p50 | 0.08 % | 0.11 % | 0.29 % | 0.13 % | 0.35 % | 0.72 % |
| sigma p95 | 0.20 % | 0.24 % | 0.34 % | 0.32 % | 0.83 % | 1.05 % |
| sigma mean | 0.07 % | 0.08 % | 0.29 % | 0.11 % | 0.35 % | 0.81 % |

Cleaned reference: bulk ESS of h_next median 114,664, min 6,263; max R-hat 1.0005. Before
cleaning the four stuck ticks had ESS 7 to 18, R-hat 1.4 to 1.5 and relative MCSEs of 10 %
(P50) to 387 % (P5).

### Stuck-chain census (ticks with >= 1 chain frozen off-target, of 100 per seed)

| arm | seed 84001 | seed 84002 | seed 84003 | total / 300 | ticks with 2 stuck | sampler flagged the same chains |
|---|---|---|---|---|---|---|
| warm50 | 0 | 0 | 0 | 0 (0.0 %) | 0 | none to flag |
| warm200 | 0 | 0 | 0 | 0 (0.0 %) | 0 | none to flag |
| refit | 9 | 7 | 5 | 21 (7.0 %) | 0 | 21/21 |
| cmdstan | 13 | 16 | 10 | 39 (13.0 %) | 2 | n/a (no flags recorded) |
| nutpie | 0 | 0 | 0 | 0 (0.0 %) | 0 | n/a (no flags recorded) |

### Relative error vs reference, as sampled, pooled over 3 seeds (300 ticks)

Median / P95 over ticks of |arm - ref| / ref. P50 column = half-spread error, P95 column =
risk-quote error; the last two columns restate them in bp per unit of spread.

| arm | ticks | P5 | P50 | P95 | mean | P50 err bp/unit | P95 err bp/unit |
|---|---|---|---|---|---|---|---|
| warm50 | 300 | 2.80 % / 9.15 % | 1.16 % / 3.70 % | 2.77 % / 7.58 % | 1.04 % / 3.18 % | 116 / 370 | 277 / 758 |
| warm200 | 300 | 1.51 % / 4.42 % | 0.64 % / 1.83 % | 1.27 % / 3.52 % | 0.49 % / 1.51 % | 64 / 183 | 127 / 352 |
| refit | 300 | 0.68 % / 3.76 % | 0.31 % / 8.31 % | 0.73 % / 996 % | 0.27 % / 1196 % | 31 / 831 | 73 / 99,643 |
| cmdstan | 300 | 0.74 % / 11.18 % | 0.36 % / 9.19 % | 0.74 % / 1.5e6 % | 0.28 % / 7.3e5 % | 36 / 919 | 74 / 1.5e8 |
| nutpie | 300 | 0.64 % / 1.78 % | 0.25 % / 0.71 % | 0.65 % / 1.76 % | 0.22 % / 0.65 % | 25 / 71 | 65 / 176 |

### Share of ticks within tolerance, as sampled (pooled over seeds)

| arm | ticks | P50 <= 1 % | P50 <= 2 % | P50 <= 5 % | P50 <= 10 % | P95 <= 1 % | P95 <= 2 % | P95 <= 5 % | P95 <= 10 % |
|---|---|---|---|---|---|---|---|---|---|
| warm50 | 300 | 44.0 % | 74.3 % | 98.7 % | 100.0 % | 18.3 % | 35.3 % | 78.0 % | 99.0 % |
| warm200 | 300 | 71.3 % | **97.3 %** | 100.0 % | 100.0 % | 40.3 % | 69.0 % | **98.3 %** | 100.0 % |
| refit | 300 | 91.3 % | 93.3 % | 93.3 % | 99.0 % | 64.3 % | 90.3 % | 94.3 % | 94.7 % |
| cmdstan | 300 | 85.3 % | 87.7 % | 89.3 % | 98.0 % | 63.7 % | 84.7 % | 89.7 % | 90.0 % |
| nutpie | 300 | 98.7 % | 100.0 % | 100.0 % | 100.0 % | 71.3 % | 98.3 % | 100.0 % | 100.0 % |

### Same, stuck ticks removed (a chain gate would refuse to quote there)

| arm | ticks | P50 median / P95 | P95 median / P95 | P50 <= 1 % | P50 <= 2 % | P95 <= 2 % | P95 <= 5 % |
|---|---|---|---|---|---|---|---|
| warm50 | 300 | 1.16 % / 3.70 % | 2.77 % / 7.58 % | 44.0 % | 74.3 % | 35.3 % | 78.0 % |
| warm200 | 300 | 0.64 % / 1.83 % | 1.27 % / 3.52 % | 71.3 % | 97.3 % | 69.0 % | 98.3 % |
| refit | 279 | 0.29 % / 0.82 % | 0.67 % / 1.86 % | 97.8 % | 100.0 % | 96.8 % | 100.0 % |
| cmdstan | 261 | 0.31 % / 0.83 % | 0.61 % / 1.80 % | 97.7 % | 100.0 % | 96.6 % | 100.0 % |
| nutpie | 300 | 0.25 % / 0.71 % | 0.65 % / 1.76 % | 98.7 % | 100.0 % | 98.3 % | 100.0 % |

### Chain quality and the arm's own Monte Carlo error (as sampled)

| arm | draws / tick | bulk ESS h_next median (min) | ESS per draw | own rel. MCSE of P50 median / P95 | R-hat <= 1.01 | R-hat max | signed P50 err median | signed P95 err median | signed P50 mean (clean ticks) | signed P95 mean (clean ticks) |
|---|---|---|---|---|---|---|---|---|---|---|
| warm50 | 200 | 285 (52) | 1.42 | 1.81 % / 2.87 % | 42 % | 1.072 | +0.04 % | -0.85 % | +0.12 % | -0.37 % |
| warm200 | 800 | 1025 (644) | 1.28 | 0.90 % / 1.32 % | 93 % | 1.030 | -0.07 % | -0.45 % | -0.07 % | -0.27 % |
| refit | 4000 | 4986 (7) | 1.25 | 0.41 % / 10.39 % | 93 % | 1.542 | +0.10 % | -0.06 % | +0.05 % | -0.06 % |
| cmdstan | 4000 | 5177 (5) | 1.29 | 0.41 % / 11.63 % | 87 % | 2.130 | +0.09 % | +0.16 % | +0.03 % | +0.02 % |
| nutpie | 4000 | 5437 (4110) | 1.36 | 0.38 % / 0.49 % | 100 % | 1.004 | +0.03 % | -0.08 % | +0.03 % | -0.03 % |

### Drift: P50 relative error, ticks 1-25 vs 76-100, per arm and seed (stuck ticks removed)

| arm | seed | mean abs err 1-25 | mean abs err 76-100 | late - early | signed mean 1-25 | signed mean 76-100 | ticks used |
|---|---|---|---|---|---|---|---|
| warm50 | 84001 | 1.51 % | 1.19 % | -0.33 pp | -0.56 % | -0.09 % | 25 + 25 |
| warm50 | 84002 | 1.14 % | 1.22 % | +0.08 pp | +0.25 % | +0.07 % | 25 + 25 |
| warm50 | 84003 | 1.11 % | 1.26 % | +0.16 pp | -0.05 % | -0.00 % | 25 + 25 |
| warm200 | 84001 | 0.84 % | 0.70 % | -0.14 pp | +0.14 % | -0.16 % | 25 + 25 |
| warm200 | 84002 | 0.84 % | 0.83 % | -0.00 pp | -0.16 % | -0.02 % | 25 + 25 |
| warm200 | 84003 | 0.75 % | 0.65 % | -0.10 pp | -0.22 % | -0.10 % | 25 + 25 |
| refit | 84001 | 0.29 % | 0.26 % | -0.03 pp | -0.02 % | +0.09 % | 24 + 22 |
| refit | 84002 | 0.42 % | 0.28 % | -0.14 pp | +0.19 % | +0.04 % | 24 + 24 |
| refit | 84003 | 0.29 % | 0.28 % | -0.01 pp | +0.00 % | +0.12 % | 24 + 22 |
| cmdstan | 84001 | 0.35 % | 0.31 % | -0.04 pp | -0.06 % | +0.02 % | 22 + 21 |
| cmdstan | 84002 | 0.40 % | 0.24 % | -0.16 pp | -0.13 % | -0.12 % | 19 + 22 |
| cmdstan | 84003 | 0.32 % | 0.35 % | +0.02 pp | +0.08 % | +0.04 % | 23 + 22 |
| nutpie | 84001 | 0.32 % | 0.27 % | -0.05 pp | -0.02 % | +0.06 % | 25 + 25 |
| nutpie | 84002 | 0.20 % | 0.31 % | +0.11 pp | +0.05 % | +0.00 % | 25 + 25 |
| nutpie | 84003 | 0.25 % | 0.40 % | +0.16 pp | +0.02 % | +0.03 % | 25 + 25 |

### Latency per tick (wall seconds, pooled over 3 seeds = 300 ticks; tick 0 excluded)

| arm | N | median s | P95 s | max s |
|---|---|---|---|---|
| warm50 | 250 | 0.021 | 0.043 | 0.045 |
| warm200 | 250 | 0.083 | 0.172 | 0.179 |
| refit | 250 | 3.054 | 19.028 | 23.433 |
| cmdstan | 250 | 6.490 | 50.802 | 59.200 |
| nutpie | 250 | 1.098 | 1.493 | 2.630 |
| warm50 | 1000 | 0.267 | 1.925 | 2.032 |
| warm200 | 1000 | 1.074 | 7.403 | 7.759 |
| refit | 1000 | 16.787 | 37.684 | 73.594 |
| cmdstan | 1000 | 41.892 | 218.485 | 228.647 |
| nutpie | 1000 | 4.490 | 5.490 | 206.545 |

(Pooled over 300 ticks, so the medians differ in the third decimal from the frozen table's
median-of-seed-medians. The nutpie N = 1000 max is a single tick, seed 84003 tick 100, 206 s;
its next slowest tick is 7.6 s.)

## Reading

**The floor.** The cleaned reference resolves the P50 of sigma_next to 0.08 % (median tick,
0.29 % worst) and the P95 to 0.20 % (0.34 % worst); two independent half-references disagree
by 0.13 % / 0.32 % at the median tick and 0.72 % / 1.05 % at the worst. Differences below
about 0.5 % on P50 and 1 % on P95 are not adjudicable per tick, and the gated 4 x 1,000-draw
refits sit at exactly that level (P50 median 0.25 to 0.31 %, within 1 % on 98 % of ticks):
a 1 % tolerance is the refits' own noise, not a standard they clear.

**What the warm refreshes meet on >= 95 % of ticks.** warm200 (80 ms): half-spread within
2 % on 97.3 % of ticks, risk quote within 5 % on 98.3 %; within 5 % / 10 % on 100 %. Its
median errors are 64 bp per unit of half-spread and 127 bp per unit of risk quote. warm50
(20 ms): half-spread within 5 % on 98.7 %, risk quote within 10 % on 99.0 %; it meets neither
2 % (74 %) nor 5 % on the risk quote (78 %). Median errors 116 / 277 bp. The arms' own
quantile MCSE predicts this: observed P95-over-ticks P50 error is 2.0 x the median own MCSE
for both K (3.70 % vs 1.81 %; 1.83 % vs 0.90 %), so an in-line 2-MCSE band is an honest error
bar without a reference. The P50 is unbiased (signed median +0.04 % / -0.07 %); the P95 is
biased low by 0.85 % (K = 50) and 0.45 % (K = 200), the usual small-sample bias of an upper
quantile from 200 / 800 autocorrelated draws, and would be the first thing to fix if the risk
quote matters more than the half-spread (more draws, or a Rao-Blackwellised tail).

**Drift.** None. warm200's late-minus-early change in mean |error| is -0.14 to 0.00 pp,
warm50's -0.33 to +0.16 pp; signed means stay within +/- 0.56 % early and +/- 0.16 % late with
no common sign across seeds. 100 ticks on a frozen step and metric (dimension 253 to 353) did
not degrade the quote.

**The refits are not the ceiling as sampled.** Against warm200, the oWALNUTS refit is worse at
every tolerance from 2 % up on P50 (93.3 % vs 97.3 %) and from 5 % up on P95 (94.3 % vs
98.3 %); CmdStan is worse still (87.7 % / 89.7 %). The cause is one thing: on 7 % (oWALNUTS,
best-of-16 starts) and 13 % (CmdStan) of ticks one chain's warmup collapsed and it froze far
off-target, so a quarter of the draws are garbage, the half-spread is off by about 10 % and the
risk quote by 100 % to 1e9 %. nutpie never froze and is the true ceiling as sampled: P50 within
1 % on 98.7 %, P95 within 2 % on 98.3 %. With stuck ticks removed all three refits converge to
the same 0.25 to 0.31 % median P50 error, i.e. the stuck chain is the whole difference, but
a gate leaves 7 to 13 % of ticks unquoted at 3 to 6 s each. oWALNUTS names the stuck chain
itself (`WarmupStep` / `SampledLogDensity`, 21/21), so a chain gate costs nothing to add.

**Why the preregistered bar failed.** It demanded |q_arm - q_ref| <= 3 MCSE_ref on h_next,
about 0.3 to 0.6 % on the quantiles, which is below the warm arms' own Monte Carlo error
(0.9 to 1.8 %) and at the refits' (0.4 %). It measured draw count, not quote quality.

## Surprises

1. The reference had stuck chains on 4/100 ticks and the frozen analysis treated it as truth.
   At those ticks every arm, nutpie included, "missed" by -7 % on P50 and -91 % to -100 % on
   P95, and the reference P5 was 1e-5 instead of 0.0035. The frozen validity rates are
   therefore up to 4 points too low and the warm "fraction inside the reference 90 %
   interval" was 1.0 instead of ~0.9 at tick 21. Not material to the frozen verdict, but
   the next protocol must gate the reference on the sampler's own chain flags.
2. Stuck chains, not divergences, are the real failure mode of a refit on this model: step
   collapsed to 1e-5 to 1e-7, log density thousands below the other chains, frozen at
   log_sigma +0.8 to +1.9 and h_last anywhere from -53 to +32, zero divergences because the
   chain never moves. "No arm had a retained divergence" and "R-hat ok 93 % / 87 %" in the
   frozen table were these chains. The warm path is immune because it never re-warms, but it
   is hostage to its tick-0 fit (clean in 3/3 seeds here, no warnings).
3. nutpie 0/300, oWALNUTS 21/300 (with best-of-16 starts), CmdStan 39/300. That ordering is
   a warmup / initialisation result worth its own study; it is not a WP84 claim.
4. ESS per draw is above 1 for every arm (1.25 to 1.42): the h_next chains are antithetic.

## Candidate accuracy rule for the next preregistered online study

Written as a candidate; thresholds come from the reference floor above, not from the warm
arm. Predictions from these data follow so the rule is falsifiable.

* **Reference, gated.** Per tick 4 x 2,000 / 20,000 at defaults. A chain named by a
  `WarmupStep` or `SampledLogDensity` warning is dropped; if fewer than 3 chains remain, or
  max R-hat(h_next) over the remaining chains exceeds 1.01, the tick is rerun with the next
  seed (logged, counted). This keeps the floor at 0.1 to 0.3 % instead of 10 to 400 %.
* **Quantities.** sigma_next = exp(h_next / 2): P50 (half-spread) and P95 (risk quote),
  relative error vs the gated reference. P5 and mean reported, not gated.
* **Tolerances.** T50 = 2 % on P50, T95 = 5 % on P95. Justification: the worst-tick
  half-reference gap is 0.72 % (P50) and 1.05 % (P95) and the worst-tick reference MCSE is
  0.29 % / 0.34 %, so T50 is ~3x the worst empirical gap and ~7x the worst MCSE, T95 ~5x and
  ~15x: a miss by more than T cannot be reference noise, and a 1 % tolerance would not be
  adjudicable per tick (the gated refits miss it on 2 % of ticks from their own noise). In
  quote terms, 200 bp per unit of half-spread and 500 bp per unit of risk quote; whether
  that is tight enough for a desk is the market maker's call, not the study's.
* **Pass.** Both |err P50| <= T50 and |err P95| <= T95 on >= 95 % of the 300 ticks (3 seeds x
  100) and on >= 90 % in every seed, with latency under its threshold on the same ticks. A
  tick with a stuck chain (sampler flag, or the census rule for external samplers) counts as
  failed, not excluded: a quote engine would have used it.
* **Self-consistency (reported; gate if the study wants a reference-free check).** The arm's
  own quantile MCSE of P50 <= T50 / 2 on >= 95 % of ticks, so a pass is predictable in-line.
* **Drift.** Per seed, |mean signed P50 error over ticks 76-100 minus ticks 1-25| <= 0.5 %
  and |mean signed P50 error over all 100 ticks| <= 0.5 % (reference noise averaged over 25
  ticks is ~0.03 %; the largest shift seen here is 0.47 pp, on warm50).
* **Predictions from these data.** warm200 passes (97.3 % / 98.3 %; own MCSE 0.9 % < 1 %);
  warm50 fails (74 % / 78 %); oWALNUTS refit and CmdStan fail as sampled (93 % / 94 % and
  88 % / 90 %) and pass gated; nutpie passes (100 % / 100 %). The open question is the
  smallest K between 50 and 200 that passes, and whether the P95 bias needs a fix.

## Rerun

```
<venv>/python posthoc/quote_error.py artifacts/cells          # tables to stdout
<venv>/python posthoc/quote_error.py artifacts/cells --json out.json
```

About 25 s with arviz 0.23.4 / numpy 2.4.6. Reads only; writes nothing unless `--json`.
