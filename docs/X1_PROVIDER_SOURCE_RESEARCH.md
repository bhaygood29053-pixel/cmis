# X1 Provider Source Research

Research date: 2026-08-16

Tracking: #30

## Research boundary

This document records public-source evidence relevant to X1 Provider capability
planning. A public webpage or advertised feature is not automatically an
authoritative CMIS source. Every machine-readable contract must be verified by
deterministic provider tests before promotion into production CMIS behavior.

Status language:

- **Official documentation** — published by X1 or the official Warp Bridge.
- **Documented provider candidate** — a third-party provider publicly documents a machine-readable capability.
- **UI / implementation evidence** — a public product demonstrates the capability, but the stable machine-readable contract is not yet proven.
- **Unverified** — current access or semantics still require live contract testing.

## 1. X1.Ninja Developer API

Source: <https://x1.ninja/developers>

Current public documentation states:

- Base URL: `https://api.x1.ninja`
- Bearer API-key authentication.
- Free tier is currently available.
- Free tier documents pools, trades and OHLCV.
- Starter and Pro tiers are currently marked `SOON`.
- Pro adds a live trade stream.

Documented endpoints:

```text
GET /v1/pools
GET /v1/pools/{address}
GET /v1/trades/{address}
GET /v1/ohlcv/{address}
GET /v1/search
GET /v1/stream/trades
```

The public endpoint table describes:

- `/v1/pools` — pool prices, volume, liquidity and market cap;
- `/v1/pools/{address}` — reserves, token metadata and holders;
- `/v1/trades/{address}` — buys, sells and LP events;
- `/v1/ohlcv/{address}` — candles for `1m`, `5m`, `15m`, `1h`, `4h`, `1D`, up to 300 rows;
- `/v1/stream/trades` — Server-Sent Events live trade stream.

The documentation also specifies rate-limit headers and explicit HTTP error
semantics including 401, 403, 429 and upstream 503 behavior.

### CMIS implication

X1.Ninja is now a strong candidate source for:

- trade history;
- OHLCV history;
- reserves;
- holder evidence;
- live trade streaming.

Do not promote these solely from documentation. Verify response schemas, units,
asset identity, timestamps and freshness first.

## 2. X1.Ninja release / implementation evidence

Source: <https://x1.ninja/release-notes>

Release notes provide supporting evidence that X1.Ninja operates substantial X1
indexing and real-time infrastructure, including:

- wallet trade history and wallet metrics;
- indexed XDEX trades;
- holder data;
- real-time trade streaming;
- real-time new-pool detection;
- WebSocket/Geyser-based internal pipelines;
- archival-RPC use for some historical safety checks;
- on-chain reserve verification and vault mapping fixes.

This is useful evidence that the underlying infrastructure exists. It is not a
substitute for verifying the public API contract used by the X1 Provider.

## 3. Official X1 read-only node

Source: <https://docs.x1.xyz/validating/create-a-read-only-node>

Classification: **Official documentation**.

The official X1 node launch example includes:

```text
--full-rpc-api
--enable-rpc-transaction-history
--enable-extended-tx-metadata-storage
--rpc-pubsub-enable-block-subscription
```

### CMIS implication

A self-hosted X1 read-only node is a viable provider strategy for controlled RPC
history and block subscriptions. It also provides a path to reduce dependence
on a single third-party RPC source.

Operational retention, storage cost, catch-up behavior, finality semantics and
required historical depth still need engineering evaluation before selecting
this as production infrastructure.

## 4. X1Scroll

Source: <https://x1scroll.io/>

Classification: **Documented third-party provider candidate**.

The current public site states that X1Scroll provides:

- archival X1 JSON-RPC;
- transaction history from genesis to present;
- HTTP JSON-RPC on the free tier;
- WebSocket support on a paid Builder tier;
- a documented archival RPC URL shape.

### Important correction

An earlier public crawl/search result referenced a Yellowstone gRPC/Geyser
product. The current public page checked on 2026-08-16 does not clearly document
that product. Therefore Geyser access must be treated as **unverified** until a
current contract is rediscovered and tested.

### CMIS implication

X1Scroll is a candidate for:

- archive/history redundancy;
- secondary RPC;
- WebSocket-based event access.

Contract-test method coverage, retention claims, authentication, rate limits,
commitment/finality behavior, errors and availability before production use.

## 5. Official X1 Warp Bridge

Sources:

- <https://app.bridge.x1.xyz/>
- <https://app.bridge.x1.xyz/info>
- <https://app.bridge.x1.xyz/history>

Classification: **Official user-facing source; machine-readable contract not yet found**.

The public bridge identifies itself as a cross-chain bridge between Solana and
X1. The bridge surface exposes user-facing fields for:

- route;
- exchange rate;
- bridge fee;
- network fee;
- bridge status.

The Info page is labeled:

```text
Real-time status and configuration of the Warp Bridge
```

The History page is wallet-gated and describes bridge transaction history.

### Current gap

This research pass did not find a documented public read-only API contract for:

