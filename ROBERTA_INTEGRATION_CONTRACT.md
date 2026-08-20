# Roberta ↔ Chain Scout ↔ CMIS Integration Contract

Last reconciled: 2026-08-20

## Canonical hierarchy

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider
```

Roberta owns orchestration, user policy, cross-chain coordination, approval boundaries, and final user-facing synthesis. Chain Scouts own chain-specific planning and interpretation, but do not manufacture facts. CMIS owns deterministic verified facts, evidence, Evidence Receipts, Proof Scores, risk, capability eligibility, historical intelligence, and bounded analysis-only pre-trade calculations. Providers remain beneath CMIS.

Fresh accepted CMIS/provider evidence overrides remembered, checkpointed, or conversational live-market values. Missing evidence remains unknown/unavailable; it is never converted into zero, false, or an LLM estimate. Risk and Proof Score remain separate dimensions.

The working Python namespace `liquidity_scout` may remain during incremental migration; it is a compatibility identifier, not a second authority layer.

## Capability handshake

CMIS publishes deployed eligibility at:

```text
GET /v1/cmis/capabilities
```

Capability schema `1` remains required. Existing accepted services retain the global minimum compatible contract `1.8.0`, while the current CMIS contract is `1.9.0` and the promoted concentration service requires `>=1.9.0`.

Scouts fail closed on malformed/incompatible manifests, non-callable services, unknown chains, weakened Evidence Receipt / Proof Score declarations, or promotion metadata that does not exactly match the accepted service contract.

The core Phase 11 `intelligence_foundation` remains read-only and non-promoted as a group:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
```

CMIS now also has accepted deterministic descriptive-classification and direct wallet-relationship evidence foundations. These remain internal/read-only/non-promoted and preserve `cmis_promotable=false` and `execution_authorized=false`. Their existence does not authorize Roberta or a Chain Scout to call internal helpers, treat them as public services, or infer behavioral/ownership conclusions.

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

The deterministic classification and wallet-relationship foundations are intentionally absent from this public service list because no separate public-service/Scout-reliance promotion contract has been accepted for them.

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

## Internal deterministic interpretation boundary

The accepted descriptive classification foundation may state only the exact concentration direction supported by canonical CMIS evidence. It does not convert that direction into whale, insider, accumulation/distribution intent, bot, manipulation, scam, ownership, or risk conclusions.

The accepted wallet-relationship foundation may state only verified observed direct token-transfer interactions between exact chain identities under a bounded compatible evidence set. It does not establish common ownership, beneficial ownership, coordinated control, intent, complete wallet history, or complete relationship-graph coverage.

Roberta and Chain Scouts may not rely on either foundation through the public service boundary unless a later promotion contract explicitly changes their eligibility.

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

## Next read-only intelligence boundary

Evidence-backed alerts are the next shared roadmap candidate. No alert becomes a public CMIS service or Scout-reliance capability until a separate accepted contract defines exact scope, freshness, threshold/policy identity, persistence semantics, triggering evidence, limitations, promotion state, and failure behavior.

An alert may report only the verified condition that crossed its explicit rule. It may not imply whale, insider, bot, common-owner, manipulation, fraud/scam, coordinated behavior, intent, or execution authority unless a separately accepted deterministic contract proves that exact conclusion.

## Human approval and execution boundary

Human review is exact-proposal review, not a reusable signing credential.

No current CMIS result, Scout report, Roberta policy decision, or human approval authorizes transaction preparation for execution, signing, broadcasting, custody, live trading, bridge transfer, or autonomous value movement.

Roberta Controlled Execution remains locked/not started.

## Core principle

**CMIS determines what verified evidence supports now. Chain Scouts preserve and interpret the chain-specific result. Roberta coordinates, applies policy, and explains the result to the user.**
