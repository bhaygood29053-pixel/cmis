# Scout ↔ CMIS Integration Contract

Last reconciled: 2026-08-20

## Boundary

```text
Roberta
  -> X1 Scout / Solana Scout
    -> CMIS
      -> Chain Providers / verified sources
```

Scouts interpret CMIS results. They do not call provider APIs, CMIS databases, or internal intelligence helpers directly, and they do not manufacture missing facts.

The compatibility runtime entry point may remain:

```bash
python -m liquidity_scout.cmis.http
```

The `liquidity_scout` namespace is a migration compatibility identifier, not a separate product/authority layer.

## Capability handshake

```text
GET /v1/cmis/capabilities
```

Capability schema `1` is required. Existing services retain the accepted global minimum `1.8.0`; current CMIS contract is `1.9.0`. The promoted concentration service requires CMIS `>=1.9.0`.

Scouts validate service state/callability, chain requirements, Evidence Receipt / Proof Score declarations, risk/proof separation, missing-evidence-is-unknown semantics, and exact promotion metadata.

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group.

## Public service surface

Where the live manifest permits:

```text
asset_lookup
market_report
rank
historical_compare
tokenomics
risk_check
pre_trade_check
verification_evidence
concentration_change_intelligence
```

`concentration_change_intelligence` is a separately accepted **Phase 12**, X1-only, bounded/read-only wrapper:

```text
service_contract = concentration_change_intelligence/v1
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

Solana is unavailable/non-callable/non-promoted for this service.

A Scout must validate these exact fields before dispatch and preserve the returned facts/evidence/proof/limitations without recomputation. The service does not establish unique-holder or beneficial-owner semantics and does not authorize whale/insider/bot/intent/ownership labels.

## Request/response rules

Every request names the chain explicitly. Unsupported chains do not fall back to another chain.

CMIS response statuses such as `ok`, `partial`, `unavailable`, `ambiguous`, conflict, or insufficient evidence are meaningful. Missing evidence remains missing; it is never converted into zero, false, or an LLM estimate.

Fresh accepted CMIS/provider evidence overrides remembered live values.

## X1

X1 is the mature CMIS surface. Evidence remains scope-specific: pool-, route-, provider-, program-, token-account-, or sample-scoped evidence is not automatically asset-wide/global truth.

The Phase 12 concentration wrapper is explicit-only in Roberta/X1 Scout adoption; it is not an autonomous planner capability merely because the service is callable.

## Solana

Solana Phase 10 is complete as a separate read-only provider path beneath the same CMIS architecture. Exact-mint identity, SPL Token / Token-2022 handling, bounded market/tokenomics/risk/history, and source cross-checks remain capability-specific and fail closed. Solana does not inherit X1 capabilities.

## Evidence, risk, and pre-trade

`verification_evidence` remains selector-bound. Evidence Receipt / Proof Score must be preserved; Proof Score is not risk.

`risk_check` is deterministic and separate from service status/proof strength.

`pre_trade_check` remains analysis only. Advanced route/slippage/fee/simulation facts are available only when independently proven for the exact accepted scope. Missing advanced evidence is not zero-filled.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Safety

No current Scout or CMIS contract authorizes transaction preparation for execution, signing, broadcasting, custody, live trading, bridge transfer, autonomous execution, or value movement.

**CMIS verifies. Scouts preserve and interpret chain-specific results. Roberta coordinates and explains.**
