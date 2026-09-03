# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-03 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the public-facing product.
- Canonical path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration and final synthesis.
- Chain Scouts validate/compose accepted CMIS contracts and never manufacture chain facts.
- CMIS owns deterministic facts, freshness, evidence, Evidence Receipts, Proof Scores, risk, history, burn arithmetic, warning evidence, and bridge qualification evidence.
- Proof Score, warning state, bridge qualification state, and risk remain separate.
- Missing evidence remains unknown/unavailable.
- Controlled Execution remains locked. `execution_authorized=false`.

## Current public heads at reconciliation

- CMIS public `main`: `260e629cc51612c23ddd2aef6967aad4f9689fa8` (merged PR #427).
- ROBERTA public `main`: `5326f3899131653acd2d3c3b2ae47892f6bdaf80` (merged PR #319).
- Protected-core implementation remains authoritative for protected runtime behavior; this public sync file does not claim newer protected-core heads without separate verification.

## Accepted X1 intelligence stack

- Historical Coverage Proof v1: accepted with supported-pair vs USD-lifetime caveats preserved.
- Burn Intelligence v1: accepted under CMIS 1.15.
- Discovery Intelligence v1: accepted under CMIS 1.16.
- WHAT CHANGED? v1: accepted in ROBERTA without local market-delta or causal inference.
- Field-scoped current-market freshness: accepted under CMIS 1.17 / `instant_x1_scan/v3`.
- Persistent concentration Early Warning foundation: accepted through CMIS #396 / public #397 / protected `cmis-core` #15.
- Concentration Warning Intelligence v1: accepted under CMIS 1.18 through CMIS #399 / public #400 / protected `cmis-core` #16.
- ROBERTA Concentration Warning adoption: accepted through public ROBERTA #318 / protected `roberta-core` #28 / Issue #317.
- Cross-chain asset provenance foundation: accepted through CMIS #402 / PR #403.
- Verified Bridge Route Evidence / Warp qualification foundation: accepted internally through CMIS #405 / PR #406, but Warp is not yet semantically qualified.
- FortiSwap read-only provider foundation: accepted through CMIS #413 / PR #414; provider assertions are not CMIS truth and do not qualify bridge semantics.
- Theo bounded advisory-provider foundation: accepted through CMIS #418 / PR #420; no exact Theo machine transport is accepted yet, so live Theo connectivity remains fail-closed.

## Concentration Warning end-to-end semantics

CMIS exposes X1 `concentration_warning_intelligence/v1` as a bounded read-only pull-only service.

ROBERTA requires CMIS >= 1.18.0, preserves the validated CMIS warning object and its Receipt/Proof lineage without recomputation, keeps WATCH/CLEAR separate from deterministic risk, and exposes the same canonical warning to Human and Machine ROBERTA.

Authority remains:

```text
delivery_mode=pull_only
push_delivery_authorized=false
warning_level_is_risk_severity=false
risk_interpretation=null
execution_authorized=false
```

No background polling, subscription, Telegram push, webhook delivery, acknowledgement/retry queue, or execution authority is accepted by this milestone.

## Warp / cross-chain evidence state

**CMIS Issue #407 is OPEN and remains the flagship evidence gate.** It was reopened because its own acceptance criteria are not yet satisfied.

Accepted evidence now includes:
- PR #412: deterministic Warp machine-contract capture harness;
- PR #417: official-app HAR network observation path;
- PR #423/#424: read-only on-chain Warp program-account inventory and accepted structural evidence;
- PR #427: metadata-only official HAR observations from the official X1 bridge app.

Official same-origin read endpoints observed from `https://app.bridge.x1.xyz/info` include:
- `GET https://app.bridge.x1.xyz/api/bridge/config`
- `GET https://app.bridge.x1.xyz/api/bridge/guardians`
- `GET https://app.bridge.x1.xyz/api/bridge/tvl?chain=sol&token=<token>`

The HAR proved endpoint provenance plus HTTP 200/JSON metadata, but Chrome omitted `response.content.text`. Therefore response-body hashes and field semantics are still unverified. The accepted semantic-contract registry remains unpromoted and Warp must still be treated as `blocked_endpoint_semantics` until a deterministic response body/fixture proves route identity, exact source/destination asset identity, route status, backing, custody, timestamp/unit, and freshness semantics.

CMIS PR #426 is the active narrow engineering slice: bounded read-only capture of rare Warp-owned account families for later binary-layout/semantic discovery. It does **not** by itself qualify Warp or unblock downstream bridge intelligence.

## Current synchronized capability state

- CMIS capability contract: `1.18.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted.
- Field-scoped freshness: accepted.
- Concentration Warning Intelligence: accepted end-to-end through CMIS -> X1 Scout -> Canonical ROBERTA Decision Object.
- Warp bridge semantics: not yet accepted.
- Bridge supply/flow intelligence (#409): blocked behind #407 semantic acceptance.
- Bridge-to-XDEX utilization (#410): blocked behind the required bridge evidence/flow gates.
- ROBERTA cross-chain adoption (#314): queued behind accepted/promoted CMIS bridge semantics; do not start live Warp promotion yet.
- Push warning delivery: not authorized.
- Controlled Execution: unauthorized.

## Repository hygiene corrected during this reconciliation

- CMIS PR #394 was closed as stale/superseded because CMIS 1.17 freshness already merged through PR #386 and later reconciliation.
- ROBERTA PR #310 was closed as stale/superseded because the accepted freshness adoption already merged through PR #301 and later reconciliation.
- CMIS Issue #407 was reopened because it had been closed before its explicit semantic acceptance requirements were met.

## Next synchronized product direction

1. **Finish CMIS #407 semantics, not merely endpoint discovery.** Capture a deterministic official Warp response body/fixture and prove exact route/asset/status/backing/custody/timestamp/freshness semantics.
2. **Merge/accept only useful structural evidence from PR #426** without promoting binary-layout guesses into truth.
3. After #407 passes, build **CMIS #409 Bridge Supply + 24h/7d/30d Inflow/Outflow Intelligence**.
4. Then build **CMIS #410 Bridge -> XDEX Utilization Intelligence**.
5. Only after CMIS exposes an accepted public-service / Scout-reliance bridge contract should **ROBERTA #314** consume the cross-chain intelligence through X1 Scout.

CMIS #363 remains parallel delayed-vault/X1.Ninja evidence research and is not the flagship blocker.

## Core sync rule

**CMIS verifies facts, freshness, warning/bridge evidence, and qualification state. X1 Scout composes only accepted CMIS contracts. ROBERTA explains the same canonical evidence. No upper layer may silently recompute facts, freshness, warnings, bridge truth, risk, or execution authority.**

`execution_authorized=false`
