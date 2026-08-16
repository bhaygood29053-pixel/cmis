# X1 Provider Gap Register

Status date: **2026-08-16**

This register tracks capability gaps beneath CMIS for the X1 Provider. It is a planning and verification document, not a source of live market facts.

Architecture boundary:

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> X1 RPC / X1.Ninja / XDEX / other verified X1 sources
```

Provider-specific endpoint discovery, contract verification, and transport logic belong in this repository. Roberta and X1 Scout must not call or reinterpret provider endpoints directly.

## Status vocabulary

- **VERIFIED** — the capability has a current deterministic implementation or an official/public contract that has been validated sufficiently for the stated scope.
- **PARTIAL** — useful capability exists, but coverage, redundancy, semantics, or CMIS promotion is incomplete.
- **CANDIDATE** — a provider advertises or demonstrates the capability, but CMIS has not contract-tested it enough for production use.
- **BLOCKED** — implementation exists or an endpoint is known, but a required live contract/semantic assumption is unresolved.
- **MISSING** — no production-ready provider path is currently available.

A public webpage, release note, UI, or advertised endpoint is evidence for investigation only. It does not become an authoritative CMIS source until deterministic request/response contracts and failure semantics are verified.

## Capability register

| ID | Capability | Status | Current evidence / implementation | Promotion requirement / next action |
|---|---|---|---|---|
| X1-RPC-01 | Core X1 RPC coverage | VERIFIED | Existing X1 RPC provider is in use. Official X1 documentation also supports a self-hosted read-only node with full RPC. | Preserve provider tests and explicit RPC provenance. |
| X1-RPC-02 | Historical transaction RPC | PARTIAL | Official X1 read-only-node documentation supports transaction history and extended transaction metadata storage. Current CMIS does not yet rely on a dedicated self-hosted historical node. | Decide self-hosted node vs secondary archival provider; test retention, finality, errors, and historical method coverage. |
| X1-RPC-03 | RPC redundancy / failover | PARTIAL | Official X1 RPC is available. X1Scroll and FortiBlox are possible secondary sources. | Contract-test a secondary RPC path before promoting it as failover. |
| X1-IDX-01 | General transaction / wallet indexer | PARTIAL | X1.Ninja publicly demonstrates deep XDEX trade/wallet indexing and wallet metrics, but a complete general wallet-indexer API surface is not yet established for CMIS. | Discover and test machine-readable wallet/indexer contracts; do not infer from UI/release notes alone. |
| X1-DEX-01 | Pool catalog / liquidity / volume | VERIFIED | X1.Ninja/XDEX catalog path is used by CMIS; direct XDEX public pool transport also exists as an independent provider-native path. | Maintain asset-wide aggregation, pool deduplication, timestamps, and source traceability. |
| X1-DEX-02 | Pool detail / reserves | PARTIAL | X1.Ninja documents pool detail including reserves. | Cross-check reserve values against direct X1 RPC/on-chain evidence and define exact units/freshness before high-confidence promotion. |
| X1-DEX-03 | Holder data | PARTIAL | X1.Ninja exposes holder information, but CMIS already preserves uncertainty when holder sources disagree or coverage is incomplete. | Cross-check holder semantics and coverage against independent/on-chain evidence where possible. |
| X1-HIST-01 | X1.Ninja trade history | PARTIAL | Public Developer API documents `/v1/trades/{address}` including buys, sells, and LP events. | Add deterministic contract tests for pagination/range, side classification, token amounts/decimals, USD-value source, LP-event semantics, signature, finality, and stale behavior. |
| X1-HIST-02 | X1.Ninja OHLCV | PARTIAL | Public Developer API documents `/v1/ohlcv/{address}` with 1m, 5m, 15m, 1h, 4h, and 1D timeframes. | Verify timestamp unit, pair direction, quote unit, interval semantics, requested-range coverage, gaps, stale/interpolated behavior, and provenance before CMIS history promotion. |
| X1-HIST-03 | Direct XDEX chart/history | BLOCKED | Read-only transport and request-shape discovery exist in `docs/XDEX_READ_ONLY_PROVIDER.md`, but exact live pair/response semantics remain gated. | Verify timestamp, price/quote units, pair direction, interval, range coverage, and exact current pool identity before use by `historical_compare` or risk. |
| X1-QUOTE-01 | Direct XDEX read-only quote | BLOCKED | Quote transport exists, but live token-supply and native-XNT handling have produced unresolved provider errors. | Verify an exact current non-XNT pair; then validate amounts, rate, route identity, fees, expiry/freshness, and `priceImpactPct` semantics before any pre-trade promotion. |
| X1-STREAM-01 | X1.Ninja real-time trades | PARTIAL | `/v1/stream/trades` is publicly documented as SSE, but current production access/tier availability remains unverified. | Probe access without assuming Pro availability; test reconnect, duplicate events, ordering, backfill, dropped-event detection, and freshness. |
| X1-STREAM-02 | General chain real-time stream | PARTIAL | Official self-hosted X1 node documentation supports block PubSub; X1Scroll advertises Yellowstone gRPC/Geyser. | Evaluate self-hosted block PubSub vs candidate Geyser source; verify commitment/finality, reconnect, ordering, backfill, and retention. |
| X1-XCHECK-01 | Same-fact independent verification | PARTIAL | Potential sources include official X1 RPC, X1.Ninja, direct XDEX, a self-hosted node, X1Scroll, and FortiBlox. | Define deterministic cross-check rules per fact type instead of treating provider count as confidence by itself. |
| X1-BRIDGE-01 | Bridge operational state | MISSING | Official Warp Bridge UI visibly exposes chain/bridge status, but no stable documented public read-only API has been verified. | Discover the UI's machine-readable source and contract-test it before CMIS use. |
| X1-BRIDGE-02 | Supported bridged assets / representations | PARTIAL | Warp Bridge UI visibly exposes bridged token mappings and distinguishes chain-side representations. CMIS now has a canonical asset/representation registry that can model these relationships. | Discover exact bridge configuration/source; verify source/destination chain, address identity, decimals, representation kind, and route support. |
| X1-BRIDGE-03 | Bridge fees / route capacity | MISSING | Official bridge UI has route/fee/network-fee surfaces, but no verified machine-readable contract is registered in CMIS. | Discover endpoint/account source and verify units, freshness, capacity meaning, fee components, and failure semantics. |
| X1-BRIDGE-04 | Bridge transfer state / history | MISSING | Official bridge UI exposes history/status concepts; X1 Prism exposes bridge-flow/TVL fields as a candidate cross-check. | Identify an authoritative read-only transfer-status/history source; verify transaction identifiers, source/destination finality, guardian state, and replay/retry semantics. |
| X1-BRIDGE-05 | Guardian set / guardian health | PARTIAL | The observed Warp Bridge UI exposes a guardian list with chain/public-key/status information. This is UI evidence only. | Identify the underlying source and verify guardian identity, quorum/threshold semantics, status freshness, and whether UI `Healthy`/`Live` labels are deterministic provider facts. |
| X1-BRIDGE-06 | Bridge-flow / TVL independent verification | CANDIDATE | X1 Prism exposes Today In, Today Out, Net, and TVL fields, but data origin/API contract is not proven. | Use only as an independent candidate until its machine-readable contract and provenance are verified. |
| X1-ALT-01 | X1Scroll archival RPC / Geyser | CANDIDATE | X1Scroll advertises archival RPC, historical queries, WebSocket/streaming, and Yellowstone gRPC. | Validate auth, supported methods, retention, commitment/finality, latency, reconnect behavior, quotas, and errors. |
| X1-ALT-02 | FortiBlox explorer / RPC ecosystem | CANDIDATE | FortiBlox documents explorer/analytics and RPC-related infrastructure, with mixed live/planned maturity. | Verify each endpoint independently and keep planned functionality out of production capability claims. |

## Warp Bridge UI evidence recorded on 2026-08-16

The supplied Warp Bridge screenshot is evidence that the user-facing bridge surface can display structured bridge state. It visibly includes:

- separate chain-status cards for Solana and X1;
- bridged-token entries showing source/destination-side asset representations;
- bridge transfer/activity summary information;
- a guardian set with chain, public-key, and status fields.

This is **not** evidence of a stable public API and is not enough to promote any bridge value into CMIS. The next bridge task is source discovery: identify whether these fields are loaded from an HTTP API, chain/RPC account, embedded configuration, WebSocket/SSE stream, or another machine-readable source.

## CMIS promotion rules

Before any PARTIAL, CANDIDATE, BLOCKED, or MISSING capability is promoted to production CMIS logic:

1. Record exact provider/source, endpoint or account contract, observed-at time, authentication requirements, rate limits/quotas, and raw response shape.
2. Fail closed on malformed success envelopes, missing required fields, stale data, undocumented units, or ambiguous identities.
3. Treat chain + verified address/mint as authoritative for token representations; symbols and names remain metadata unless a canonical registry mapping explicitly says otherwise.
4. Preserve canonical asset identity separately from provider/DEX/bridge representations.
5. Record completeness and uncertainty; never replace missing values with zero.
6. Add deterministic unit/contract tests before CMIS promotion.
7. Add an opt-in live verification test where the capability is freshness-sensitive or provider-contract dependent.
8. Preserve source role and timestamp in the CMIS envelope.
9. For same-fact cross-checks, define deterministic disagreement behavior instead of averaging incompatible facts.

### History / OHLCV checks

Verify:

- timestamp field and unit;
- pair/base/quote direction;
- quote currency/unit;
- candle interval semantics;
- requested-range coverage;
- missing candles/gaps;
- stale/interpolated/aggregated behavior;
- provider provenance and observed-at time.

### Trade-history checks

Verify:

- buy/sell side definition;
- token amount units and decimals;
- USD-value source;
- LP-event semantics;
- transaction signature/identifier;
- commitment/finality;
- pagination/range coverage;
- duplicates and ordering.

### Reserve / holder checks

Cross-check against X1 RPC/on-chain state where practical. A provider's reported reserve or holder count is not automatically a verified on-chain total.

### SSE / Geyser / PubSub checks

Verify:

- authentication and access tier;
- reconnect behavior;
- duplicate events;
- ordering;
- commitment/finality;
- backfill behavior;
- dropped-event detection;
- stream freshness and heartbeats.

### Bridge checks

Bridge Intelligence is an X1-provider capability and remains separate from ordinary DEX polling. Verify independently:

- bridge operational state;
- source and destination chains;
- canonical asset and both chain-side representations;
- supported asset/route status;
- route capacity and its exact meaning;
- bridge fee and network-fee units/components;
- transfer identifier and lifecycle state;
- source/destination finality;
- guardian set, threshold/quorum, and health freshness;
- post-bridge XDEX liquidity when economic usability is relevant.

## Immediate work order

1. **Register created** — this document is the baseline.
2. Add deterministic contract tests for X1.Ninja `/v1/trades/{address}`.
3. Add deterministic contract tests for X1.Ninja `/v1/ohlcv/{address}`.
4. Cross-check X1.Ninja pool reserves/holders against direct X1 RPC evidence.
5. Probe current X1.Ninja SSE access without assuming the documented Pro tier is live.
6. Evaluate a self-hosted X1 read-only node versus X1Scroll for history/streaming redundancy.
7. Perform read-only Warp Bridge source discovery and contract verification.
8. Evaluate X1 Prism only as an independent bridge-flow/TVL cross-check until provenance is proven.

## Source registry

Research basis dated 2026-08-16:

- X1.Ninja Developer API — `https://x1.ninja/developers`
- X1.Ninja Release Notes — `https://x1.ninja/release-notes`
- Official X1 read-only node documentation — `https://docs.x1.xyz/validating/create-a-read-only-node`
- X1Scroll — `https://x1scroll.io/`
- Official Warp Bridge — `https://app.bridge.x1.xyz/`
- X1 Prism — `https://x1prism.com/`
- FortiBlox Explorer docs — `https://docs.fortiblox.com/docs/explorer/intro`
- FortiBlox RPC Proxy docs — `https://docs.fortiblox.com/docs/nexus/security/rpc-proxy`
- Existing direct-XDEX contract record — `docs/XDEX_READ_ONLY_PROVIDER.md`

Research boundary: this register records capability evidence and integration status. It does not certify provider uptime, current endpoint access, response accuracy, or contractual stability unless the specific row is explicitly marked verified for that scope.
