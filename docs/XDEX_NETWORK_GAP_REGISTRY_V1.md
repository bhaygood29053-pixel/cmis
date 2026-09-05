# XDEX Network Gap Registry v1

Status: implementation candidate under CMIS Issue #483.

## Purpose

This contract answers a narrow architectural question:

> Does XDEX need browser/network capture to expose useful read-only information that CMIS cannot already obtain from direct machine endpoints?

Current answer:

`browser_capture_required_now=false`

The reason is not that the XDEX frontend has no additional behavior. The reason is that every currently known useful uncovered read-only surface is already available as a direct machine-readable GET endpoint.

Contract:

`xdex_network_gap_registry/v1`

## Covered read-only surfaces

Already covered by `xdex_structured_discovery/v1`:

1. `https://api.xdex.xyz/api/xendex/pool/list`
2. `https://api.xdex.xyz/api/token-price/price`
3. `https://api.xdex.xyz/api/xendex/chart/history`
4. `https://api.xdex.xyz/api/xendex/swap/quote`

These remain discovery/transport identities only until their existing CMIS semantic verification contracts actually run.

## Direct read-only gap candidates

### Frontend quote alias

`https://api.xdex.xyz/api/xdex/swap/quote`

CMIS already has live evidence comparing this deployed frontend route with the accepted research route:

`/api/xendex/swap/quote`

The existing live test requires tested output/config/price-impact values to match when both aliases respond successfully.

This makes the frontend alias a useful direct read-only structured-discovery candidate. It does not make alias equivalence universal or permanent.

### XDEX Oracle token price

`https://oracle.xdex.xyz/api/v1/token/price`

Existing CMIS evidence probes:
- one exact token;
- another exact token;
- `all=true&details=true`.

The Oracle remains part of the XDEX source family. It is not independent from XDEX merely because it uses another hostname.

### XDEX Oracle sell quote

`https://oracle.xdex.xyz/api/v1/token/sell-quote`

Existing scoped evidence verifies `amount_out_quote` as a no-fee constant-product curve reference for tested XENCAT/native-XNT sizes.

It is not:
- fee-complete;
- slippage-adjusted;
- an executable quote;
- route-optimality proof;
- independent market data.

## Execution-adjacent exclusions

The following are explicitly excluded:

- `https://api.xdex.xyz/api/xendex/swap/prepare`
- `https://api.xdex.xyz/api/xdex/swap/prepare`

The deployed frontend references prepare behavior, and existing research uses that fact as implementation corroboration only.

CMIS did not invoke prepare in the evidence work, and Web Discovery must not silently reclassify it as read-only because it shares the word `swap` with a quote path.

Both GET and POST attempts to these exact paths remain:

`execution_adjacent_excluded`

with:

`execution_authorized=false`

## UI-only candidates

Routes on `app.xdex.xyz` / `xdex.xyz`, including known surfaces such as swap, liquidity, and alpha, remain UI-only candidates unless a separate machine endpoint is identified.

A UI route proves only that a web surface exists.

It does not prove:
- an API contract;
- a response schema;
- data freshness;
- token identity;
- market semantics;
- an execution contract.

## Classifications

The registry uses:

- `covered_read_only`
- `read_only_gap_candidate`
- `execution_adjacent_excluded`
- `ui_only_candidate`
- `unknown`

A URL classification is not semantic verification.

## Browser-capture decision

The current gap set contains three useful read-only candidates:

1. frontend quote alias;
2. Oracle token price;
3. Oracle sell quote.

All three are direct machine-readable GET endpoints.

Therefore:

```text
all_known_read_only_gaps_direct_machine_access = true
browser_capture_required_now = false
```

The correct next contract is:

`xdex_extended_readonly_structured_discovery/v1`

That contract should add explicit structured/query validation for:
- `/api/xdex/swap/quote`;
- `oracle.xdex.xyz/api/v1/token/price`;
- `oracle.xdex.xyz/api/v1/token/sell-quote`.

Only after those direct surfaces are exhausted should XDEX browser capture be reconsidered.

## Authority boundary

The registry does not fetch or replay anything.

Every record preserves:

`discovery_state=DISCOVERED`
`surface_identity_verified=false`
`provider_response_verified=false`
`semantic_verification_complete=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`request_replay_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

## Non-goals

This contract does not:
- perform a live request;
- inspect browser traffic;
- launch Playwright;
- discover undocumented endpoints dynamically;
- call swap prepare;
- prepare/sign/broadcast transactions;
- authorize route execution;
- treat Oracle as independent from XDEX;
- promote public CMIS or Scout reliance;
- move value.
