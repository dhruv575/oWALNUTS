# Bounded downside decisions for existing spot-long inventory

Status: proposal only, prepared without E66 outcomes. No new data acquisition,
posterior sampling, loss calculation or policy evaluation is authorized here.
This does not amend the frozen fresh-risk confirmation study.

## Decision contract

At each origin, start with one externally endowed unit of spot-long inventory
at current price S>0 and
the same 30-minute horizon as E64. The action set is fixed: retain the unit, or
convert it to cash immediately at a hypothetical deterministic friction cS,
with c=0.0005 (five basis points of current notional). There is no optimized
fee, adaptive threshold or estimated fill model. This friction is an explicit
toy contract, not a measured executable transaction cost.

The objective is positive downside plus conversion cost, normalized by S:

- Retain: loss Y=(1-exp(R))_+, which lies in [0,1].
- Convert: loss c, regardless of the next return.

Origins are separate endowed-inventory decisions, not one self-financing path:
conversion does not imply free replenishment for an actual strategy.
Upside foregone, market impact, inventory replenishment and execution uncertainty
are outside this objective. It is a downside-control decision, not a profit
strategy or a complete utility specification. A normal AMM's multiasset inventory
and endogenous fills are also outside this one-step isolated test.

The finite optimal decision for a forecast distribution is retain when
m=E[Y]<=c, convert otherwise; equality deterministically retains. The choice
is defined for the unrestricted predictive hierarchy because Y is bounded,
even though E[exp(R)] is infinite under the current model. No artificial cap is
placed on a short position, and no short-liability guarantee is implied.

## Forecast target versus decision quality

The proper forecast target is the conditional mean m of bounded downside.
Squared-error loss (m-Y)^2 strictly elicits that mean and is integrable. This
proper target is separate from the policy's realized cost
Y*I[retain]+c*I[convert]. Good squared-error forecasts need not rank identically
to policies at one fixed threshold; both results must be reported.

Use unchanged SV, rolling Student-t5 and EWMA Student-t5 predictive distributions.
All three face the identical action set, friction and realized loss. Include
always-retain and always-convert controls for decision cost. No comparator or
cost level is selected after seeing outcomes. The important comparison is
whether posterior inference improves this declared decision over cheap EWMA,
not merely whether it improves a density or quantile score.

## Finite and auditable integration

For the predictive return CDF F, Tonelli's theorem gives

    E[(1-exp(R))_+] = integral from -infinity to 0 of exp(r) F(r) dr.

The contribution below -A is at most exp(-A), independent of posterior tails.
For example, A=log(1e10) bounds omitted mass in this integral by 1e-10. All
exponentials evaluated in the retained domain have nonpositive arguments.
This avoids computing a nonexistent unconditional exponential-price moment.

Reuse the existing full predictive CDF and exact t5 backend with the unchanged
GH64/GH128 rules and full stored draws. Before any historical arithmetic, choose
and freeze the outer bounded integration rule through deterministic correctness
and full-size literal timing tests. Proposed absolute targets are 1e-8 for the
outer integral and GH-rule agreement, plus the explicit 1e-10 tail bound. These
are proposals, not a claim of demonstrated accuracy. No fitted tail truncation,
return clipping, reduced posterior draws or outcome-based numerical adaptation.
The omitted-tail bound is rigorous, but GH-rule agreement and an adaptive
integrator's error estimate alone are not a certified total-error bound. Report
threshold decisions that differ across the frozen numerical checks as numerically
ambiguous, without claiming certified regret or action accuracy. A regret bound
requires an independently justified bound on the complete CDF integral: if
|m_hat-m|<=epsilon truly holds, a wrong threshold action has conditional regret
at most epsilon.

## Analytic correctness fixtures

Before empirical execution, require all of the following without market data:

1. Degenerate-return distributions recover (1-exp(r0))_+, including negative,
   zero and positive r0, and deterministic decisions around the fixed threshold.
2. An independent high-accuracy integral for a single finite-scale t5 law agrees
   with the production CDF-integral calculation within the frozen tolerance.
3. Mixtures obey linearity, permutation invariance and duplicated-draw invariance;
   increasing returns by a fixed shift cannot increase positive downside.
4. Every result lies in [0,1]; omitted-tail bounds hold for adversarial bounded
   CDF fixtures; multiplying price/notional by S scales dollar costs exactly
   while leaving normalized forecasts and decisions unchanged.
5. The fixed decision minimizes the two expected losses on analytic fixtures;
   squared error decomposes into conditional variance plus (forecast-m)^2.
6. Deadline, malformed-draw, numerical-disagreement and partial-output fixtures
   retain planned denominators and never substitute a different action/model.

No numerical success criterion or economic threshold may be weakened because a
historical result or a full-size fixture is inconvenient. Any necessary method
revision must be separately reviewed before outcome calculation.

## Smallest useful empirical follow-on

If the analytic and resource review clears, use all already exposed E64
April/May/June origins and the same stored draws, saved baseline fits and 24
reference spots. This is explicitly retrospective exploratory reuse. E66 remains
untouched and is not silently repurposed as a holdout for an extra endpoint.
No additional acquisition or sampler is needed for this first decision diagnostic.

Freeze all three complete panels, per-month paired 24/48/96-origin block intervals
(48 primary), and complete missing-denominator rules before arithmetic. Report
all model-versus-control squared-error and decision-cost comparisons, conversion
rates, numerical ambiguity counts and reference precision. Overall means would
be descriptive only; no pooled interval, familywise pass count or profit gate.
An informative result could be that improved forecast scores do not change
decisions or do not beat EWMA at the declared cost. That result must be retained.

Proposed operational envelope: existing 12 one-core shards, 8GiB aggregate RSS,
1GiB output and at most 3,600 internal / 3,720 external seconds. First measure
full-size literal candidate/reference integral costs under bounded readiness;
do not infer feasibility from quantile timing. If all mandatory origins cannot
fit, stop at a documented resource finding rather than select a favorable subset.

Practical acceptance is deliberately separated: numerical acceptance requires
the frozen fixtures and accuracy/resource bounds; evidence completeness requires
every planned slot; an empirical advantage requires the declared paired cost
comparison with its uncertainty. None of these establishes fills, realistic
execution costs, inventory-policy stability or profitable AMM deployment.

See the [moment/decision contract](../amm_decision_contract_v1/README.md) and
[E65 tail-limit comparison](../predictive_risk_limits_v1/README.md).
