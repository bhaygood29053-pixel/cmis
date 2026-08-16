# XDEX Read-Only Provider Contract Verification

Status: **provider transport implemented; live contract promotion gated**

This document records the XDEX API surface being verified for direct use by
the X1 Provider beneath CMIS. It separates user-supplied API notes, live
observations, request contracts, and fields that are safe to promote into CMIS.

## Ownership

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> XDEX public API
```

Roberta and X1 Scout must not call XDEX HTTP endpoints directly.

The direct XDEX provider in this milestone is read-only. It does not prepare,
sign, or broadcast transactions.

## X1 network liveness vs economic availability

X1 mainnet validator/RPC operation and practical DeFi/economic availability are
separate concepts.

The project rule supplied by the user is that normal practical access to the
X1 economy depends on bridging USDC from Solana across the X1 bridge and then
using the X1-side liquidity path. Therefore CMIS must not equate an operational
RPC/validator network with available XDEX liquidity, routability, or a usable
native-XNT market.

Bridge availability, bridge capacity, XDEX liquidity, pool existence, and quote
availability are freshness-sensitive provider facts and must be verified when
needed. They must not be inferred from the fact that X1 mainnet RPC is online.

## Native XNT identity rule

Project policy supplied by the user:

```text
Canonical asset: XNT
Asset type: native X1 currency
Native/provider identifier: So11111111111111111111111111111111111111112
```

The user has explicitly instructed that Roberta/CMIS must use **native XNT** and
must not model or substitute WXNT as a separate asset for this workflow, even
though the same identifier may be associated with XNT/WXNT in external tooling.

The canonical CMIS identity therefore remains native XNT. A provider must not
silently convert XNT into a wrapped-token identity merely to satisfy a token
program or DEX endpoint.

A live XDEX quote using the supplied native-XNT identifier reached the XDEX
backend but failed with:

```text
failed to get token supply: Invalid param: could not find account
```

This is evidence about the current XDEX quote path, not evidence that the
canonical XNT identity is wrong. The XDEX adapter must treat native-token
handling as a provider-specific concern. Until XDEX native-XNT quote behavior
is verified, native XNT must not be forced through token-mint semantics and no
alternate wrapped-XNT address may be invented.

## Base URL

```text
https://api.xdex.xyz
```

Use HTTPS.

## Live-observed network contract

The user-supplied catalog described generic values such as
`mainnet | testnet | devnet`. Live XDEX responses on 2026-08-16 showed that
the quote endpoint rejects `network=mainnet` and explicitly requires one of:

```text
Solana Devnet
Solana Mainnet
X1 Testnet
X1 Mainnet
```

The X1 provider therefore uses:

```text
network=X1 Mainnet
```

This is live-observed request-contract evidence, not a market fact.

## Current token price

A live request using `address=<mint>` failed with:

```text
Network and token_address are required
```

The provider now uses:

```text
GET /api/token-price/price
  ?network=X1%20Mainnet
  &token_address=<TOKEN_MINT>
```

A live AGI request using this shape succeeded. This verifies the request shape
for that endpoint only. It does **not** prove that the same identifier is a
currently deployed/routable X1 token account for swap or chart endpoints.
Returned field units remain unpromoted until explicitly verified.

## Price history

A live request using `token=<mint>&days=7` failed with:

```text
Missing required parameters: from_token, to_token, time_from, time_to, network
```

The provider now uses the live-observed parameter names:

```text
GET /api/xendex/chart/history
  ?network=X1%20Mainnet
  &from_token=<TOKEN_MINT>
  &to_token=<QUOTE_TOKEN_MINT>
  &time_from=<INTEGER>
  &time_to=<INTEGER>
```

A subsequent AGI -> XNM request reached the endpoint and returned:

```text
Pool not found for the given token pair
```

That is useful negative evidence: token identifiers accepted by the token-price
endpoint must not be assumed to form a current X1 pool.

The live probe now loads the existing provider-owned X1.Ninja/XDEX pool catalog,
selects an **exact current pool**, excludes any side identified as XNT/WXNT, and
uses that pool's two token addresses for history verification. This avoids
hard-coded pair guesses and keeps native-XNT adapter behavior out of endpoint
contract discovery.

Unix epoch seconds remain provisional until XDEX accepts an exact catalog pair
and returned point semantics are inspected.

XDEX history must not feed CMIS `historical_compare` or `risk_check` until the
live probe verifies:

- timestamp field and unit;
- price field and quote unit;
- pair direction;
- sampling interval;
- requested-range coverage;
- stale/interpolated/aggregated behavior.

Until then, CMIS's existing verified local historical observations remain
authoritative.

## Swap quote

A live request with `network=mainnet` failed and explicitly identified
`X1 Mainnet` as a valid network value. The provider uses:

```text
GET /api/xendex/swap/quote
  ?network=X1%20Mainnet
  &token_in=<ADDRESS>
  &token_out=<ADDRESS>
  &token_in_amount=<POSITIVE_NUMBER>
  &is_exact_amount_in=true
```

The request is read-only. A live quote using the supplied native-XNT identifier
failed in XDEX token-supply lookup, so native-XNT quote support remains
unverified.

A later AGI -> XNM quote also failed in XDEX token-supply lookup for the AGI
identifier even though AGI token-price lookup succeeded. Therefore quote
verification must use token addresses taken from an exact current X1 pool, not
assets chosen only because token-price lookup recognizes them.

The live probe now uses the same catalog-selected non-XNT pool pair for quote
verification. Response fields must not feed `pre_trade_check` policy until live
verification confirms amount units, rate semantics, `priceImpactPct` semantics,
route identity, freshness/expiry, and fees.

## Live-pair discovery rule

The opt-in probe uses the existing `X1Provider` / X1.Ninja catalog as the source
of current pool membership. Pool rows use the established provider shape:

```text
address
baseToken.mint / baseToken.address
quoteToken.mint / quoteToken.address
```

The probe:

1. refreshes the current X1 pool catalog;
2. finds the first exact pool whose two sides have usable addresses;
3. excludes XNT/WXNT/`Wrapped XNT` sides per project policy;
4. prints the selected pool and symbols;
5. uses that exact pair for token-price, history, and quote checks.

If no current pool has two non-XNT token sides, the live XDEX tests skip with an
explicit reason instead of fabricating a pair or substituting WXNT. The catalog
requires the same `X1_NINJA_API_KEY` used by the existing X1 market provider.

## HTTP/error evidence

Provider transport includes bounded XDEX response details for HTTP errors and
top-level `success:false` responses. This is intentional contract-discovery
support so an unsuccessful request identifies the actual missing/invalid
provider assumption instead of being reduced to a generic status.

## Swap prepare is out of scope

```text
POST /api/xendex/swap/prepare
```

is intentionally excluded. Transaction preparation belongs to the future
Execution Agent boundary. Signing, broadcasting, value movement, and wallet
permission changes require human approval.

## Opt-in live verification

```bash
RUN_XDEX_LIVE_TESTS=1 \
python -m unittest discover -s tests -p "test_xdex_live_contract.py" -v
```

The live probe no longer hard-codes AGI/XNM/XNT as a presumed tradable pair.
It discovers an exact current non-XNT pool pair from the provider-owned X1 pool
catalog and prints the selected pair before making the read-only XDEX calls.

A passing live probe verifies only the fields asserted by the test. It does
not authorize CMIS promotion of undocumented units or semantics without a
deterministic adapter and tests.
