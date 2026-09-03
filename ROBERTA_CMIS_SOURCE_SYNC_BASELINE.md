# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-02 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Product identity and authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- Canonical authority path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration, policy coordination, specialist selection, learning coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning, contract validation, and interpretation; they do not manufacture blockchain facts.
- CMIS owns deterministic freshness-sensitive facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, burn arithmetic, freshness policy, and bounded analysis-only calculations.
- Missing evidence remains unknown/unavailable; it is never converted into zero, false, infinity, or a model estimate.
- Proof Score remains separate from risk.
- Controlled Execution remains locked/not started. `execution_authorized=false` remains invariant.

## Accepted implementation heads before this reconciliation-only sync

- CMIS public `main`: `abcda406ff361a229c72fdeca1211bef0c8bf354`
- protected `cmis-core` `main`: `df69f0d74810390f80d9a352aaf69ccf98302c1d`
- ROBERTA public `main`: `a83ea07148eceaa23fb7bf6b28053ab9585232a0`
- protected `roberta-core` `main`: `c056ccfd79140f5f1f8baad1201124acc63763af`

## Accepted X1 intelligence product stack

### Historical Coverage Proof v1

CMIS Issue #383 is complete. The exact supported XNT/USDC.X market has verified lifetime-start evidence, archive-start exhaustion, continuous one-minute pair-price coverage through the accepted rolling checkpoint, current-end renewal, exact pair identity, and supported provider-range completeness.

This does **not** promote historical USDC.X -> USD equivalence, full USD lifetime, global XDEX archive completeness, or legacy full-asset lifetime.

### Burn Intelligence v1

CMIS `burn_intelligence/v1` is accepted under capability contract 1.15.0 through public CMIS #389 and protected `cmis-core` #12. ROBERTA public #295/#304 and protected `roberta-core` #23/#24 expose the same burn facts to Human and Machine ROBERTA.

### Discovery Intelligence v1

CMIS Discovery Ledger v1 is accepted through public #365 and protected `cmis-core` #6. CMIS public #391 promotes bounded read-only `discovery_intelligence/v1` under capability contract 1.16.0. ROBERTA public #306 and protected `roberta-core` #25 preserve the same Discovery history.

First verified observation is not token launch time. Sparse observations do not prove continuous coverage or archive completeness.

### WHAT CHANGED? v1

ROBERTA public #308 and protected `roberta-core` #26 provide `x1_what_changed/v1` and `/changed <asset>`. The workflow composes accepted Instant Scan, Burn, and Discovery products; it does not calculate new market deltas or infer causality.

### Field-scoped current-market freshness — CMIS 1.17

CMIS public #386 promotes `instant_x1_scan/v3` and `x1_current_market_freshness/v1`. Protected `cmis-core` #9 derives price freshness from the existing verified provider-observation path without creating a second history store or price authority.

ROBERTA public #301 requires CMIS 1.17/v3 and validates the CMIS freshness object. Protected `roberta-core` #19 preserves that object in the Canonical Decision Object and renders per-field freshness for Human ROBERTA while Machine ROBERTA receives the same structured facts unchanged.

Accepted semantics:
- collection recency is not provider fact time;
- price freshness may be VERIFIED only when CMIS proves collection recency, timestamped provider price fact time, and value linkage;
- liquidity freshness remains NOT VERIFIED under 1.17;
- rolling 24h volume freshness remains NOT VERIFIED under 1.17;
- rolling 24h transaction freshness remains NOT VERIFIED under 1.17;
- one fresh field produces PARTIAL current-market freshness, not global VERIFIED freshness;
- Evidence Receipt freshness remains a separate evidence dimension;
- no layer above CMIS recomputes freshness.

## Current synchronized capability state

- CMIS capability contract: `1.17.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Historical Coverage Proof: accepted with pair-vs-USD caveats preserved.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted.
- Field-scoped current-market freshness: accepted end-to-end.
- Controlled Execution: unauthorized.

## Next synchronized product direction

**Early Warning is the active product gate.** Promote one warning family at a time. Each family must have explicit subject identity, observation persistence, fact-time freshness, comparator/baseline semantics, replay/deduplication behavior, severity vocabulary, Evidence Receipt/Proof Score lineage, delivery semantics, and fail-closed unknown handling before public/Scout reliance.

CMIS #363 and related X1.Ninja/vault evidence research may continue in parallel but do not block the flagship ROBERTA product roadmap.

## Core sync rule

**CMIS verifies changing chain facts and freshness. X1 Scout validates and composes accepted CMIS contracts. ROBERTA orchestrates and explains them. Human and Machine ROBERTA share the same Canonical Decision Object. No layer above CMIS may silently recompute facts/freshness, convert missing evidence into values, or infer execution authority.**

`execution_authorized=false`
