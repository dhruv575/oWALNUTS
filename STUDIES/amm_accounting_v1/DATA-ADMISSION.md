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
was not disabled. At that checkpoint pool identity/state acquisition remained
unverified. These failures remain in the engineering history.

### Transport recovery and completed snapshot

Windows curl 8.21.0/Schannel also failed TLS negotiation with the PublicNode
endpoint (HTTP status 000). A separate fixed-block attempt through
`https://eth.drpc.org`, listed in the
[Ethereum chain registry](https://raw.githubusercontent.com/ethereum-lists/chains/master/_data/chains/eip155-1.json),
completed all 13 read-only requests in 4.37 seconds. No certificate verification
was disabled, and no chain outcome was used to choose a different block.

At the same pinned block, the factory resolves pair
`0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc`. Returned token0/token1 match
USDC/WETH, decimals are 6/18, and the pair reports the intended factory.
Reserves in raw integer units are 9855293124395 and 4152633905887036482868;
LP total supply is 70825582185439218. The runtime bytecode is 11293 bytes;
its fingerprint is preserved, not claimed independently compiled.

The factory's fee recipient is nonzero:
`0xf38521f130fccf29db1961597bc5d2b60f995f85`. Observed LP-supply accounting must
therefore include protocol-fee minting behavior rather than assume the E69
no-protocol-fee abstraction. Both header checks match the original finalized
block hash. Metadata/raw responses are in `evidence/pair-snapshot-20261028/drpc/`;
a verified local archive also preserves the exact executed source and 43 sealed
files. This is a state/identity snapshot only: no swap-event panel or economic
policy evaluation has yet been admitted.

## Fixed 64-block engineering panel completed

The predeclared range 26290193–26290256 yielded 18 logs: nine Sync/Swap
pairs and no liquidity events. All 74 read-only calls completed in 18.55 seconds
within the declared request, byte and time bounds. Full-range and two half-range
responses agree; 65 headers form a continuous ancestry ending at the pinned
finalized hash. This does not establish provider-independent completeness.

The swap-only auditor reconstructs every integer reserve transition, checks the
997/1000 fee-adjusted product inequality, and matches terminal reserves and
reserve timestamp exactly. LP total supply is unchanged. Three focused tests
cover large integers, invalid accounting and Ethereum Keccak. Raw requests,
responses, exact sources, accounting output and a verified archive manifest are
preserved in `evidence/pool-events-20261028/`. The 1,451,200-byte archive was
uploaded to the private versioned S3 research bucket, downloaded by its exact
version ID, and checked against its SHA-256 and all 233 member hashes. The
`S3-VERIFIED.json` receipt identifies the immutable object version; local
originals remain available.

This is a narrow accounting admission, not a policy evaluation. The auditor
rejects unsupported events rather than silently excluding them. Mint, burn,
standalone Sync, donations and protocol-fee issuance remain unvalidated. The
observed nonzero feeTo requires protocol-fee accounting before LP economics.
No gas, liquidation, demand-response or profitability claim follows from this
sample. Reproduce offline with Python and pycryptodome 3.23.0:
`python audit_swap_panel.py evidence/pool-events-20261028 NEW-ACCOUNTING.json`.

## Requirements for broader acquisition

`liquidity_math.py` adds a separate integer arithmetic model based on the
[upstream v2 pair implementation](https://github.com/Uniswap/v2-core/blob/master/contracts/UniswapV2Pair.sol),
reviewed 2026-10-28. It handles protocol liquidity issuance before LP mint/burn,
the initial 1,000 locked LP tokens, donation-inclusive balances, floor division,
integer square roots and checked uint256 operations. Five hand-computable tests
cover dilution, fee switching, donations, rounding, invalid mint/burn and overflow.
The existing swap-only event auditor remains strict and does not silently use
this arithmetic to admit unsupported events.

This is not a compiled-contract equivalence result or deployed-bytecode match.
Burn assumes ordinary transfers debit the stated amounts; taxes, rebases and
balance-changing callbacks are outside this helper. Broader replay must acquire
pre-event balances, supply, kLast, feeTo history and LP transfers. It must also
distinguish initial mint-to-zero from burns and ordinary transfers to zero;
recipient address alone does not determine a supply change. Observed liquidity
events and contract-level differential checks remain required.

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

### Liquidity discovery transport failure (2026-10-28)

A separate fixed 4,096-block range ending at the same finalized anchor was
declared for Mint/Burn discovery, with 20 requests, 120 seconds and byte caps.
Both the initial attempt and a diagnostic attempt stopped on their first log
query after chain and anchor checks succeeded. The diagnostic attempt added
HTTP-error-body preservation; it was not an independent scientific replicate.
The provider returned HTTP 400 and RPC code 35, reporting an unsupported range
over 10,000 blocks, despite the serialized bounds spanning 4,096 blocks.
The cause of that inconsistency is unresolved. No events were acquired and no
liquidity accounting was admitted. Exact executed sources, source hashes,
plans, requests, successful responses and terminal failures are preserved in
`evidence/liquidity-discovery-20261028/`. The first attempt did not retain its
HTTP error body; the second did. Any revised range/chunking is a new declared
engineering acquisition, not a retry hidden within these attempts.

A separately declared partitioned acquisition retained that exact 4,096-block
range, comparing 256-block with 128-block partitions. A coverage test proved
both partitions cover the same integers without overlap or gaps. The first
256-block query received the same code-35 rejection. Four fixed diagnostic
queries then tested no topic filter, Mint/Burn alternatives, Mint alone and Burn
alone over that identical 256-block interval. The initial diagnostic used the
default Python user agent and received non-JSON `error code: 1010` bodies;
a separately recorded diagnostic with the acquisition's explicit user agent
received code 35 for all four variants. Thus this evidence does not isolate a
topic-filter problem. All raw responses and exact executed sources are retained.
No diagnostic acquired event data. Further acquisition needs a separately
reviewed transport/provider change rather than repeated identical requests.

### Same-range acquisition from AWS completed

The [Ethereum chain registry](https://raw.githubusercontent.com/ethereum-lists/chains/master/_data/chains/eip155-1.json)
also lists `https://mainnet.gateway.tenderly.co`. A bounded local attempt failed
TLS negotiation before any chain response. Running the separately recorded,
same-range partitioned probe from AWS completed 54 requests in 13.43 seconds.
It obtained three Mint and two Burn events across blocks 26287531, 26289040
and 26289812. The first two blocks each contain a Mint and Burn in the same
transaction; their economic purpose has not been inferred from those labels.

The 256-block and 128-block partitions returned identical event lists; event
block hashes match returned headers and the original finalized anchor was
rechecked. This is not independent-provider completeness or full intervening
header ancestry. A downloaded 134,212-byte archive has SHA-256
`8d3933fdcb9f0f3744e3b9762e3fadab7abef46e1726b97a6099e06cd37bb2ab`.
Local checks matched executed source hashes, partition responses and event
headers. Raw evidence is in `evidence/liquidity-discovery-20261028/tenderly-aws/`;
the failed local attempt is also retained. Transaction receipts, token transfers,
pre-event balances, feeTo and kLast still need acquisition and accounting checks.
Finding these events does not validate mint/burn arithmetic or protocol dilution.

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