- bridge operational state;
- supported assets;
- capacity/limits;
- current fee schedule;
- transfer status;
- route configuration;
- freshness/observed time.

The bridge UI is therefore evidence that these concepts exist, not yet a stable
CMIS provider contract.

Do not treat a crawled `Offline - Checking...` UI string as a current bridge
health fact; it is only evidence that the interface has a bridge-status field.

## 6. X1 Prism

Source: <https://x1prism.com/>

Classification: **Bridge cross-check candidate**.

The public UI contains an `X1 Bridge / Warp Bridge — Solana ↔ X1` section with
fields for:

```text
Today In
Today Out
Net
TVL
```

During the public crawl these fields were placeholders rather than usable
values, and this research did not identify a documented machine-readable API or
prove the source of the values.

### CMIS implication

Keep X1 Prism as a candidate independent bridge-flow/TVL cross-check. Do not make
it authoritative until its data origin, refresh cadence and API contract are
verified.

## 7. FortiBlox

Sources:

- <https://docs.fortiblox.com/docs/explorer/intro>
- <https://docs.fortiblox.com/docs/nexus/security/rpc-proxy>

Classification: **Third-party candidate with mixed documentation maturity**.

FortiBlox Explorer documentation advertises X1 real-time blockchain data,
advanced analytics, portfolio/account tooling and developer-oriented data
capabilities.

The RPC Proxy documentation references FortiBlox RPC infrastructure but also
contains contradictory maturity language: portions are labeled planned or
coming while later sections describe functionality as if available.

### CMIS implication

Keep FortiBlox in the candidate registry but aggressively contract-test any
specific endpoint. Do not infer production availability from documentation
alone.

## 8. Recommended status changes

| Gap | Research status | Provider action |
| --- | --- | --- |
| RPC | Available | Keep current official RPC path; evaluate redundancy |
| Archive/history RPC | Candidate available | Test self-hosted X1 history and/or X1Scroll |
| General indexer | Partial | X1.Ninja demonstrates substantial indexing; discover stable public wallet contract |
| DEX pools/liquidity | Available | Existing X1.Ninja/XDEX path remains valid |
| Reserves/holders | Candidate available | Verify X1.Ninja pool-detail schema and cross-check on-chain |
| Trade history | Candidate available | Verify X1.Ninja trades contract |
| OHLCV | Candidate available | Verify X1.Ninja candle semantics |
| Direct XDEX history/quote | Still gated | Preserve issue #28 gates |
| Real-time trades | Documented candidate | Test X1.Ninja Pro SSE access and event semantics |
| General event streaming | Partial | Official self-hosted block PubSub + X1Scroll WebSocket are current candidates |
| Independent verification | Partial | Build same-fact cross-source checks |
| X1 Bridge Intelligence | Partial discovery / still a gap | Discover stable read-only Warp Bridge contract; Prism only as a candidate cross-check |

## 9. Verification checklist before CMIS promotion

For every newly integrated source:

1. Record source, endpoint/method, authentication and observed time.
2. Preserve the raw response or raw values required for provenance.
3. Verify token/pool identity by public address; do not merge by symbol/name.
4. Verify numeric units and decimals.
5. Verify timestamps, timezone/epoch units and freshness.
6. Verify pair direction and quote denomination.
7. Verify pagination/range limits and history completeness claims.
8. Verify error and rate-limit semantics.
9. Add malformed-response and unavailable-state tests.
10. Cross-check high-impact facts against direct on-chain evidence where possible.
11. Keep candidate/provider diagnostics separate from CMIS authoritative facts.
12. Never convert unavailable evidence into zero or a guessed value.

### Additional streaming checks

For SSE/WebSocket/subscription providers verify:

- reconnect behavior;
- duplicate events;
- ordering;
- commitment/finality;
- backfill semantics;
- dropped-event detection;
- heartbeat/freshness behavior.

### Additional bridge checks

Bridge Intelligence must independently verify, when available:

- bridge operational state;
- asset support;
- route/direction;
- capacity/limits;
- bridge and network fees;
- transfer state/history;
- source freshness;
- post-bridge XDEX liquidity and quote availability.

Network health, bridge health and market liquidity are separate facts.

## 10. Recommended work order

1. Add deterministic contract tests for X1.Ninja `/v1/trades/{address}`.
2. Add deterministic contract tests for X1.Ninja `/v1/ohlcv/{address}`.
3. Verify `/v1/pools/{address}` reserves/holders and cross-check on-chain.
4. Test whether `/v1/stream/trades` is actually accessible today; do not assume
   paid-tier availability from the endpoint table.
5. Compare self-hosted read-only X1 history against X1Scroll for archive needs.
6. Perform read-only network-contract discovery on the official Warp Bridge.
7. Investigate X1 Prism only as an independent bridge cross-check.
8. Keep direct XDEX quote/history promotion gated by issue #28 until its own live
   response semantics can be proven.

## Core rule

```text
Public documentation identifies candidates.
Deterministic provider tests establish authority.
CMIS preserves uncertainty until that verification is complete.
```
