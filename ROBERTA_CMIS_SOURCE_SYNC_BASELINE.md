# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-08-25 (America/New_York)

Merge verified: 2026-08-26 — paired Roberta PR #226 and CMIS PR #269 are merged on both `main` branches.

This file is the compact cross-project synchronization baseline for source-of-truth documentation. It does not replace `ROBERTA_INTEGRATION_CONTRACT.md`, `ROBERTA_CMIS_ACCEPTED_BASELINE.md`, or `docs/CMIS_PRODUCT_ROADMAP.md`.

## Canonical authority path

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

- Roberta owns orchestration, policy coordination, specialist selection, and final synthesis.
- Chain Scouts own chain-specific planning and interpretation; they do not manufacture facts.
- CMIS owns deterministic freshness-sensitive verified facts, evidence, Proof Scores, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.
- Providers remain beneath CMIS.
- Fresh accepted CMIS/provider facts override remembered, checkpointed, RAG/source-mastery, Pyramid, or conversational live values.
- Missing evidence remains unknown/unavailable and is never converted into zero, false, or an LLM estimate.
- Proof Score remains separate from risk.
- `pre_trade_check` remains analysis-only and preserves `execution_authorized=false`.
- The working `liquidity_scout` namespace may remain during incremental migration as a compatibility identifier only.

## Current CMIS/Roberta capability baseline

```text
CMIS capability contract = 1.9.0
Phase 11 intelligence_foundation public_service_promoted = false
Phase 11 intelligence_foundation scout_reliance_promoted = false
```

The separately accepted Phase 12 wrapper is exactly:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

Solana remains unavailable/non-promoted for this service.

## Internal non-promoted foundations

Accepted on CMIS `main` and safe for documentation/source synchronization, but not Scout-callable by implication:

- deterministic descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership/non-beneficial-owner semantics;
- concentration-threshold alert evidence.

All remain internal/read-only/non-promoted and do not create public-service, Scout-reliance, behavioral/ownership, risk, or execution authority.

## Current promotion state

There is currently **no accepted next public intelligence/alert service, Scout-reliance promotion, or broader Verified Intelligence promotion**. Any future promotion requires a separate CMIS contract/roadmap acceptance gate and a separate Roberta/Scout adoption-readiness gate.

## Execution boundary

Roberta Controlled Execution remains locked/not started. No current source material, Learning System/Pyramid state, CMIS result, Scout report, Proof Score, risk result, alert state, pre-trade `PASS`, policy decision, or human approval authorizes transaction construction as an execution path, signing, broadcasting, custody, trading, bridge transfer, or autonomous value movement.
