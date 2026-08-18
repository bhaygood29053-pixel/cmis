# Roberta ↔ Chain Scout ↔ CMIS Integration Contract

## Purpose

This document defines the source-of-truth authority boundary between **Roberta**, chain-specific **Scouts**, and **CMIS — Cross-Chain Market Intelligence Service**.

The repository historically began as Liquidity Scout; that is prototype history, not a separate current authority layer.

```text
Roberta
  ↓
Chain Scout
  ↓
CMIS
  ↓
Chain Provider
```

Authority flows downward:

```text
Roberta → Chain Scout → CMIS → Chain Provider
```

Verified information flows upward:

```text
Chain Provider → CMIS → Chain Scout → Roberta
```

CMIS supplies deterministic facts, evidence, proof quality, risk analysis, bounded pre-trade analysis, and explicit uncertainty. Roberta owns user intent, policy, coordination, broader reasoning, approval boundaries, and final user-facing synthesis.

**CMIS Phase 10 is complete. CMIS Phase 11 read-only Verified Intelligence is complete. Roberta's separately named future Controlled Execution milestone remains locked/not started.**

---

## 1. Authority boundary

### Roberta owns

- user interaction and intent;
- user policy and stable context;
- specialist selection and coordination;
- cross-chain/higher-level reasoning;
- final user-facing synthesis;
- human-review/approval workflow boundaries.

Roberta does **not** own provider calculations, live market reconstruction, CMIS verification/proof rules, or transaction execution.

### Chain Scouts own

- chain-specific planning and interpretation;
- choosing allowed CMIS investigations for the user objective;
- preserving exact CMIS status, provenance, proof, limitations, and uncertainty;
- reporting structured specialist findings upward.

Chain Scouts do not manufacture provider facts or silently upgrade partial evidence.

### CMIS owns

- asset discovery/resolution;
- deterministic market collection/normalization;
- asset/pool aggregation only where scope is proven;
- rankings/history where supported;
- tokenomics/authority and burn/mint evidence where verified;
- verification evidence storage/lookup;
- independent-source comparison and data-quality rules;
- Evidence Receipts and Proof Scores;
- deterministic risk calculations;
- bounded analysis-only pre-trade calculations;
- read-only Verified Intelligence foundations;
- source timestamps, confidence, warnings, errors, and unavailable states;
- machine-readable capability eligibility.

### Providers own

Provider transport/parsing beneath CMIS, including X1.Ninja/XDEX, X1 RPC, Solana RPC, Jupiter, Helius, DEX/pool/indexer adapters, scanners, and verification plumbing.

Roberta and Scouts must not reproduce provider or CMIS calculations to manufacture a second market fact.

---

## 2. Source-of-truth rule

For freshness-sensitive market, liquidity, tokenomics, verification, proof, and risk facts:

> **Fresh accepted CMIS/provider evidence overrides remembered, checkpointed, or conversational values.**

Never invent or substitute unavailable values for price, liquidity, volume, holders, supply, rankings, burns/mints, addresses, pool identity, authority state, proof, risk, slippage, price impact, route, fees, or simulation.

If a fact cannot be verified, CMIS preserves the accepted unavailable/ambiguous/partial/conflict/insufficient-evidence state. Roberta preserves that state in synthesis.

---

## 3. Capability handshake

CMIS publishes runtime eligibility at:

```text
GET /v1/cmis/capabilities
```

The accepted Scout boundary currently requires capability schema `1` and CMIS contract `1.8.0` or a compatible newer contract.

Scouts fail closed on:

- unsupported/malformed capability schema;
- a contract below the accepted minimum;
- malformed/unclassified chain/service records;
- explicitly non-callable services;
- weakened Evidence Receipt / Proof Score declarations;
- missing or promoted Phase 11 `intelligence_foundation` boundaries;
- unknown chains.

The `intelligence_foundation` remains read-only and outside `supported_services`. Its primitives are not automatically callable by Scouts.

Roberta does not perform capability discovery directly. The handshake belongs to the **Chain Scout ↔ CMIS** boundary.

---

## 4. Shared public service surface

The Roberta/Scout contract includes, where the chain manifest permits:

- `asset_lookup`;
- `market_report`;
- `rank`;
- `historical_compare`;
- `tokenomics`;
- `risk_check`;
- `pre_trade_check`;
- `verification_evidence`.

Internal CMIS helpers may exist without becoming public services.

Common service statuses include `ok`, `partial`, `unavailable`, `ambiguous`, and `error`. Evidence states such as agreement, conflict, and insufficient evidence remain distinct from service status.

---

## 5. Chain-specific boundary

### X1

X1 is the mature CMIS surface. Accepted behavior includes market reporting, rankings/history, tokenomics, deterministic risk, verification evidence, trade/activity verification tooling, and bounded analysis-only pre-trade behavior where the manifest permits it.

X1 completeness remains scope-specific. Provider, program, pool, route, or sample evidence is not automatically asset-wide/global truth.

Recent XDEX work has promoted selected field-level semantics while preserving unresolved boundaries. Exact route/config identity, route-scoped price impact, selected quote/history semantics, and bounded historical 2800-ppm execution evidence exist for accepted tested scopes. This does not establish global route quality, fill quality, universal execution semantics, or a hidden fee/business attribution.

### Solana

