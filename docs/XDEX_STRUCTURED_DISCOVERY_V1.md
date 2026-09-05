# XDEX Structured Discovery v1

Status: implementation candidate under CMIS Issue #479.

## Purpose

This contract adds source-specific XDEX endpoint interpretation beneath the accepted CMIS Web Discovery foundation.

Contract:

`xdex_structured_discovery/v1`

The structured layer does not create a new XDEX transport or verification path. It recognizes URLs that correspond to the existing accepted read-only CMIS XDEX provider and maps them back into that provider plus the existing X1 RPC / semantic evidence gates.

## Accepted machine surfaces

The current CMIS XDEX transport defines these read-only public API URLs:

- `https://api.xdex.xyz/api/xendex/pool/list`
- `https://api.xdex.xyz/api/token-price/price`
- `https://api.xdex.xyz/api/xendex/chart/history`
- `https://api.xdex.xyz/api/xendex/swap/quote`

The XDEX Web Discovery source also allows documentation under:

- `https://xdexdocs.gitbook.io/xdex/`

No other API path is inferred or accepted by this contract.

In particular, transaction-preparation endpoints such as `/swap/prepare` remain outside structured discovery.

## Endpoint classes

### pool_list

Required query:

- `network`

Handoff:

- `XDEXReadOnlyProvider.pool_list`
- existing X1 RPC XDEX program/pool/config/vault verification where stronger pool identity is required.

### token_price

Required query:

- `network`
- `token_address`

The token address must decode as a 32-byte Base58 X1/SVM address candidate.

Handoff:

- `XDEXReadOnlyProvider.token_price`
- existing CMIS price/evidence semantic gates.

### price_history

Required query:

- `network`
- `from_token`
- `to_token`
- `time_from`
- `time_to`

The token identifiers must be distinct 32-byte Base58 address candidates. Times must be positive integers and `time_to > time_from`.

Handoff:

- `XDEXReadOnlyProvider.price_history`
- existing accepted XDEX history semantics.

The structured layer does not relabel compact provider fields such as `o/h/l/c/v/t`.

### swap_quote

Required query:

- `network`
- `token_in`
- `token_out`
- `token_in_amount`
- `is_exact_amount_in`

The mint candidates must be distinct valid 32-byte Base58 identifiers. Input amount must be a positive finite decimal. `is_exact_amount_in` must be explicit `true` or `false`.

The optional `slippage` query parameter may be preserved as raw query metadata because CMIS already has scoped XDEX slippage evidence. This structured layer does not itself promote the slippage semantics.

Handoff:

- `XDEXReadOnlyProvider.swap_quote`
- existing route/config/reserve/quote semantic verification.

This contract never calls transaction preparation, signing, or broadcast.

### documentation

Any allowlisted XDEX GitBook path under `/xdex` may be retained as documentation candidate evidence.

Documentation is corroborating evidence only. It is not a live market-data source or chain truth.

## Query policy

The parser fails closed on:

- missing required parameters;
- empty required parameters;
- duplicate parameters;
- unknown parameters outside the explicit endpoint allowlist;
- malformed Base58 identifiers;
- same-token history/quote requests;
- invalid time windows;
- non-positive/non-finite quote amounts;
- non-boolean `is_exact_amount_in`.

This prevents a URL from silently acquiring semantics because its parameter names merely look familiar.

## Network labels

The structured result records whether the supplied network label matches one of the currently recognized CMIS XDEX labels:

- `mainnet` for the existing pool-list contract;
- `X1 Mainnet` for existing token-price/history/quote contracts.

A recognized label is not proof that a fresh response is current or correct.

## Existing CMIS verification remains authoritative

The structured layer does not replace:

- XDEX route discovery;
- exact XDEX program/pool/config/vault verification;
- X1 RPC reserve verification;
- XDEX quote semantic gates;
- history timestamp/OHLC evidence;
- slippage/price-impact evidence;
- evidence freshness rules.

Example:

```text
XDEX quote URL
  -> XDEX Structured Discovery
     xdex_route_verified=true
     quote_semantics_verified=false
  -> XDEXReadOnlyProvider.swap_quote
  -> exact XDEX route/config/reserve verification
  -> accepted field-level semantic gate
  -> only verified fields become CMIS truth
```

## Third-party implementation corroboration

A public X1 integration was observed at:

- repository: `Xenian84/x1pays`
- ref: `main`
- commit: `73497fbc5b44ff63c4712094f653fff440ec1b5c`

Its `@x1pay/dex` package independently corroborates:

- XDEX mainnet program `sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN`;
- 637-byte pool-state discovery;
- mint-pair memcmp filtering;
- AMM config and vault reads;
- constant-product pool math.

This repository is third-party implementation corroboration only. It is not treated as an independent XDEX market-data source, and it does not prove XDEX API deployment semantics.

## Truth boundary

Every supported endpoint remains:

`discovery_state=DISCOVERED`
`xdex_route_verified=true`
`provider_response_verified=false`
`pool_identity_verified=false`
`quote_semantics_verified=false`
`history_semantics_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

A valid endpoint URL proves only that the URL/query shape is understood.

## Non-goals

This contract does not:

- discover undocumented XDEX endpoints;
- prepare a swap transaction;
- invoke `/swap/prepare`;
- select an optimal route;
- claim fill quality;
- recalculate quote semantics;
- treat X1Pays as independent market evidence;
- launch a browser;
- replay captured requests;
- authorize public CMIS or Scout use;
- sign, broadcast, custody, trade, or move value.

## Next extension

After acceptance, the next XDEX Web Discovery issue should add **sanitized XDEX network observation** only if it provides useful information beyond the already machine-readable API surfaces.

Unlike X1 Explorer, XDEX already exposes direct JSON APIs, so browser capture should not be added by default. The next issue should first prove what additional frontend/network evidence is actually missing.
