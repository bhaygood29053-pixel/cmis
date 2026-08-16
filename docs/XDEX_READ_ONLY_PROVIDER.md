# XDEX Read-Only Provider Contract Verification

Status: **provider transport implemented; live contract promotion gated**

This document records the XDEX API surface being verified for direct use by
the X1 Provider beneath CMIS. It deliberately separates user-supplied API
catalog information, observed endpoint behavior, candidate request contracts,
and fields that are safe to promote into CMIS.

## Ownership

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> XDEX public API
```

Roberta and X1 Scout must not call XDEX HTTP endpoints directly.

The direct XDEX provider added in this milestone is read-only. It does not
prepare, sign, or broadcast transactions.

## Base URL

```text
https://api.xdex.xyz
```

Use HTTPS. The user-supplied quote notes included an `http://` example, but
the supplied base URL and the public X1 client implementations use HTTPS.

## Network naming

The user-supplied endpoint catalog shows values such as:

```text
mainnet | testnet | devnet
```

However, direct probing of some chart endpoints with `network=mainnet` was
not sufficient, and public X1 clients use:

```text
X1 Mainnet
X1 Testnet
Solana Mainnet
Solana Devnet
```

The X1 direct provider therefore uses `X1 Mainnet` as the current **candidate
runtime contract**. This remains subject to the opt-in live contract probe.

## Current token price

Candidate request:

```text
GET /api/token-price/price
  ?network=X1%20Mainnet
  &address=<TOKEN_MINT>
```

The transport requires a top-level JSON object with:

```json
{
  "success": true,
  "data": {}
}
```

The provider preserves all `data` values as returned. It does not convert
missing fields to zero.

Public X1 clients currently reference candidate fields including:

- `price`
- `price_usd`
- `price_change_24h`
- `volume_24h`
- `market_cap`
- `liquidity`

These names are not automatically treated as independently verified CMIS
facts by the direct transport.

## Price history

The user-supplied catalog includes:

```text
GET /api/xendex/chart/history?network=mainnet
```

A request with only `network=mainnet` returned HTTP 400 during this milestone,
which shows that additional parameters are required.

Public X1 clients use this candidate request shape:

```text
GET /api/xendex/chart/history
  ?network=X1%20Mainnet
  &token=<TOKEN_MINT>
  &days=<POSITIVE_INTEGER>
```

Candidate response:

```json
{
  "success": true,
  "data": [
    {
      "timestamp": "...",
      "price": "...",
      "volume": "..."
    }
  ]
}
```

Some clients tolerate `time` instead of `timestamp`.

### CMIS integration gate

XDEX history must **not** be promoted into CMIS `historical_compare` or
`risk_check` until the live probe verifies:

- whether `timestamp`/`time` is UTC, epoch seconds, epoch milliseconds, or an
  ISO string;
- whether `price` is USD or another quote unit;
- whether points are token-wide or pool-specific;
- sampling interval and requested `days` semantics;
- whether historical coverage is complete enough for a requested comparison;
- whether the endpoint can return stale, interpolated, or aggregated points.

Until then, CMIS's existing local historical observations remain authoritative
for verified historical comparisons.

## Chart price endpoint

The user-supplied catalog includes:

```text
GET /api/xendex/chart/price?network=mainnet
```

A direct probe of that exact form returned HTTP 404 during this milestone.
No code is wired to this endpoint.

The implemented current-price transport uses `/api/token-price/price`, which
has a concrete address parameter in public X1 client code.

## Swap quote

Candidate request:

```text
GET /api/xendex/swap/quote
  ?network=X1%20Mainnet
  &token_in=<ADDRESS>
  &token_out=<ADDRESS>
  &token_in_amount=<POSITIVE_NUMBER>
  &is_exact_amount_in=true
```

`is_exact_amount_in` is treated as required because both the user-supplied
detailed quote contract and public X1 wallet code send it.

Public wallet code currently consumes candidate response fields:

- `data.outputAmount`
- `data.rate`
- optional `data.priceImpactPct`

The provider preserves those values without changing units.

### CMIS integration gate

Quote data must **not** yet feed `pre_trade_check` policy. The live probe must
first verify:

- input/output token unit conventions;
- whether amounts are UI units or raw integer units;
- exact meaning of `rate`;
- whether `priceImpactPct` is a fraction (`0.01 == 1%`) or percentage points;
- route/pool identity and whether it is included;
- quote freshness/expiry;
- fee fields and whether output is pre/post fee;
- behavior for insufficient liquidity and unsupported pairs.

## Swap prepare is out of scope

The endpoint:

```text
POST /api/xendex/swap/prepare
```

is intentionally not part of this provider milestone.

Transaction preparation belongs to the future Execution Agent / transaction
preparation boundary. Signing, broadcasting, value movement, or wallet
permission changes require human approval.

## Opt-in live verification

The live probe is intentionally excluded from ordinary deterministic CI.

Run:

```bash
RUN_XDEX_LIVE_TESTS=1 \
python -m unittest tests.test_xdex_live_contract -v
```

Defaults:

- history/current-price token: AGI mint
  `7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER`
- quote input: XNT market representation
  `So11111111111111111111111111111111111111112`
- quote output: XNM
  `AvNDf423kEmWNP6AZHFV7DkNG4YRgt6qbdyyryjaa4PQ`

These can be overridden with:

```text
XDEX_LIVE_TOKEN
XDEX_LIVE_QUOTE_TOKEN_IN
XDEX_LIVE_QUOTE_TOKEN_OUT
```

A passing live probe verifies only the fields asserted by the test. It does
not authorize CMIS promotion of undocumented units or semantics without an
explicit deterministic adapter and tests.
