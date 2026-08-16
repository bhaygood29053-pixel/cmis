# X1 Provider Gap Register

Last updated: 2026-08-16

Tracking: #30

## Purpose

This register tracks data-source gaps beneath CMIS for the X1 chain provider.
It is not a list of features that Roberta or X1 Scout may call directly.

```text
Roberta
  -> X1 Scout
    -> CMIS
      -> X1 Provider
        -> X1-specific sources
```

Provider capabilities are classified as:

- **VERIFIED** — implemented and proven against the actual provider/data contract required by CMIS.
- **PARTIAL** — useful implementation or documented source exists, but coverage or semantics are incomplete.
- **BLOCKED** — groundwork exists but live verification cannot currently be completed without a real market/source condition.
- **MISSING** — no adequate verified provider capability exists yet.

Public documentation is evidence that a candidate capability exists. It is not
sufficient by itself to make the data authoritative inside CMIS.

## Current register

| Capability | Status | Current evidence | Required next step |
| --- | --- | --- | --- |
| X1 RPC current chain facts | VERIFIED | Existing `X1RPCProvider` plus official X1 mainnet RPC | Preserve current fail-closed semantics and provenance |
| RPC redundancy / archive history | PARTIAL | Official X1 read-only node supports transaction history; X1Scroll currently advertises archival JSON-RPC and paid WebSocket access | Contract-test a secondary/archive source and define failover rules |
| General transaction / wallet indexing | PARTIAL | Existing bounded RPC activity scanner; X1.Ninja publicly demonstrates indexed trade/wallet tooling | Discover and verify a stable machine-readable wallet/indexer contract before CMIS use |
| XDEX pool catalog / liquidity / volume | VERIFIED | Existing X1.Ninja/XDEX market provider | Preserve address identity and source timestamps |
| Pool reserves / holders | PARTIAL | X1.Ninja Developer API documents these in `/v1/pools/{address}` | Add deterministic contract tests and cross-check on-chain where possible |
| Pool trade history | PARTIAL | X1.Ninja documents `/v1/trades/{address}` | Verify side, amounts, decimals, signatures, LP-event semantics, timestamps and finality |
| OHLCV / market history | PARTIAL | X1.Ninja documents `/v1/ohlcv/{address}` | Verify timestamp units, price/quote units, pair direction, intervals and coverage before CMIS promotion |
| Direct XDEX price history | BLOCKED / PARTIAL | Transport and request discovery are implemented | Keep gated by issue #28 until live pair response semantics are proven |
| Direct XDEX swap quote | BLOCKED / PARTIAL | Read-only quote transport is implemented | Keep out of `pre_trade_check` until amount/rate/impact/route/fee/freshness semantics are proven |
| Real-time XDEX trades | PARTIAL | X1.Ninja documents `/v1/stream/trades` as a Pro SSE endpoint; paid tiers are currently marked SOON | Test current access, event schema, reconnect, ordering, duplicates and freshness |
| General chain event streaming | PARTIAL | Official self-hosted X1 node supports block PubSub; X1Scroll currently advertises WebSocket on paid tier | Choose and contract-test the required subscription strategy; do not assume undocumented Geyser access |
| Independent same-fact verification | PARTIAL | X1 RPC, X1.Ninja, direct XDEX and secondary provider candidates exist | Define deterministic cross-source checks for high-value facts |
| X1 Bridge Intelligence | MISSING / PARTIAL DISCOVERY | Official Warp Bridge exposes user-facing route/fee/status/history/info surfaces; X1 Prism exposes bridge-flow/TVL fields | Discover and verify a stable read-only bridge data contract; keep bridge state separate from XDEX liquidity |

## X1-only Bridge Intelligence

Bridge Intelligence is an X1-specific provider requirement in the current
architecture. It must not be automatically generalized to other chains.

CMIS must treat the following as separate fresh conditions:

```text
X1 network operational
  -> bridge operational
    -> requested asset bridgeable
      -> route/capacity usable
        -> XDEX liquidity available
          -> quote/routing available
```

Success at one stage must never be used as proof of the next stage.

When a stable read-only source is found, track where available:

- supported bridge assets;
- source and destination chains;
- bridge operational state;
- route configuration;
- capacity or limits;
- exchange/bridge/network fees;
- transfer state/history;
- source timestamp / freshness;
- post-bridge usable XDEX liquidity.

Bridge provider work is read-only market/infrastructure intelligence. Bridge
transaction preparation, signing, broadcasting and value movement remain
outside CMIS and require the later execution + human-approval boundary.

## Verification requirements

Before a PARTIAL capability can become VERIFIED:

1. Record exact source, endpoint/method, authentication and observed time.
2. Preserve raw provider values and explicit unavailable states.
3. Fail closed on malformed responses, missing required fields and undocumented units.
4. Keep `chain + public address` as the provider identity for non-native token assets; symbols/names remain metadata.
5. Verify timestamp units and freshness semantics.
6. Verify provider-specific units and directionality rather than inferring them.
7. Cross-check high-value facts against direct on-chain evidence where practical.
8. Add deterministic tests for success, unavailable, malformed and provider-error states.
9. Keep source provenance visible through the CMIS envelope.
10. Do not promote a capability based only on a website or marketing claim.

## Current priority

1. Verify X1.Ninja trade-history and OHLCV contracts.
2. Cross-check X1.Ninja reserves/holders against direct X1 evidence.
3. Evaluate archive/secondary RPC strategy.
4. Verify current SSE access and semantics.
5. Perform read-only Warp Bridge contract discovery.
6. Evaluate X1 Prism only as a bridge cross-check until its data origin/API is proven.
7. Preserve issue #28's direct-XDEX history/quote gates until a real usable pair allows verification.

## Core rule

```text
Unavailable data is a deterministic state.
It is not permission to invent a source, pair, route, quote, history series,
bridge capacity or provider semantic.
```
