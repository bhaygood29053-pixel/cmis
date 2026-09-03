# CMIS Roadmap Reconciliation — 2026-09-03

This reconciliation records the accepted/current CMIS state after the latest Warp, FortiSwap, Theo, freshness, warning, and cross-project synchronization work. It does not promote unverified provider claims or change execution authority.

## Current accepted platform

- CMIS capability contract: `1.18.0`.
- `instant_x1_scan/v3`: accepted.
- Burn Intelligence v1: accepted.
- Discovery Intelligence v1: accepted.
- Field-scoped current-market freshness: accepted.
- Concentration Warning Intelligence v1: accepted and consumed end-to-end by ROBERTA.
- Cross-chain asset provenance v1: accepted as an internal deterministic foundation.
- Verified Bridge Route Evidence / Warp qualification v1: accepted as an internal deterministic foundation only.
- FortiSwap read-only provider foundation: accepted; provider assertions are not promoted to CMIS truth.
- Theo advisory-provider foundation: accepted fail-closed; no exact live Theo machine transport is accepted yet.
- Controlled Execution: unauthorized.

## Warp state — active flagship gate

Issue #407 is OPEN and remains the active semantic evidence gate.

Accepted acquisition/structural evidence:
- PR #412 — Warp machine-contract capture harness;
- PR #417 — official-app HAR observation path;
- PR #423/#424 — read-only Warp program-account inventory and structural evidence;
- PR #427 — metadata-only official HAR endpoint evidence.

Observed official same-origin GET endpoints:
- `https://app.bridge.x1.xyz/api/bridge/config`
- `https://app.bridge.x1.xyz/api/bridge/guardians`
- `https://app.bridge.x1.xyz/api/bridge/tvl?chain=sol&token=<token>`

These endpoint observations are real and provenance-backed, but the HAR did not include `response.content.text`. Therefore deterministic response-body hashing and route/status/backing/custody/timestamp field semantics are still unverified.

Current authority remains:

```text
semantic_contract_accepted=false
warp_qualified=false
scout_reliance_promoted=false
execution_authorized=false
```

PR #426 is the active narrow engineering slice for bounded rare Warp-owned account capture. It is structural discovery only and must not be treated as a semantic promotion.

## Corrected repository state

- Issue #407 was reopened because it had closed before its explicit semantic acceptance requirements were satisfied.
- PR #394 was closed as stale/superseded; CMIS 1.17 freshness had already been accepted through PR #386 and later reconciliation.
- The mirrored `ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md` was refreshed in both public repos with the same content blob.

## Next sequence

1. Finish #407 by capturing a deterministic official response body/fixture and proving route id, exact source/destination asset ids, status, backing, custody, timestamp/unit, and freshness semantics.
2. Accept/merge PR #426 only if its bounded structural evidence passes exact-head review; do not promote guessed binary roles.
3. After #407 passes, advance #409 — Bridge Supply + 24h/7d/30d Inflow/Outflow Intelligence.
4. Then advance #410 — Bridge -> XDEX Utilization Intelligence.
5. Only after a public CMIS bridge service / Scout-reliance contract is accepted should ROBERTA #314 consume live cross-chain bridge intelligence.

CMIS #363 remains parallel evidence research and is not the flagship blocker.

`execution_authorized=false`
