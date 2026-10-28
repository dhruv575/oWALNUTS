# E69: self-financing constant-product accounting oracle

Engineering qualification only: no market data, posterior fitting, optimized
strategy, or profit claim. This replaces the repeated-endowment abstraction
with carried base/quote reserves. Generic constant-product pool with retained
input fees, no protocol fee, no liquidity deposits/withdrawals, no borrowing.
This is not a replica of a deployed protocol's current fee configuration.

At external quote/base price p, reserves (x,y) have value px+y. A quote input a
returns x*g*a/(y+g*a) base, where g=1-fee. Full a enters reserves; the difference
between a and g*a is retained fee, not additional cash income. Base input is
symmetric. Every swap records both token flows, retained fee, and pool change
at the external mark. Counterparty profit must be its negative, before any
external execution/gas cost. Reserves carry across events.

For one frictionless arbitrageur, optimize the actual swap profit. Quote input
is (sqrt(p*x*g*y)-y)/g when p>y/(g*x); base input is
(sqrt(y*g*x/p)-x)/g when p<g*y/x; otherwise no trade. No arb profit is invented
inside the fee band. Gas/market execution are omitted in this engineering
oracle and must be introduced before empirical economics.

Verify exact zero-fee formulas, token conservation, product nondecrease, fee-band
inactivity, independent scalar-optimizer agreement and a multi-event telescoping
ledger. A pool with only arbitrage cannot earn positive marked trading income
from those arbitrage trades, even when gross fees are positive. Mark-to-market
gains from prior inventory must remain separate.

Primary references: Uniswap's v2 pricing mechanics
https://developers.uniswap.org/docs/protocols/v2/concepts/pricing ;
Milionis et al. https://arxiv.org/abs/2208.06046v6 and
https://arxiv.org/abs/2305.14604v2 . The formulas above are derived for this
specific discrete model; no continuous-time theorem is asserted for it.

Research admission beyond this oracle requires: actual venue/data choice;
observable executable opportunity set; information and action timestamps;
fee-dependent uninformed demand or explicit execution bounds; adverse selection;
inventory and wealth constraints; costs; fixed controls; and a fresh evaluation
protocol. Deribit half-hour returns alone cannot identify AMM fee revenue or
counterfactual fills. A synthetic test must remain labelled synthetic.
