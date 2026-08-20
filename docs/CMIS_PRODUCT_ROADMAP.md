# CMIS Product & Premium Service Roadmap

## Purpose

**CMIS — Cross-Chain Market Intelligence Service** is the deterministic evidence, verification, normalization, historical-intelligence, risk, bounded pre-trade, and promoted read-only intelligence layer beneath chain-specific Scouts.

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

The repository was originally created as **Liquidity Scout**. That name remains only as historical context and in the compatibility Python namespace `liquidity_scout`; it is not a second current authority layer.

Core principle: premium users may receive more depth, history, speed, automation, analytics, and access, but never a weaker or different definition of truth.

## Roadmap status — 2026-08-20

Accepted milestones:

- **CMIS Phase 10 — Solana read-only provider foundation: COMPLETE.**
- **Evidence Receipts + Proof Score: COMPLETE.**
- **Remaining X1 evidence gaps: CLASSIFIED at an explicit fail-closed capability boundary.**
- **Deterministic pre-trade trade-size analysis: COMPLETE.**
- **CMIS Phase 11 — read-only Verified Intelligence foundation: COMPLETE.**
- **CMIS Phase 12 — first public read-only Verified Intelligence service: ACCEPTED for X1.**
- **XDEX quote/history and route evidence: bounded field-by-field progress accepted.**

CMIS contract `1.9.0` preserves the Phase 11 `intelligence_foundation` as read-only and unpromoted as a whole while separately promoting exactly one Phase 12 service:

```text
concentration_change_intelligence/v1
accepted conclusion: top_account_concentration_change
initial chain: X1 only
```

For X1 the service is bounded, callable, read-only, publicly promoted, Scout-reliance promoted, and `execution_authorized=false`. For Solana it is unavailable/non-callable with promotion false and `execution_authorized=false`.

No controlled-execution milestone is active in CMIS.

## 1. Stable architecture and ownership

Roberta owns user intent, policy, coordination, and final explanation. Chain Scouts own chain-specific planning and interpretation. CMIS owns deterministic facts, evidence, proof, risk, capability eligibility, bounded pre-trade calculations, and accepted intelligence-service calculations. Providers own source transport/parsing beneath CMIS.

Roberta and Scouts must not manufacture provider facts, recompute CMIS proof/risk into a second source of truth, or promote unavailable evidence.

## 2. Verified-data foundation

### X1 / XDEX — COMPLETE / ACTIVE foundation

Accepted capabilities include exact identity, market/ranking support, tokenomics/authority facts, transaction/trade verification, provider-vs-chain reconciliation, persisted verification evidence, deterministic risk, bounded trade-size analysis, field/scope-specific route evidence, and fail-closed behavior for incomplete/stale/conflicting evidence.

Program-, pool-, route-, account-, or sample-scoped completeness remains distinct from asset-wide/global X1 completeness.

### Solana Phase 10 — COMPLETE read-only foundation

Accepted components include exact-mint identity, SPL Token and Token-2022 handling, canonical supply/authority evidence, configured Jupiter/Helius/DEX Screener evidence, deterministic cross-source checks, provenance-safe observation history, and bounded/partial read-only services where advertised.

Solana is not assumed to have X1 parity. Ranking, pre-trade execution modeling, trade verification, verified asset-wide activity, and the Phase 12 concentration-change service remain unavailable unless separately promoted.

## 3. Evidence quality and Verified Intelligence

### Evidence Receipts and Proof Score — COMPLETE / ACTIVE

Evidence Receipts preserve provenance, verification state, scope, freshness, disagreements, limitations, unresolved fields, and content-addressed identity. Proof Score remains separate from market risk.

### Phase 11 foundation — COMPLETE / STILL UNPROMOTED AS A WHOLE

Phase 11 established deterministic primitives for top-account concentration and compatible numeric change, neutral wallet activity, sanitized sparse history/comparison, and evidence-bound conclusions.

