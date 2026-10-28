# Observed accounting evidence and economic limits

This supplement records engineering and conditional accounting results. It does
not establish an economic policy advantage or an original accounting algorithm.
The generic AMM oracle is not a deployed-contract replica.

## Fixed observed panel

The panel uses Ethereum USDC/WETH pair
`0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc` and a 4,096-block interval ending
at the previously pinned finalized block 26290256. Transport failures and
provider changes are retained. The successful acquisition came from AWS through
one provider; two fixed query partitions agree. This does not establish
provider-independent completeness or complete intervening header ancestry.

Five liquidity events occur in three transactions across three blocks: three
mints and two burns. All five match their transaction receipts. Before/after
block snapshots contain 42 state calls; 410 pool and token logs were preserved.
Transfer-derived pool balances match the boundary snapshots, and every observed
Sync matches the reconstructed token balances. These endpoints do not prove
that there were no offsetting unobserved intermediate balance changes.

Under constant intrablock feeTo, ordinary token-transfer behavior and upstream
pair semantics, the integer model reproduces all five operations. Checked
quantities include protocol LP issuance and recipient, user mint amounts,
pair-held LP consumed by burns, burn amounts and recipient, reserves, final LP
supply and kLast. All three block reconstructions match. These five operations
are a fixed engineering case study, not five independent statistical trials or
a population estimate of accounting reliability.

The check is deliberately restricted to the observed liquidity-only pair-event
blocks. It rejects unsupported pair events. Tests include altered event amounts
and burn recipients, zero-address ambiguity, ABI padding, integer rounding,
overflow and donation-inclusive arithmetic. Passing these checks is not EVM
equivalence, a deployed-bytecode/compiler match, or proof of the intrablock
fee-recipient assumption. The arithmetic follows the existing
[Uniswap pair](https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2Pair.sol)
and [LP-token](https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2ERC20.sol)
implementations, rather than a claimed novel mechanism.

## Evidence preservation

Raw discovery, receipts and boundary-state archives were uploaded to private
versioned S3 and downloaded by exact version ID. Restored bytes match the
locally verified archive SHA-256 values. Object identities and version receipts
are linked from the [accounting admission record](../STUDIES/amm_accounting_v1/DATA-ADMISSION.md).
Reports preserve source and input hashes; failures remain alongside successes.

## Remaining economic requirements

Accounting consistency alone does not identify future fee revenue, demand
response, executable entry/exit, gas or liquidation costs. A marginal-LP policy
needs cash, matched token-inventory and fixed-LP controls under the same
information and execution assumptions. Observed swaps cannot simply be replayed
unchanged under a different fee and called counterfactual fills.

The [predictive-tail derivation](../STUDIES/amm_accounting_v1/LOG-WEALTH-OBJECTIVE.md)
also remains a separate concern: conditional on posterior propriety, its current
argument implies divergent positive return moments under the unbounded
log-normal scale prior. It needs independent mathematical review. Finite
Monte Carlo estimates and passing sampler diagnostics cannot establish finite
economic moments. Proposed bounded objectives change the decision question;
they do not estimate unbounded expected profit.

Before economic results enter the manuscript, the missing assumptions must be
validated or explicitly bounded, and the decision objective, policy family,
costs, selection procedure and untouched evaluation interval must be frozen.
No profitability or decision-value claim is admitted by this supplement.
