# X1.Ninja Structured Discovery v1

Status: implementation candidate under CMIS Issue #490.

## Purpose

This contract begins source-specific X1.Ninja interpretation beneath the accepted CMIS Web Discovery foundation.

Contract:

`x1_ninja_structured_discovery/v1`

The contract recognizes only X1.Ninja read-only routes that already have provider/evidence implementations inside CMIS. It does not create a second X1.Ninja transport, history engine, liquidity model, or freshness path.

## Supported Developer API surfaces

### Pool catalog

`GET https://api.x1.ninja/v1/pools`

Optional query parameters:

- `limit` — positive integer syntax only;
- `offset` — non-negative integer syntax only.

The structured layer records:

`pagination_semantics_verified=false`

because URL syntax does not prove catalog exhaustiveness, stable ordering, offset semantics, or retention.

Verification handoff:

- `ninja_pool_catalog.fetch_pool_catalog_raw`;
- existing `market.fetch_all_pools`;
- later pool/token/liquidity/freshness semantic gates.

### Pool detail

`GET https://api.x1.ninja/v1/pools/{address}`

The address path segment must decode as a 32-byte Base58 X1/SVM candidate.

This proves syntax only:

`pool_identity_verified=false`

Reserve-like provider fields remain lexical candidates until the existing pool-detail / pooled-reserve / vault / X1 RPC contracts prove their roles and units.

### Trade history

`GET https://api.x1.ninja/v1/trades/{address}`

The address path segment must decode as a 32-byte Base58 candidate.

No query parameter is accepted by v1.

Existing provider row-shape evidence remains authoritative for structure. The structured layer does not promote:

- trade side;
- amount units;
- USD derivation;
- LP-event meaning;
- transaction signature;
- finality;
- pagination/range semantics.

### OHLCV

`GET https://api.x1.ninja/v1/ohlcv/{address}`

Required query:

- `tf`

Accepted timeframes are the current CMIS provider contract values:

- `1m`
- `5m`
- `15m`
- `1h`
- `4h`
- `1D`

Optional:

- `limit` — positive integer, maximum 300.

No other query parameter is accepted.

The structured layer does not promote:

- candle timestamp units;
- pair direction;
- quote units;
- interval semantics;
- range completeness;
- gap behavior;
- stale/interpolated behavior;
- freshness.

### Trade-stream access

`GET https://api.x1.ninja/v1/stream/trades`

This route is represented only as an **access/handshake candidate**.

The accepted CMIS provider module probes the HTTP/SSE handshake and deliberately does not consume the event body.

The structured result therefore requires:

`handshake_only=true`
`event_body_consumption_authorized=false`
`event_schema_verified=false`
`event_ordering_verified=false`
`event_finality_verified=false`
`reconnect_semantics_verified=false`
`backfill_semantics_verified=false`
`stream_freshness_verified=false`

No stream event becomes CMIS market data through this contract.

## Website classification

Allowlisted `https://x1.ninja/` pages may be classified as `website` candidates.

This is bounded Web Discovery only. A website page does not prove API semantics, chain identity, liquidity, price, freshness, or source independence.

## Authentication boundary

X1.Ninja Developer API provider fetches use Bearer authentication.

Structured discovery does not perform a provider request and never accepts credentials as URL evidence.

Credential-like query keys such as:

- `api_key`
- `apikey`
- `authorization`
- `bearer`
- `access_token`
- `token`
- `secret`
- `password`

fail closed.

Every result preserves:

`authentication_material_retained=false`

Actual API keys remain transport configuration outside Web Discovery output.

## Verification handoff

The trust path remains:

```text
X1.Ninja URL / page
  -> X1.Ninja Structured Discovery
     discovery_state=DISCOVERED
  -> existing X1.Ninja provider contract
  -> exact semantic/X1 RPC corroboration gate
  -> only proven fields may become CMIS truth
```

Important existing handoff families include:

- pool catalog contract;
- pool detail contract;
- pooled reserve semantics;
- priceNative / reserve-ratio evidence;
- trade-history membership and execution evidence;
- OHLCV/history semantics;
- liquidity USD semantics;
- current-market fact-time/freshness evidence;
- delayed-vault correlation research.

The structured parser does not merge or upgrade those gates.

## Truth state

Every supported route remains:

`discovery_state=DISCOVERED`
`x1_ninja_route_verified=true`
`pool_identity_verified=false`
`provider_response_verified=false`
`price_semantics_verified=false`
`liquidity_semantics_verified=false`
`history_semantics_verified=false`
`freshness_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

Route verification means only that CMIS understands the URL/query shape.

## Non-goals

This contract does not:

- call the live Developer API;
- retain API credentials;
- claim pool identity from a path alone;
- assign reserve or liquidity meaning from field names;
- promote price/liquidity USD semantics;
- establish provider freshness;
- claim source independence;
- consume SSE event bodies;
- launch a browser;
- replay requests;
- expose Web Discovery as a public CMIS service;
- authorize X1 Scout or ROBERTA reliance;
- construct, sign, broadcast, or execute transactions;
- move value.

## Next step after acceptance

After v9 is accepted, the next X1.Ninja Web Discovery step should be a **network/API gap inventory**:

- reconcile all known X1.Ninja endpoints already present in CMIS;
- identify any useful read-only machine surface not covered by v9;
- keep delayed-vault/liquidity/freshness semantic work separate from route discovery;
- add browser capture only if a specific material fact cannot be reached through the direct API/provider contracts.
