# Roberta ↔ Chain Scout ↔ CMIS Integration Contract

Last refreshed: 2026-08-20

## Purpose

This document defines the source-of-truth authority boundary between **Roberta**, chain-specific **Scouts**, and **CMIS — Cross-Chain Market Intelligence Service**.

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider
```

The repository historically began as Liquidity Scout; that is prototype history, not a separate current authority layer. The compatibility Python namespace `liquidity_scout` remains intentionally unchanged during the staged identity migration.

CMIS supplies deterministic facts, evidence, proof quality, risk analysis, bounded pre-trade analysis, explicit uncertainty, and separately promoted read-only intelligence services. Roberta owns user intent, policy, coordination, broader reasoning, approval boundaries, and final user-facing synthesis.

**CMIS Phase 10 and Phase 11 are complete. Phase 12 has promoted one narrow X1-only read-only intelligence service. Roberta Controlled Execution remains locked/not started.**

## 1. Authority boundary

### Roberta owns
- user interaction and intent;
- user policy and stable context;
- specialist selection and coordination;
- cross-chain/higher-level reasoning;
- final user-facing synthesis;
- human-review boundaries.

Roberta does not own provider calculations, live market reconstruction, CMIS verification/proof rules, trusted intelligence evidence, or transaction execution.

### Chain Scouts own
- chain-specific planning and interpretation;
- choosing allowed CMIS investigations;
- preserving exact CMIS status, provenance, proof, limitations, and uncertainty;
- reporting structured findings upward.

### CMIS owns
- deterministic collection/normalization;
- verification and source comparison;
- Evidence Receipts and Proof Scores;
- deterministic risk and bounded pre-trade calculations;
- capability eligibility;
- Phase 11 read-only intelligence foundations;
- promoted Phase 12 read-only intelligence-service calculations and CMIS-owned intelligence evidence;
- timestamps, confidence, warnings, errors, and unavailable states.

Providers own transport/parsing beneath CMIS. Roberta and Scouts must not reproduce provider or CMIS calculations to manufacture a second market fact.

## 2. Source-of-truth rule

Fresh accepted CMIS/provider evidence overrides remembered, checkpointed, or conversational values. Missing or conflicting facts remain unavailable/partial/conflict/insufficient as defined by CMIS. Roberta may explain but not upgrade them.

## 3. Capability handshake

CMIS publishes runtime eligibility at:

```text
GET /v1/cmis/capabilities
```

The accepted Scout boundary requires capability schema `1` and **CMIS contract `1.9.0` or a compatible newer contract**.

Scouts fail closed on malformed/incompatible capability state, unknown chains, explicitly non-callable services, weakened Evidence Receipt/Proof Score requirements, or invalid promotion state.

The Phase 11 `intelligence_foundation` remains read-only and outside ordinary public Scout service promotion. Its top-level flags remain `public_service_promoted=false` and `scout_reliance_promoted=false`.

Phase 12 does not change that foundation boundary. Instead, it separately promotes exactly one narrow service contract where the per-chain manifest permits it.

Roberta does not perform provider calls or capability bypasses directly; the handshake belongs to the Chain Scout ↔ CMIS boundary.

## 4. Shared public service surface

The CMIS contract includes, where the chain manifest permits:

- `asset_lookup`;
- `market_report`;
- `rank`;
- `historical_compare`;
- `tokenomics`;
- `risk_check`;
- `pre_trade_check`;
- `verification_evidence`;
- `concentration_change_intelligence`.

A service existing in CMIS does not imply every chain can call it or that every Scout may invoke it autonomously. The live manifest is authoritative.

## 5. Chain-specific boundary

### X1

X1 is the mature CMIS surface. In addition to existing market, tokenomics, risk, verification, historical, and bounded pre-trade capabilities, CMIS `1.9.0` promotes:

```text
service: concentration_change_intelligence
contract: concentration_change_intelligence/v1
accepted conclusion: top_account_concentration_change
state: bounded
callable: true
read_only: true
public_service_promoted: true
scout_reliance_promoted: true
execution_authorized: false
```

The request is evidence-ID bound to CMIS-owned canonical intelligence evidence. Caller-supplied conclusions, full intelligence bundles, Evidence Receipts, or Proof Scores are not trusted inputs. Facts preserve observed top-token-account scope and must not be relabeled as unique-holder or beneficial-owner truth.

Optional explicit/versioned concentration-threshold policy can return only deterministic policy observations such as `WITHIN_THRESHOLD`, `AT_THRESHOLD`, or `EXCEEDS_THRESHOLD`. This is not a market-risk conclusion or behavioral classification; `risk` remains separate/null for this service.

### Solana

Solana Phase 10 remains a bounded read-only provider/runtime path under the shared CMIS contract. Exact identity, no X1 fallback, scope preservation, and capability-specific fail-closed configuration remain mandatory.

`concentration_change_intelligence` is currently **unavailable and non-callable on Solana**, with public/Scout promotion false and `execution_authorized=false`.

## 6. Evidence Receipts and Proof Score

Roberta and Scouts preserve provider/source identity, verification state, proof strength, observation time/chain position where available, freshness, scope, disagreements, limitations, and unresolved fields. Risk and proof are separate dimensions. Neither Roberta nor a Scout recomputes CMIS proof or upgrades provider-reported evidence to independent verification.

## 7. Phase 11 foundation and Phase 12 promoted service

CMIS Phase 11 established read-only foundations for top-account concentration/change, neutral wallet activity, sanitized sparse intelligence history, and evidence-bound conclusions.

Those broader primitives remain non-public/non-automatic as a foundation. Phase 12 promotes only `concentration_change_intelligence/v1` for X1. It does **not** promote raw concentration snapshots as a separate service, wallet activity, generic sanitized history, generic `verified_intelligence`, public intelligence-evidence upload/storage, holder/beneficial-owner identity, or behavioral/intent labels.

No automatic whale, insider, bot, accumulator, distributor, market-maker, manipulation, ownership, relationship, or intent label is permitted.

## 8. `verification_evidence`

`verification_evidence` is callable where the manifest permits. Only accepted verified/promotable agreement may expose a promoted fact. Stale/non-promotable agreement, conflict, insufficient evidence, and missing records remain explicit.

## 9. `risk_check`

Risk outcomes are `PASS`, `WARN`, and `BLOCK`. Service status, proof strength, policy observations, and risk severity are separate concepts. Roberta may explain a risk result but does not invent/recalculate market facts or risk scores.

## 10. `pre_trade_check` — bounded analysis only

CMIS may evaluate requested notional, verified liquidity, notional-to-liquidity ratio, explicit versioned trade-size policy, freshness, and accepted route-scoped evidence. Missing execution evidence remains unavailable rather than zero or guessed.

Every current result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade. Roberta explains the CMIS result but does not recalculate replacement market, route, fee, slippage, proof, or risk facts.

## 11. Failure rules

CMIS, Scouts, and Roberta must not substitute memory for unavailable live facts; invent missing values; silently route an unsupported chain elsewhere; bypass the capability manifest; treat the Phase 11 foundation as wholesale public services; treat X1 Phase 12 promotion as Solana promotion; convert token-account concentration into holder/beneficial-owner claims; accept caller self-attestation as trusted intelligence proof; or treat analysis/human review as signing authority.

## 12. Roberta consumption flow

1. Roberta preserves user intent and policy.
2. Roberta selects the relevant Chain Scout.
3. The Scout plans allowed chain-specific CMIS work.
4. The Scout-side client validates live capability eligibility.
5. CMIS/provider code collects/calculates deterministic facts or resolves trusted CMIS-owned evidence.
6. CMIS returns structured evidence/proof/uncertainty.
7. The Scout interprets chain-specific meaning without inventing facts.
8. Roberta synthesizes the result for the user.

## 13. Human approval and execution boundary

Human approval is a bounded review state, not a signing credential or reusable future authority. No current CMIS/Scout result or Roberta review authorizes transaction preparation as an execution precursor, wallet signing, broadcasting, custody, live trading, bridge transfer, autonomous execution, or value movement.

Roberta's future **Controlled Execution** milestone remains separately locked/not started. CMIS Phase 12 does not imply execution authority.

## 14. Core principle

**CMIS determines what verified evidence supports now.**

**Chain Scouts determine what those verified facts mean within their chains.**

**Roberta determines how to coordinate and explain those specialist findings to the user.**

The system becomes more capable by proving more—not by guessing more.
