# From accounting oracle to observed pool evidence

Status: data-engineering preparation, not an economic result or a frozen
profitability experiment. The existing Deribit half-hour bars do not measure
AMM swaps, liquidity ownership, executable fills or counterfactual fee demand.

## Verified access

A two-request, no-retry public RPC probe completed on 2026-10-28. It checked
Ethereum chain ID 1 and obtained finalized block 26290256, hash
`0xc16c4e48c8281db0d4bb49675df01bd4bb3ab359e617141407644a66b18862e6`.
The requests, responses, source hash and bounded protocol are preserved in
`evidence/rpc-readiness-20261028/`. It did not acquire a trading evaluation
panel. PublicNode documents this endpoint on its
[Ethereum gateway page](https://ethereum.publicnode.com/).

The [Ethereum JSON-RPC specification](https://ethereum.org/developers/docs/apis/json-rpc/)
provides block and log retrieval. Availability on two calls does not establish
provider completeness, archive access, historical coverage or future service.

## Fixed pair snapshot preparation and transport failures

`pair_snapshot.py` fixes the earlier finalized block and resolves the USDC/WETH
pair through the Ethereum v2 factory. The factory address is corroborated by
the [official deployments table](https://developers.uniswap.org/docs/protocols/v2/deployments);
token addresses/decimals are corroborated by the
[Uniswap token list](https://github.com/Uniswap/default-token-list/blob/main/src/tokens/mainnet.json).
The intended checks cover returned pair factory, token ordering, decimals,
reserve ABI bounds, LP supply, runtime bytecode fingerprint, protocol-fee
recipient and unchanged pinned block hash. A bytecode fingerprint is not
independent compiler equivalence. Two ABI controls pass, including integer
precision above the floating-point exact range and rejection of address padding.

Both the initial attempt and one separately recorded transport-recovery attempt
failed on the first request with SSL WRONG_VERSION_NUMBER. Neither received a
chain response or acquired pool observations; no per-attempt request retries
occurred. The second attempt followed the first transport failure and is not
presented as an independent scientific replication. Both plans, attempted
requests and terminal errors are preserved in `evidence/pair-snapshot-20261028/`.
No proxy was reported by urllib's proxy discovery, and certificate verification
was not disabled. Pool identity/state acquisition remains unverified; no event
panel has been admitted. Diagnose transport or use a documented provider before
proceeding, preserving these failures in the engineering history.

## Next bounded engineering acquisition

Use a declared pool and fixed finalized block range before inspecting swap
activity. Resolve and verify factory/pair/token identities and bytecode;
retrieve token decimals and initial reserve/supply state at the preceding
block. Preserve raw request/response bytes, block hashes, timestamps, log order,
transaction identifiers and acquisition wall-clock times. Keep removed logs,
gaps, RPC errors and byte/rate/time-limit failures explicit. Validate event
identities and compare terminal reconstructed state against an independent
state call. A provider's empty response is not by itself proof of no events.

The [Uniswap v2 pair implementation](https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2Pair.sol)
is an initial concrete accounting candidate. Its state updates and event order
must be reproduced, including non-swap reserve changes and liquidity issuance.
The generic real-valued E69 oracle is not an integer-accurate replica of this
contract. No observed pool is admitted solely because the oracle tests pass.

## Economic identification boundary

Observed swaps support reconstruction under the observed contract and policy.
Replaying those same swaps unchanged under another fee is not an identified
demand response. Transaction classification alone cannot label every trader as
uninformed or recover their reservation prices. A fee-changing policy therefore
needs an explicit response model or sensitivity bounds, not fabricated fills.

A possible first feasible control is marginal LP exposure versus cash in the
quote token, rather than assuming an LP can change a deployed pool's fee.
This remains a proposal. It requires LP ownership/supply accounting, entry and
exit execution, token transfer behavior, gas, latency and an observable mark or
liquidation convention. Treating a position as an infinitesimal price-taker is
an assumption to bound and test, not a statement about arbitrary capital size.
Quote-token wealth is not automatically USD wealth.

Before evaluating any policy, freeze the information available at each action,
decision delay, capital constraints, objective, controls, costs and untouched
evaluation data. Compare inference methods on the same economic model and
decision rule to isolate algorithm value. Forecasting observed returns alone
does not model future fee revenue. Neither successful data acquisition nor an
accounting replay can establish profitability.
