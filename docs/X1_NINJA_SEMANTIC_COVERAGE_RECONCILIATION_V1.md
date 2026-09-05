# X1.Ninja Semantic Coverage Reconciliation v1

Status: implementation candidate under CMIS Issue #496.

## Purpose

This contract answers a different question from X1.Ninja route discovery:

> For the X1.Ninja fields and behaviors already represented by accepted CMIS evidence, which semantic claims are verified, partial, blocked, or unavailable?

Contract:

`x1_ninja_semantic_coverage_reconciliation/v1`

The only allowed statuses are:

- `verified`
- `partial`
- `blocked`
- `unavailable`

A verified status is never global by implication. Every verified family carries an explicit scope.

## Route-discovery prerequisite

Accepted v10 result:

`known_documented_api_route_count=5`

`known_documented_api_route_gap_count=0`

`all_known_documented_api_routes_covered_by_v9=true`

Therefore v11 does not add endpoints or browser capture.

It maps existing evidence to semantic status.

## Current semantic map

### Verified

#### pooled reserve roles / units

Status:

`verified`

Accepted basis: Issue #341.

Bounded semantic mapping:

`pooledBase -> RPC vault_1 / mint_1 scaled reserve`

`pooledQuote -> RPC vault_0 / mint_0 scaled reserve`

The proof used multiple independently verified exact pools and exact X1 RPC pool/mint/vault/decimals/reserve evidence.

This verified status does not mean every arbitrary Ninja pool can be trusted without exact identity and current evidence.

#### liquidity fact-time

Status:

`verified`

Accepted basis: merged PR #465.

The accepted repeated fact-time policy was satisfied by three unique verified revaluation events across three distinct pools with same-fact alignment to the exact X1 RPC XNT/USDC.X reserve-ratio reference and no intervening reference-pool transaction.

Accepted claim:

`liquidity_fact_time_verified=true`

Still false:

`x1_ninja_liquidity_usd_semantics_verified=false`

`liquidity_freshness_verified=false`

Fact time is not freshness.

## Partial

### priceNative semantics

Status:

`partial`

Issue #343 established bounded direction/reserve-ratio evidence.

Issue #345 remains open because only a subset of live pools matched the instantaneous gross reserve ratio in the original live evidence and provider fact-time/update-source semantics remain unresolved.

Do not promote:

- universal current `priceNative` semantics;
- provider update-source semantics;
- a universal `priceNative` fact-time contract;
- `priceUsd` from `priceNative`.

### trade-history semantics

Status:

`partial`

Accepted foundations include:

- response/container shape;
- row shape;
- bounded sample transaction-id cross-check;
- bounded maker/primary-signer comparison;
- provider-slot/RPC-slot comparison;
- wallet-level side cross-check where exact RPC reports support it.

Still unavailable globally:

- exhaustive history;
- retention;
- pagination/range semantics;
- transaction finality;
- provider timestamp semantics;
- amount/price units;
- provider ordering contract.

### OHLCV / history semantics

Status:

`partial`

Accepted foundations include request/response/candle shape and exact request scope.

CMIS verified-provider price backfill may accept XDEX historical closes only when they agree with corresponding X1.Ninja OHLCV closes for the exact pair/time scope.

Still unverified:

- X1.Ninja archive completeness;
- continuous coverage;
- complete asset lifetime;
- all pair/timeframe timestamp semantics;
- all quote-unit semantics;
- range/gap behavior;
- OHLCV freshness.

### delayed-vault / update behavior

Status:

`partial`

Issue #363 is closed with deterministic event-level delayed-link evidence.

One exact delayed link may be verified event evidence.

A bounded pattern-support policy also exists.

Still not established:

- longitudinal provider-wide departure pattern;
- universal provider fact-time;
- provider update-source semantics;
- freshness;
- universal catalog-price semantics.

## Blocked

### liquidity USD semantics

Status:

`blocked`

Current GitHub state verified before v11 construction:

- Issue #461: open;
- PR #470: open.

The final five-pool semantic proof remains required.

Until acceptance:

`x1_ninja_liquidity_usd_semantics_verified=false`

### liquidity freshness

Status:

`blocked`

Issue #459 remains open.

Liquidity fact-time cannot be converted into freshness.

Freshness requires the separate field-scoped current RPC corroboration and eligible valuation evidence path.

### rolling 24h volume / transaction freshness

Status:

`blocked`

Issue #459 explicitly keeps these fields unverified until CMIS proves:

- bounded on-chain 24h reconstruction;
- provider rolling-window semantics;
- provider transaction-count semantics.

## Unavailable

### verified asset-wide holder total

Status:

`unavailable`

Issue #304 / PR #305 is an accepted semantic correction, not holder-total proof.

Provider holder-looking values, RPC token-account counts, and unique token-account-authority counts remain different evidence classes.

The bounded XENCAT comparison observed different candidates, and CMIS intentionally does not collapse them into one "holder" number.

Still unavailable:

- enumeration completeness;
- counted-entity holder semantics;
- verified asset-wide holder total;
- wallet identity;
- beneficial ownership.

### usable trade-stream event semantics

Status:

`unavailable`

The route is documented and structured.

Repository evidence observed HTTP 403/access_denied for the tested credential.

No SSE event body was consumed.

Unavailable:

- current authenticated stream access;
- event schema;
- ordering;
- finality;
- reconnect;
- backfill;
- dropped-event detection;
- stream freshness.

### priceUsd semantics

Status:

`unavailable`

Current reserve-ratio, `priceNative`, fact-time, and liquidity work do not establish a universal direct semantic contract for provider `priceUsd`.

Do not infer `priceUsd` from `priceNative` or provider liquidity.

### source independence

Status:

`unavailable`

Same-fact agreement is not source independence.

Multiple provider observations or X1.Ninja/XDEX relationships must not be counted as independent market sources without a fact-specific accepted independence proof.

## Current distribution

The deterministic registry contains 13 semantic families:

- verified: 2
- partial: 4
- blocked: 3
- unavailable: 4

The distribution is intentionally conservative.

## Priority order

### Priority 1 — #470 / #461

Finish the five-pool X1.Ninja USD-liquidity semantic proof.

Do not close #461 until PR #470 meets its exact live acceptance conditions.

### Priority 2 — #459

After liquidity USD semantics are accepted, promote field-scoped liquidity freshness and separately prove rolling 24h volume/transaction freshness.

### Priority 3 — #345

Continue `priceNative` fact-time/update-source research independently.

This work must not weaken already accepted bounded reserve/fact-time evidence and must not widen tolerances merely to hide temporal mismatch.

## Web Discovery decision

v11 preserves:

`route_discovery_complete_for_known_documented_api=true`

`browser_capture_required_now=false`

`semantic_reconciliation_complete=true`

The word "complete" here means the repository status map is complete for the enumerated semantic families.

It does not mean all Ninja semantics are verified.

## Authority boundary

v11 preserves:

`discovery_state=DISCOVERED`
`provider_response_verified_globally=false`
`semantic_verification_complete_globally=false`
`freshness_verified_globally=false`
`source_independence_verified=false`
`public_service_promotion_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`event_body_consumption_authorized=false`
`request_replay_authorized=false`
`background_monitoring_authorized=false`
`cmis_promotable=false`
`execution_authorized=false`

## Non-goals

This contract does not:

- perform live X1.Ninja requests;
- reinterpret an open workflow as accepted evidence;
- close or promote #461/#470;
- close or promote #459;
- generalize #341 reserve semantics to unidentified pools;
- relabel holder-looking values;
- consume SSE events;
- prove source independence;
- add browser capture;
- expose Web Discovery publicly;
- authorize X1 Scout or ROBERTA reliance;
- construct/sign/broadcast transactions;
- move value.