Phase 10 added a separate Solana read-only provider/runtime path beneath the same CMIS contract.

Accepted foundation includes exact-mint identity, canonical RPC tokenomics, SPL Token/Token-2022 handling, bounded market/risk evidence, cross-source checks, provenance-safe observation history, and narrow historical comparison.

Solana rules include exact identity, no X1 fallback, scope preservation, and capability-specific fail-closed provider configuration. Solana is not assumed to have X1 parity.

---

## 6. Evidence Receipts and Proof Score

Normal CMIS results may carry deterministic Evidence Receipts and Proof Scores.

Roberta and Scouts must preserve:

- provider/source identity and role;
- verification state;
- proof strength/category state;
- observation time and chain position where available;
- freshness;
- scope;
- disagreements;
- limitations;
- unresolved fields.

Risk and proof are separate dimensions. Roberta may explain them but must not recompute CMIS proof or upgrade provider-reported evidence to independent verification.

---

## 7. Verified Intelligence foundation

CMIS Phase 11 established read-only foundations for:

- top-account concentration and compatible numeric changes;
- neutral verified wallet-activity facts;
- sanitized sparse intelligence history/comparison;
- evidence-bound conclusions.

A later deterministic helper can compare a canonical concentration change with an explicit versioned threshold, but that remains policy evaluation—not a whale/insider/accumulation/distribution/manipulation/risk conclusion and not a public Scout service.

No automatic behavioral or ownership labels are permitted from the Phase 11 foundation.

---

## 8. `verification_evidence`

`verification_evidence` is callable where the manifest permits.

Only accepted verified/promotable agreement may expose a promoted fact. Stale/non-promotable agreement, conflict, and insufficient evidence remain explicit.

Roberta requests evidence through the appropriate Scout and accepted selectors; it does not submit raw verifier/provider objects or reconstruct verification state.

---

## 9. `risk_check`

Risk outcomes are:

```text
PASS
WARN
BLOCK
```

Service status and risk severity are separate concepts. Roberta may explain a risk result but does not invent/recalculate market facts or risk scores.

---

## 10. `pre_trade_check` — bounded analysis only

CMIS can evaluate, where evidence permits:

- requested notional;
- verified liquidity;
- notional-to-liquidity ratio;
- explicit versioned trade-size policy;
- risk-evidence freshness;
- exact route-scoped internal evidence for selected advanced facts.

CMIS does not invent hidden default size/freshness policies.

The accepted internal route-evidence seam requires exact route identity, accepted producer/source, explicit freshness, accepted semantic/unit, and exact proof-basis requirements before a route capability becomes usable.

Current distinctions:

- route-scoped price impact may be available when exact accepted proof gates pass;
- bounded 0.28% AMM/execution-model fee evidence may be available for an exact accepted route/evidence scope;
- XDEX quote slippage tolerance is not expected execution slippage;
- expected execution slippage remains unavailable absent a separately accepted execution-slippage observation contract;
- route quality, bridge dependency, fill quality, transaction simulation, and generic execution quality remain unavailable unless separately proven.

The public HTTP gateway does not accept arbitrary caller-supplied internal `route_evidence` as a shortcut to verification.

Every current result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` means only that the deterministic checks actually performed did not produce WARN/BLOCK. It is not permission to trade.

Roberta explains the CMIS result but does not recalculate replacement size ratios, price impact, fees, slippage, routes, simulation, proof, or deterministic risk.

---

## 11. Failure rules

CMIS, Scouts, and Roberta must not:

- substitute memory for unavailable live facts;
- invent LPs, supply, holders, rankings, burns, mints, authorities, route facts, fees, price impact, slippage, or simulation;
- average conflicts unless an accepted deterministic contract permits it;
- promote a fact without required identity, units, semantics, freshness, scope, and independence;
- treat missing execution evidence as zero risk;
- silently route an unsupported chain elsewhere;
- bypass the capability manifest;
- treat internal intelligence primitives as public services;
- treat analysis or human review as signing authority.

---

## 12. Roberta consumption flow

1. Roberta preserves user intent and policy.
2. Roberta selects the relevant Chain Scout.
3. The Scout plans allowed chain-specific CMIS work.
4. The Scout-side CMIS client validates live capability eligibility.
5. CMIS/provider code collects/calculates deterministic facts.
6. CMIS returns structured evidence/proof/uncertainty.
7. The Scout interprets chain-specific meaning without inventing facts.
8. Roberta synthesizes the specialist result for the user.

If an estimate is unavailable, Roberta says it is unavailable.

---

## 13. Human approval and execution boundary

Human approval/review is a bounded review state, not a signing credential or reusable future authority.

No current CMIS/Scout result or Roberta review authorizes:

- transaction preparation for execution;
- wallet signing;
- broadcasting;
- custody;
- autonomous live trading;
- bridge transfer;
- value movement.

Roberta's future **Controlled Execution** milestone remains separately locked/not started. If ever promoted, it requires its own transaction construction/simulation, approval consumption/revalidation, signer/broadcast, replay-protection, precondition, and failure contracts. CMIS Phase 11 completion does not imply any of that authority.

---

## 14. Core principle

**CMIS determines what verified evidence supports now.**

**Chain Scouts determine what those verified facts mean within their chains.**

**Roberta determines how to coordinate and explain those specialist findings to the user.**

The system becomes more capable by proving more—not by guessing more.