The top-level foundation remains:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
```

Broader concentration snapshots, wallet activity, sanitized history, and generic evidence-bound conclusions are not automatically added to `supported_services`.

### Phase 12 concentration-change intelligence — ACCEPTED / X1 ONLY

The first separately promoted intelligence service is:

```text
service: concentration_change_intelligence
contract: concentration_change_intelligence/v1
accepted conclusion: top_account_concentration_change
```

The public trust root is CMIS-owned evidence, not caller self-attestation. A request binds exact `chain=x1`, exact asset identity, and one canonical CMIS-owned `intelligence_evidence_id`; optional explicit/versioned threshold policy is allowed. Caller-supplied conclusions, full intelligence bundles, Evidence Receipts, or Proof Scores are rejected as trusted inputs.

The service preserves observed **top-token-account** scope. It does not convert token accounts into unique holders or beneficial owners. Optional threshold output is deterministic policy observation only (`WITHIN_THRESHOLD`, `AT_THRESHOLD`, `EXCEEDS_THRESHOLD`), not market risk or behavioral interpretation. `risk` remains null/separate.

Unsupported scope still includes generic `verified_intelligence`, public intelligence-evidence upload/storage, raw concentration snapshots as a separate service, wallet activity services, generic history services, holder/beneficial-owner identity, behavioral/intent labels, and Solana concentration intelligence.

## 4. Pre-trade analysis — COMPLETE foundation / bounded evidence

`pre_trade_check` remains analysis only. Accepted behavior includes requested notional evaluation, verified notional-to-liquidity ratio where evidence exists, versioned trade-size policy, freshness handling, and exact evidence-gated advanced fields.

Every current result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission or advice to execute a trade.

## 5. Product direction

### Layer A — Verified Data
Established substantially on X1 and as a bounded read-only foundation on Solana.

### Layer B — Verified Intelligence
The Phase 11 foundation is complete, and Phase 12 has now proven the promotion pattern by exposing one narrow X1 service through the canonical runtime/capability manifest. Future intelligence services require their own accepted service, evidence, chain-scope, and Scout-reliance contracts.

Potential future interpretation layers include wallet behavior profiles, relationship evidence, verified classifications, liquidity deterioration, abnormal authority/issuance behavior, historical-pattern interpretation, and broader cross-source disagreement intelligence. None is implied by the Phase 12 concentration service.

### Layer C — Early Warning
Future alerts require explicit evidence-backed scope, freshness, threshold, persistence, and classification semantics. No alert should imply ownership, intent, manipulation, or fraud beyond an accepted contract.

### Layer D — Cross-Chain Intelligence
- X1: mature active foundation plus first promoted Phase 12 intelligence service;
- Solana: Phase 10 read-only foundation complete, no Phase 12 concentration service yet;
- Ethereum: future explicit provider/verification milestone.

## 6. Premium capability candidates

Premium candidates include deeper wallet intelligence after classification contracts, wallet relationship evidence with non-ownership semantics, evidence-backed alerting, investigation/evidence export, developer/agent API access, longer retention where proven, chain-neutral capital-flow primitives, Ethereum support, and institutional audit/access-control capabilities.

Premium access never changes the verification standard.

## 7. Recommended implementation sequence from the current boundary

### Completed

1. deterministic pre-trade trade-size policy — **COMPLETE**;
2. Phase 11 concentration/wallet/history/evidence foundation — **COMPLETE**;
3. XDEX semantic/evidence work — **BOUNDED FIELD-BY-FIELD PROGRESS ACCEPTED**;
4. route-scoped pre-trade evidence seam — **COMPLETE**;
5. explicit concentration-threshold evaluator — **COMPLETE**;
6. Phase 12 `concentration_change_intelligence/v1` canonical runtime/capability promotion for X1 — **COMPLETE**.

### Next accepted-milestone candidates — NOT YET ACTIVE

7. add further public intelligence services only through separate accepted promotion contracts; do not widen the Phase 11 foundation implicitly;
8. define deterministic inference/classification contracts before whale, insider, bot, accumulator, distributor, market-maker, ownership, or behavioral labels;
9. add wallet relationship evidence only after identity/provenance/non-ownership semantics are accepted;
10. add alert rules only with explicit scope/freshness/threshold/persistence/evidence semantics;
11. deepen XDEX route/execution evidence field-by-field without using transaction preparation as a shortcut to proof;
12. mature Solana coverage field-by-field and promote any Solana intelligence service separately;
13. begin Ethereum only under an explicit capability table and acceptance plan;
14. productize investigation/evidence export and premium access only after deterministic services are stable.

None of these candidates is an execution milestone merely because it appears here.

## 8. Governance principles

1. Facts before interpretation.
2. Providers are candidate evidence, not automatic truth.
3. Unknown remains unknown.
4. Inference is labeled.
5. Evidence is reproducible.
6. Freshness is explicit.
7. Cross-chain normalization preserves chain provenance.
8. Risk and proof are separate.
9. Route/account scope is not asset-wide scope.
10. Public-service promotion is explicit and service-specific.
11. No autonomous execution by implication.
12. Premium does not change truth.

## 9. Strategic positioning

**CMIS is a blockchain evidence and intelligence service that converts raw market and chain activity into verified, explainable, machine-consumable intelligence.**

## 10. Relationship to Roberta

CMIS supplies verified facts, evidence receipts, proof strength, deterministic risk, bounded pre-trade evidence, and separately promoted read-only intelligence services. Chain Scouts investigate within their chain. Roberta coordinates, applies policy, and explains.

Roberta must not silently promote inference into a CMIS-verified fact, recalculate market/proof truth, collapse risk and evidence quality into one grade, or treat X1 service promotion as cross-chain promotion.

## 11. Success criterion

CMIS should answer clearly: what was reported, what can be verified, how strong/complete the evidence is, what deterministic policy/intelligence service concluded within its exact contract, and what remains unknown or unavailable.
