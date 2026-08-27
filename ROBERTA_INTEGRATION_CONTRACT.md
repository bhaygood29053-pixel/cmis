# Roberta ↔ Chain Scout ↔ CMIS Integration Contract

Last reconciled: 2026-08-26

## Canonical hierarchy

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider
```

Roberta owns orchestration, user policy, cross-chain coordination, learning-workflow coordination, approval boundaries, and final user-facing synthesis. Chain Scouts own chain-specific planning and interpretation, but do not manufacture facts. CMIS owns deterministic verified facts, evidence, Evidence Receipts, Proof Scores, risk, capability eligibility, historical intelligence, and bounded analysis-only pre-trade calculations. Providers remain beneath CMIS.

Fresh accepted CMIS/provider evidence overrides remembered, checkpointed, retained, source-mastery, Pyramid, or conversational live-market values. Missing evidence remains unknown/unavailable; it is never converted into zero, false, or an LLM estimate. Risk and Proof Score remain separate dimensions.

The working Python namespace `liquidity_scout` may remain during incremental migration; it is a compatibility identifier, not a second authority layer.

## Capability handshake

CMIS publishes deployed eligibility at:

```text
GET /v1/cmis/capabilities
```

Capability schema `1` remains required. Existing accepted services retain the global minimum compatible contract `1.8.0`, while the current CMIS contract is `1.12.0` and the promoted concentration service continues to require `>=1.9.0`.

Scouts fail closed on malformed/incompatible manifests, non-callable services, unknown chains, weakened Evidence Receipt / Proof Score declarations, or promotion metadata that does not exactly match the accepted service contract.

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
```

## Shared public service surface

Where the live manifest permits, the shared contract includes:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`
- `concentration_change_intelligence` — bounded X1-only promoted service under CMIS `1.9.0`

A runtime service does not become an autonomous Scout action merely because it exists.

## First promoted Verified Intelligence service — Phase 12

Phase 11 established the non-promoted read-only Verified Intelligence foundation. Phase 12 separately promotes exactly one narrow wrapper:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
execution_authorized = false
```

Solana is explicitly unavailable/non-callable/non-promoted for this service.

The request is bound to X1 plus exact asset context and a canonical CMIS-owned intelligence evidence id. CMIS resolves and revalidates the stored evidence internally. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state are not accepted as trust inputs.

The service does not convert token accounts into total unique holders or beneficial owners. It does not establish whale, insider, bot, accumulator, distributor, market-maker, manipulation, common-owner, relationship, or intent labels. Optional concentration-threshold output is deterministic policy evaluation, not risk. Proof strength does not become risk.

## Post-Phase-12 internal deterministic foundations

Accepted CMIS `main` foundations also include:

- deterministic descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership/non-beneficial-owner semantics;
- concentration-threshold alert evidence bound to canonical concentration evidence, exact identity, explicit threshold units/comparator, freshness, and deterministic evidence identity.

All remain internal/read-only/non-promoted. They do not create a new capability-manifest service, Scout dispatch authority, behavioral or ownership label, risk conclusion, or execution authority. There is currently no accepted next public intelligence/alert service or Scout-reliance promotion.

## Roberta autonomous Learning Plane boundary

Roberta Learning System Phases 1-10 are accepted on Roberta `main`, and PR #228's autonomous source-grounded Learning Plane is merged and accepted.

The Learning Plane may autonomously process an explicitly selected static source through provenance, curriculum, examination, remediation, retention/transfer verification, and curriculum-scoped learned-concept promotion. Exact active retained lessons may also be classified as `verified_learned_knowledge` under Roberta's accepted retention contract.

Those states are **not CMIS trust inputs**. They do not create or alter:

- current blockchain/market facts;
- provider verification or source independence;
- CMIS capability eligibility;
- public-service or Scout-reliance promotion;
- Evidence Receipt / Proof Score semantics;
- deterministic risk semantics;
- wallet permissions;
- execution authority.

For freshness-sensitive claims, Roberta must continue routing through the relevant Chain Scout -> CMIS -> provider path. A learned or retained value that conflicts with fresh accepted CMIS/provider evidence is subordinate to the fresh evidence.

## Historical intelligence modes

CMIS `1.10.0` extends the existing `historical_compare` service on X1 with deterministic `window`, `all_available`, and `all_available_pair` modes. Roberta does not compute lifetime market statistics herself.

For “entire/full/lifetime history” requests, X1 Scout should preserve the exact CMIS coverage window and distinguish:

- all verified history currently available to CMIS;
- the asset's actual lifetime, which remains unverified unless CMIS explicitly proves it;
- pairwise common-window results, which must use only overlapping verified history with accepted aligned anchors.

A missing earlier asset period is not zero-filled, interpolated, or inferred from model knowledge. CMIS `1.12.0` may extend the X1 price series with a narrow verified provider backfill: XDEX historical close observations must match the exact provider pair/time scope and cross-check against the corresponding X1.Ninja OHLCV close before persistence. The backfill is price-only, retains provider evidence/provenance, and does not establish source independence, archive completeness, continuous coverage, historical stable-quote peg behavior, or complete asset lifetime. Other external OHLCV/archive history remains unaccepted unless its own CMIS gates pass.

## Chain boundaries

### X1

X1 is the mature CMIS surface. Evidence completeness remains field- and scope-specific. Pool-, route-, provider-, program-, token-account-, or sample-scoped evidence must not be relabeled as global asset truth without an accepted aggregation/identity contract.

### Solana

Solana Phase 10 is complete as a separate read-only provider path beneath the same CMIS architecture. Exact-mint identity, SPL Token / Token-2022 handling, bounded market/tokenomics/risk/history, and configured source cross-checks remain capability-specific and fail closed. No Solana request may silently fall back to X1. Solana is not assumed to have X1 parity.

## Verification evidence

`verification_evidence` remains selector-bound. Only accepted verified/promotable agreement may expose a promoted fact. Conflict, stale/non-promotable evidence, insufficient evidence, and missing records remain explicit.

## Risk and pre-trade

`risk_check` outcomes such as `PASS`, `WARN`, and `BLOCK` are deterministic risk results, not Proof Scores.

`pre_trade_check` is analysis only. It may use verified notional/liquidity, explicit versioned policy, freshness rules, and selected exact-route facts only where their semantics are independently proven. Missing slippage, route, fee, bridge, fill, simulation, or execution-quality evidence is not zero-filled.

Every current pre-trade result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Human approval and execution boundary

Human review is exact-proposal review, not a reusable signing credential.

No current CMIS result, Scout report, Roberta policy decision, Learning Plane result, retained lesson, learned concept, or human approval authorizes transaction preparation for execution, signing, broadcasting, custody, live trading, bridge transfer, or autonomous value movement.

Roberta Controlled Execution remains locked/not started.

## Core principle

**CMIS determines what verified evidence supports now. Chain Scouts preserve and interpret the chain-specific result. Roberta coordinates, learns within bounded static-source rules, applies policy, and explains the result to the user.**
