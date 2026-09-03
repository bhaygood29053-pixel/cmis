# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-02 (America/New_York)

This file is the compact cross-project synchronization baseline and is intentionally mirrored byte-for-byte in the public ROBERTA and CMIS repositories. Repository-local roadmap, contract, status, and protected-core documents remain authoritative for implementation details.

## Product identity and authority invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- Canonical authority path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration, policy coordination, specialist selection, learning coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning, contract validation, and interpretation; they do not manufacture blockchain facts.
- CMIS owns deterministic freshness-sensitive facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, burn arithmetic, freshness policy, Early Warning evidence, and bounded analysis-only calculations.
- Missing evidence remains unknown/unavailable; it is never converted into zero, false, infinity, or a model estimate.
- Proof Score remains separate from risk and warning state.
- Controlled Execution remains locked/not started. `execution_authorized=false` remains invariant.

## Accepted implementation heads before this reconciliation-only sync

- CMIS public `main`: `7b5f429b2c7eb2f88f5b7ed62d595908ff68b036`
- protected `cmis-core` `main`: `20b4a1b28f59223dc0abebe5242cb94281726411`
- ROBERTA public `main`: `9a95a157293b02c9e58c30dd107d5f929e5c929e`
- protected `roberta-core` `main`: `c056ccfd79140f5f1f8baad1201124acc63763af`

## Accepted X1 intelligence product stack

### Historical Coverage Proof v1

CMIS Issue #383 is complete. Exact supported XNT/USDC.X pair-lifetime evidence remains accepted with historical quote-to-USD, full USD lifetime, global archive completeness, and legacy full-asset-lifetime caveats preserved.

### Burn Intelligence v1

CMIS `burn_intelligence/v1` is accepted under capability contract 1.15.0.

### Discovery Intelligence v1

CMIS Discovery Ledger and `discovery_intelligence/v1` are accepted under capability contract 1.16.0. First verified observation is not token launch time; sparse observations do not prove continuous lifetime coverage.

### WHAT CHANGED? v1

ROBERTA `x1_what_changed/v1` composes accepted Scan/Burn/Discovery evidence without creating a second market-delta or causal-inference authority.

### Field-scoped current-market freshness — CMIS 1.17

CMIS `instant_x1_scan/v3` / `x1_current_market_freshness/v1` are accepted. One fresh field never promotes global freshness and Evidence Receipt freshness remains a separate evidence dimension.

### Persistent concentration Early Warning foundation

CMIS Issue #396 / public #397 / protected `cmis-core` #15 establish the accepted internal two-distinct-observation persistence foundation with strict ordering, bounded persistence, current-evidence freshness, duplicate/replay rejection, deterministic `cw_...` identity, and exact Evidence Receipt / Proof Score lineage.

### Concentration Warning Intelligence v1 — CMIS 1.18

CMIS Issue #399 is accepted through public CMIS #400 and protected `cmis-core` #16.

Accepted service semantics:
- service: `concentration_warning_intelligence`;
- contract: `concentration_warning_intelligence/v1`;
- X1 only;
- bounded, read-only and pull-only;
- public service promoted and Scout reliance promoted;
- runtime owns the trusted intelligence-evidence resolver;
- caller-supplied evidence, receipts, Proof Scores, warning objects, risk/behavior/ownership labels, or resolver state are rejected;
- exactly two distinct compatible CMIS-owned concentration-change evidence ids;
- strict fact-time ordering, persistence-window bound, latest-evidence freshness, and no unresolved fields;
- exact Receipt ids and Proof Score records are preserved;
- deterministic WATCH/CLEAR state;
- WATCH/CLEAR are not risk severity, behavior, ownership, manipulation, causality, or prediction;
- Solana unavailable for v1;
- `delivery_mode=pull_only`;
- `push_delivery_authorized=false`;
- `execution_authorized=false`.

The nested canonical persistent warning retains its internal non-promotion flags; the public CMIS service wrapper is the explicit promotion boundary.

## Current synchronized capability state

- CMIS capability contract: `1.18.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Historical Coverage Proof: accepted with pair-vs-USD caveats preserved.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted.
- Field-scoped current-market freshness: accepted end-to-end.
- Persistent concentration Early Warning foundation: accepted.
- Concentration Warning Intelligence v1: accepted as an X1 pull-only CMIS public service with Scout reliance.
- ROBERTA/X1 Scout product adoption of Concentration Warning Intelligence: not yet accepted.
- Push notification/delivery service: not authorized.
- Controlled Execution: unauthorized.

## Next synchronized product direction

**Adopt Concentration Warning Intelligence through X1 Scout and the Canonical ROBERTA Decision Object.** ROBERTA should validate CMIS >=1.18 and `concentration_warning_intelligence/v1`, preserve the canonical warning/evidence object without recomputation, expose WATCH/CLEAR clearly to Human ROBERTA, preserve the same structured facts for Machine ROBERTA, and keep warning state separate from deterministic risk.

The first ROBERTA workflow should remain on-demand/pull. Push delivery, Telegram notifications, subscriptions, watchlists, background polling, retry queues, and acknowledgement semantics require a later separate delivery contract.

CMIS #363 and related X1.Ninja/vault evidence research may continue in parallel but do not block the flagship ROBERTA roadmap.

## Core sync rule

**CMIS verifies changing chain facts, freshness, and warning evidence. X1 Scout validates and composes accepted CMIS contracts. ROBERTA orchestrates and explains them. Human and Machine ROBERTA share the same Canonical Decision Object. No layer above CMIS may silently recompute facts/freshness/warning states, convert missing evidence into values, or infer execution authority.**

`execution_authorized=false`
