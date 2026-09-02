# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-02 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Product identity and authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- Canonical authority path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration, policy coordination, specialist selection, learning coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning, contract validation, and interpretation; they do not manufacture blockchain facts.
- CMIS owns deterministic freshness-sensitive facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, burn arithmetic, and bounded analysis-only calculations.
- Missing evidence remains unknown/unavailable; it is never converted into zero, false, infinity, or a model estimate.
- Proof Score remains separate from risk.
- Controlled Execution remains locked/not started. `execution_authorized=false` remains invariant.

## Accepted implementation heads before this baseline-only sync

- CMIS public `main`: `a412d078a05629aa09d338c117d945820b465f58`
- protected `cmis-core` `main`: `1e39e7d1e1af19a167fc946d51f5e2a12090de99`
- ROBERTA public `main`: `f4480ca6424f645fc02bbf4f68858fd14e543755`
- protected `roberta-core` `main`: `bf7e6d737bb7726ead3db1b048a190fbe05c3b56`

## Accepted X1 intelligence product stack

### Historical Coverage Proof v1

CMIS Issue #383 is complete. The exact supported XNT/USDC.X market has verified lifetime-start evidence, archive-start exhaustion, continuous one-minute pair-price coverage through the accepted rolling checkpoint, current-end renewal, exact pair identity, and supported provider-range completeness.

This does **not** promote historical USDC.X -> USD equivalence, full USD lifetime, global XDEX archive completeness, or legacy full-asset lifetime.

### Burn Intelligence v1

CMIS `burn_intelligence/v1` is accepted under capability contract 1.15.0 through public CMIS #389 and protected `cmis-core` #12.

ROBERTA public #295/#304 and protected `roberta-core` #23/#24 make Burn Intelligence a first-class X1 Scout + Canonical Decision Object workflow.

Human ROBERTA exposes:

```text
/burn <asset>
```

Accepted facts include cumulative verified-observed burn, 1h/24h/7d/30d windows, event counts, 24h/7d/30d equal-period comparison states/percentages, issuance context, independently gated circulation context, burn-time valuation state, and explicit lifetime-completeness limits.

### Discovery Intelligence v1

CMIS Discovery Ledger v1 is accepted through public #365 and protected `cmis-core` #6. CMIS public #391 promotes bounded read-only `discovery_intelligence/v1` under capability contract 1.16.0.

ROBERTA public #306 promotes Discovery through X1 Scout. Protected `roberta-core` #25 preserves the same Discovery history in the Canonical Decision Object for Human and Machine ROBERTA.

First verified observation is explicitly **not** token launch time. Sparse observations do not prove continuous coverage or archive completeness.

Human ROBERTA exposes:

```text
/discovery <asset>
```

### WHAT CHANGED? v1

ROBERTA public #308 adds first-class `x1_what_changed/v1` through X1 Scout. Protected `roberta-core` #26 adds the same workflow to `roberta_decision/v1`.

The workflow composes exactly the already-validated:
- Instant X1 Scan product;
- Burn Intelligence product;
- Discovery Intelligence product.

It does not calculate new market deltas in ROBERTA. Market/history change values are surfaced only when accepted CMIS/Scout history already supplies them. Burn comparison states and percentages are preserved exactly, including null percentage semantics. Discovery first/latest observations and completeness limits are preserved exactly.

Human ROBERTA exposes:

```text
/changed <asset>
```

Human and Machine ROBERTA consume the same canonical facts/history. No causal, manipulation, ownership, intent, or launch-time inference is added.

Issue ROBERTA #293 is complete and closed.

## Current synchronized capability state

- CMIS capability contract: `1.16.0`.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted in ROBERTA over accepted Scan/Burn/Discovery products.
- XNT supported-pair historical lifetime proof: accepted with USD-lifetime caveats preserved.
- Controlled Execution: unauthorized.

## Next synchronized product direction

The next reliability gate is **field-scoped current-market freshness**, but the older draft family (CMIS #386 / `cmis-core` #9 / ROBERTA #301 / `roberta-core` #19) predates accepted CMIS 1.15 Burn and 1.16 Discovery. It must be reconciled onto current public/private heads and promoted under a new CMIS contract version rather than merged with stale assumptions.

After freshness, advance **Early Warning** one evidence family at a time with explicit persistence, replay/deduplication, freshness, identity, severity, and delivery contracts.

CMIS #363 and related X1.Ninja/vault evidence research may continue in parallel but do not block the flagship ROBERTA product roadmap.

## Core sync rule

**CMIS verifies changing chain facts. X1 Scout validates and composes accepted CMIS contracts. ROBERTA orchestrates and explains them. Human and Machine ROBERTA share the same Canonical Decision Object. No layer above CMIS may silently recompute facts, convert missing evidence into values, or infer execution authority.**

`execution_authorized=false`
