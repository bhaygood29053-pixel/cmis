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

The transport still preserves returned values without interpreting units.
A successful live response is required before any response fields are promoted.

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

The next live probe uses AGI -> XNT market representation and Unix epoch
seconds for a seven-day window. **The time unit remains provisional** until
XDEX accepts the request and returned point semantics are inspected.

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

The request is read-only. Response fields must not feed `pre_trade_check`
policy until live verification confirms amount units, rate semantics,
`priceImpactPct` semantics, route identity, freshness/expiry, and fees.

## HTTP error evidence

Provider transport includes a bounded XDEX response body in HTTP errors. This
is intentional contract-discovery support so a 4xx response identifies the
actual missing/invalid parameter instead of being reduced to a generic status.

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

Defaults:

- current-price/history base token: AGI
  `7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER`
- history quote token / quote input: XNT market representation
  `So11111111111111111111111111111111111111112`
- quote output: XNM
  `AvNDf423kEmWNP6AZHFV7DkNG4YRgt6qbdyyryjaa4PQ`

Overrides:

```text
XDEX_LIVE_TOKEN
XDEX_LIVE_HISTORY_TO_TOKEN
XDEX_LIVE_QUOTE_TOKEN_IN
XDEX_LIVE_QUOTE_TOKEN_OUT
```

A passing live probe verifies only the fields asserted by the test. It does
not authorize CMIS promotion of undocumented units or semantics without a
deterministic adapter and tests.
