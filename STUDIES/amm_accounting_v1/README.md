# E69: self-financing AMM accounting oracle

The deterministic accounting checks pass. This is a generic constant-product
pool with retained input fees and carried reserves, not a deployed strategy or
evidence of profitability. Six local tests cover closed-form zero-fee outcomes,
fee-band inactivity, token/value conservation, independent scalar optimization,
multi-event self-financing accounting and invalid inputs.

AWS also passed all 1,375 fixed engineering cases across reserve scales, price
shocks and fee levels using 12 worker processes. Maximum normalized discrepancies:

| Check | Maximum |
|---|---:|
| Pool trade P&L plus counterparty profit | 3.64e-16 |
| Product nondecrease violation from rounding | 1.56e-15 |
| Independent optimizer versus analytic arbitrage | 3.00e-16 |
| Post-trade no-arbitrage band violation | 1.58e-15 |

The admission tolerance was 1e-10. The grid completed in about 0.094 seconds
in the pinned AWS environment; this is a small arithmetic test, not a sustained
utilization benchmark. Source hashes and runtime version are in stress-results.json.
No new data acquisition, random simulation, posterior fit or tuning occurred.

The ledger demonstrates why retained swap fees cannot be added again as cash
income. It also separates price exposure from trading income: in an
arbitrage-only sequence, positive collected fees coexist with negative marked
trading P&L. A realistic economic evaluation therefore still needs information
about other demand, execution constraints, latency, costs and feasible controls.

Scope is finite numerical fixtures and real-valued accounting. Token integer
rounding, protocol fees, gas, transaction ordering and market impact at the
external venue are not modeled. Inputs outside safe floating-point ranges can
be rejected; these tests do not establish universal numerical stability.

The next sampler-specific work should strengthen the independent reference
evidence and compare same-target inference methods at matched accuracy. A
successful forecast-versus-EWMA study alone cannot identify an oWALNUTS advantage.
