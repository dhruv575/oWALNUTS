# Decision contracts for the current return model

2026-10-27. Exploratory analytic review of the existing model, not a new empirical
study or a recommendation to deploy a strategy. No sampling or market data was
used for this note.

## What the model supports

The current predictive model has log return

`R = beta + exp(H/2) T5`, with `H | theta ~ Normal(m, s^2)`.

For any finite location and positive finite scale, the conditional Student-t5
right-tail density behaves as `C r^-6`. Therefore the integral of
`exp(r) f(r)` over the right tail diverges. This holds before posterior or
future-volatility mixing; nonnegative integration (Tonelli's theorem) preserves
the divergence under mixing. A finite empirical mixture of posterior draws does
not remove this conditional tail property.

Consequently, for positive current price `S`, the implied future price
`S exp(R)` has infinite expectation. A one-unit unbounded short has infinite
expected positive dollar loss `S (exp(R)-1)+`. A long's signed expected price
gain is also not finite. Finite realized observations in a backtest do not
establish a finite model-based expected P&L.

This is a moment limitation, not a failure to define a probability distribution.
Finite quantiles, event probabilities and monotone price quantiles
`S exp(q_p(R))` remain well-defined. Numerical approximation of those quantities
still needs its own accuracy checks.

## Distinguish the loss being evaluated

For a finite stored-draw mixture, the first absolute log-return moment is bounded
by the weighted sum of

`|beta| + E|T5| exp(m/2 + s^2/8)`.

Each term is finite for finite parameters. Thus log-return pinball loss is
integrable for that mixture. This argument does not establish integrability for
an unrestricted hierarchical posterior over the parameters. An observed finite
label also gives a finite realized pinball loss without proving that hierarchy's
moment condition.

Dollar downside is not uniformly unbounded. A one-unit long's positive downside
loss `S (1-exp(R))+` lies between zero and `S`, so its expectation is finite.
Likewise, a genuinely bounded payoff or loss has a finite expectation. A fixed,
finite action set with bounded losses therefore defines a mathematical decision
problem even when expected future price is infinite.

The underlying economic contract must justify any cap. Capping pinball itself
changes the scoring objective and does not automatically preserve quantile
propriety. Pinball applied to a separately defined bounded loss variable instead
targets that variable's quantile. These are different operations.

## A Gaussian replacement is not an automatic fix

If the observation model alone becomes `R | H ~ Normal(beta, exp(H))`, with
volatility-independent location and nondegenerate Gaussian `H`, then

`E[exp(R)] = exp(beta) E[exp(exp(H)/2)] = infinity`.

The exponential of `exp(H)` dominates the Gaussian tail penalty. Thus changing
only the observation distribution does not settle the price-moment question.
Different drift/volatility constructions must be assessed on their own; no model
change is selected or validated here.

## Next empirical contract

Specify the horizon, inventory exposure, available actions, payoff/loss and
required moments before interpreting a forecast as an AMM decision. Quantile
limits and bounded-loss decisions can be useful intermediate tests. Fills,
inventory evolution, fees and adverse selection still need explicit models and
validation; a density or quantile score does not supply them.

The [stored-draw risk-limit diagnostic](../predictive_risk_limits_v1/PLAN-DRAFT.md)
uses separate 95% long/short **log-return** loss limits and realized pinball loss.
It introduces no expected-dollar-P&L claim. The
[historical density replication](../market_replication_v1/README.md) remains
predictive evidence with its original scope.

Source interface:
[predictive density implementation](../predictive_value_diagnostic_v1/predictive_density.py)
and [SV target](../resident_predictive_harness_v1/sv_target.py).
