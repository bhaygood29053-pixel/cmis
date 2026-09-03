# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-03 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the public-facing product.
- Canonical path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration and final synthesis.
- Chain Scouts validate/compose accepted CMIS contracts and never manufacture chain facts.
- CMIS owns deterministic facts, freshness, evidence, Evidence Receipts, Proof Scores, risk, history, burn arithmetic, and warning evidence.
- Proof Score, warning state, and risk remain separate.
- Missing evidence remains unknown/unavailable.
- Controlled Execution remains locked. `execution_authorized=false`.

## Accepted implementation heads before this reconciliation-only sync

- CMIS public `main`: `eaca9a29d5dd61f18e3d4a49416576908f42a318`
- protected `cmis-core` `main`: `20b4a1b28f59223dc0abebe5242cb94281726411`
- ROBERTA public `main`: `d62e920556e87d63fec391abc510245c84be7dff`
- protected `roberta-core` `main`: `eb2028e0097f93eb4bb276789f2a0f39211fc39a`

## Accepted X1 intelligence stack

- Historical Coverage Proof v1: accepted with supported-pair vs USD-lifetime caveats preserved.
- Burn Intelligence v1: accepted under CMIS 1.15.
- Discovery Intelligence v1: accepted under CMIS 1.16.
- WHAT CHANGED? v1: accepted in ROBERTA without local market-delta or causal inference.
- Field-scoped current-market freshness: accepted under CMIS 1.17 / `instant_x1_scan/v3`.
- Persistent concentration Early Warning foundation: accepted through CMIS #396 / public #397 / protected `cmis-core` #15.
- Concentration Warning Intelligence v1: accepted under CMIS 1.18 through CMIS #399 / public #400 / protected `cmis-core` #16.
- ROBERTA Concentration Warning adoption: accepted through public ROBERTA #318 / protected `roberta-core` #28 / Issue #317.

## Concentration Warning end-to-end semantics

CMIS exposes X1 `concentration_warning_intelligence/v1` as a bounded read-only pull-only service.

ROBERTA now:
- requires CMIS >= 1.18.0 and the exact promoted warning capability;
- accepts exactly two CMIS-owned intelligence evidence ids plus explicit threshold/freshness/window policy inputs;
- introduces no hidden defaults;
- preserves the validated CMIS canonical warning, policy, persistence, freshness, observations, Receipt ids, Proof Score records, and limitations;
- exposes stable X1 Scout product `x1_concentration_warning_intelligence/v1`;
- stores the same warning object unchanged in Canonical Decision Object `facts.warning`;
- gives Machine ROBERTA that same structured warning object;
- renders Human ROBERTA from the same Decision Object;
- keeps WATCH/CLEAR separate from deterministic risk;
- does not infer behavior, ownership, manipulation, fraud, intent, causality, or imminent price movement.

Authority remains:

```text
delivery_mode=pull_only
push_delivery_authorized=false
warning_level_is_risk_severity=false
risk_interpretation=null
execution_authorized=false
```

No background polling, subscription, Telegram push, webhook delivery, acknowledgement/retry queue, or execution authority is accepted by this milestone.

## Current synchronized capability state

- CMIS capability contract: `1.18.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted.
- Field-scoped freshness: accepted.
- Concentration Warning Intelligence: accepted end-to-end through CMIS -> X1 Scout -> Canonical ROBERTA Decision Object.
- Push warning delivery: not authorized.
- Controlled Execution: unauthorized.

## Next synchronized product direction

**CMIS Issue #407 — Warp endpoint / semantic-fixture qualification is the next exact evidence gate.**

The cross-chain provenance and bridge-route/Warp qualification foundations are already accepted internally, but Warp remains `blocked_endpoint_semantics`. Do not promote bridge truth to X1 Scout or ROBERTA until CMIS accepts exact endpoint semantics and a separate public-service / Scout-reliance contract.

ROBERTA Issue #314 remains queued behind that CMIS evidence/promotion boundary.

CMIS #363 remains parallel delayed-vault/X1.Ninja evidence research and is not the flagship blocker.

## Core sync rule

**CMIS verifies facts, freshness, and warning/bridge evidence. X1 Scout composes only accepted CMIS contracts. ROBERTA explains the same canonical evidence. No upper layer may silently recompute facts, freshness, warnings, bridge truth, risk, or execution authority.**

`execution_authorized=false`
