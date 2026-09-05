# X1.Ninja Network/API Gap Inventory v1

Status: implementation candidate under CMIS Issue #494.

## Purpose

This contract reconciles the X1.Ninja Developer API surface already known to CMIS after accepted v9 structured discovery.

Contract:

`x1_ninja_network_api_gap_inventory/v1`

The inventory separates four concepts that must not be collapsed into one another:

1. direct route coverage;
2. access limitations;
3. semantic verification gaps;
4. advertised capabilities without a stable machine contract.

The current expected direct-route result is:

`known_documented_api_route_count=5`

`known_documented_api_route_gap_count=0`

`all_known_documented_api_routes_covered_by_v9=true`

This is scoped to the documented Developer API inventory currently owned by the repository.

It does not claim universal X1.Ninja endpoint completeness.

## Documented Developer API routes

The accepted research inventory contains exactly these five documented routes:

- `/v1/pools`
- `/v1/pools/{address}`
- `/v1/trades/{address}`
- `/v1/ohlcv/{address}`
- `/v1/stream/trades`

v9 must continue to recognize all five.

The first four are classified as:

`covered_read_only_route`

The trade stream is classified as:

`access_limited_route`

because the route is known and structured even though current repository evidence records an HTTP 403/access-denied observation for the credential used in that bounded probe.

That 403 is repository evidence, not a permanent provider claim:

`live_current_access_verified=false`

and:

`access_limitation_is_route_gap=false`

## Access limitation is not route discovery

A known route can be inaccessible to current credentials while still being fully covered by structured discovery.

For the trade stream:

- route identity is known;
- v9 route syntax is accepted;
- current repository evidence observed access denied;
- event body was not consumed;
- no event schema/order/finality/backfill/freshness semantics were inferred.

Therefore the gap inventory must not count the stream as a missing endpoint.

## Semantic gaps

The following remain separate verification work.

### Pool identity / reserves / holders

Route coverage does not prove:

- pool identity;
- reserve roles;
- reserve units;
- token decimals;
- holder counted-entity semantics;
- enumeration completeness;
- wallet identity;
- beneficial ownership.

### Trade history

Route coverage does not prove:

- side classification;
- token amount units;
- USD-value source;
- LP-event meaning;
- signature/finality;
- pagination/range;
- duplicate behavior;
- stable ordering.

### OHLCV

Route coverage does not prove:

- timestamp units;
- pair direction;
- quote units;
- interval semantics;
- requested-range coverage;
- gaps;
- stale/interpolated behavior;
- freshness.

### Liquidity USD / fact time / freshness

The pool routes do not by themselves prove:

- provider liquidity USD meaning;
- stable-quote/USD equivalence;
- provider field fact time;
- current freshness.

Those remain under the existing X1.Ninja liquidity/fact-time/freshness evidence gates.

### Delayed vault departure

Delayed reserve/vault departure behavior is a provider-to-chain semantic problem.

It is not evidence of a missing API route.

### Stream events

Even if authenticated access later succeeds, route coverage does not prove:

- event schema;
- event ordering;
- finality;
- reconnect behavior;
- backfill behavior;
- dropped-event detection;
- freshness.

Event body consumption remains unauthorized by Web Discovery.

## Advertised capabilities without machine contract

Public research/release notes support broader X1.Ninja capabilities such as:

- general wallet/indexer behavior;
- wallet metrics.

CMIS does not currently own an exact stable Developer API route for those broader capabilities.

They are classified as:

`capability_without_machine_contract`

The inventory explicitly records:

`invented_endpoint_authorized=false`

A release-note capability must not be converted into a guessed path such as `/v1/wallets`, `/v1/metrics`, or any other invented URL.

## Browser decision

Current decision:

`browser_capture_required_now=false`

Reasons:

- all five known documented Developer API routes are already structured by v9;
- access-limited SSE is not a route-discovery gap;
- semantic gaps belong in provider/X1 RPC verification;
- wallet/indexer capabilities lack an exact machine contract and should not be reverse-engineered into truth through browser scraping without a specific material requirement.

Browser/network capture may be reconsidered only when a specific useful fact is shown to exist solely behind browser behavior.

## Recommended next contract

`x1_ninja_semantic_coverage_reconciliation/v1`

The next task should map each v9 route to its existing semantic evidence gates and identify which field families are:

- accepted;
- bounded/partial;
- unavailable;
- still pending promotion.

That reconciliation should not reopen endpoint discovery unless a new exact route is first evidenced.

## Truth boundary

The gap inventory itself preserves:

`discovery_state=DISCOVERED`
`provider_response_verified=false`
`semantic_verification_complete=false`
`freshness_verified=false`
`source_independence_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`event_body_consumption_authorized=false`
`request_replay_authorized=false`
`background_monitoring_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

## Scope warning

The output:

`known_documented_api_route_gap_count=0`

means only that the current repository-known documented Developer API inventory is fully covered by v9.

It does not mean:

- X1.Ninja has no undocumented endpoints;
- future documentation cannot add endpoints;
- current credentials can access every route;
- route responses are semantically verified;
- source independence is established;
- provider freshness is proven.

## Non-goals

This contract does not:

- make a live X1.Ninja request;
- use credentials;
- consume SSE events;
- discover undocumented routes dynamically;
- invent wallet APIs;
- launch a browser;
- replay requests;
- promote liquidity/history/freshness;
- expose Web Discovery publicly;
- authorize Scout reliance;
- construct/sign/broadcast transactions;
- move value.
