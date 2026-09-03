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

- CMIS public `main`: `d376c11052060c4510b0a6d0e9a5e04d4371676b`
- protected `cmis-core` `main`: `4595ae6a5f5cf8cb48c6ed36ab832bba7ddaa698`
- ROBERTA public `main`: `4a94b356faf452cc2e062ca75c8e55c8c65c8e87`
- protected `roberta-core` `main`: `c056ccfd79140f5f1f8baad1201124acc63763af`

## Accepted X1 intelligence product stack

### Historical Coverage Proof v1

CMIS Issue #383 is complete. Exact supported XNT/USDC.X pair-lifetime evidence remains accepted with historical quote-to-USD, full USD lifetime, global archive completeness, and legacy full-asset-lifetime caveats preserved.

### Burn Intelligence v1

CMIS `burn_intelligence/v1` is accepted under capability contract 1.15.0. Human and Machine ROBERTA preserve the same cumulative verified-observed burn, windows, event counts, period-over-period changes, and coverage semantics.

### Discovery Intelligence v1

CMIS Discovery Ledger and `discovery_intelligence/v1` are accepted under capability contract 1.16.0. First verified observation is not token launch time; sparse observations do not prove continuous lifetime coverage.

### WHAT CHANGED? v1

ROBERTA `x1_what_changed/v1` composes accepted Scan/Burn/Discovery evidence without creating a second market-delta or causal-inference authority.

### Field-scoped current-market freshness — CMIS 1.17

CMIS public #386 and protected `cmis-core` #9 establish `instant_x1_scan/v3` / `x1_current_market_freshness/v1`. ROBERTA public #301 and protected `roberta-core` #19 preserve and render the same field-scoped freshness without recomputation.

One fresh field never promotes global freshness. Evidence Receipt freshness remains a separate evidence dimension.

### Persistent concentration Early Warning foundation

CMIS Issue #396 is complete through public PR #397 and protected `cmis-core` #15.

Accepted foundation semantics:
- exactly two distinct canonical CMIS-owned `top_account_concentration_change` intelligence evidence ids;
- exact X1 subject identity;
- same source, scope, requested-account limit, and observed-account count;
- strict increasing canonical fact-time order;
- explicit bounded persistence window;
- explicit latest-evidence age;
- accepted concentration-intelligence Receipt freshness must be verified and unresolved fields must be empty;
- duplicate evidence cannot inflate persistence;
- exact Evidence Receipt ids and Proof Score records are preserved;
- explicit GT/GTE threshold policy over `absolute_delta_bps`;
- deterministic content-addressed `cw_...` warning identity;
- `WATCH` only when both observations satisfy the condition; otherwise `CLEAR`;
- `WATCH`/ `CLEAR` are not risk severity, behavior, ownership, manipulation, causality, or prediction.

The foundation remains internal:
```text
public_service_promoted=false
scout_reliance_promoted=false
delivery_authorized=false
risk_interpretation_verified=false
behavioral_interpretation_verified=false
ownership_interpretation_verified=false
execution_authorized=false
```

## Current synchronized capability state

- CMIS capability contract: `1.17.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Historical Coverage Proof: accepted with pair-vs-USD caveats preserved.
- Burn Intelligence: accepted.
- Discovery Intelligence: accepted.
- WHAT CHANGED?: accepted.
- Field-scoped current-market freshness: accepted end-to-end.
- Persistent concentration Early Warning evidence foundation: accepted internally.
- Public Early Warning service: not promoted.
- Controlled Execution: unauthorized.

## Next synchronized product direction

**Promote the first bounded Early Warning service as a separate gate.** The service should be X1-only, pull-only/read-only, internally resolve CMIS-owned evidence, expose stable WATCH/CLEAR semantics and exact evidence lineage, reject caller-supplied trust material, remain separate from risk, and keep push delivery plus execution unauthorized.

Only after the CMIS public-service / capability-manifest / Scout-reliance gate passes should X1 Scout and the Canonical ROBERTA Decision Object adopt Early Warning.

CMIS #363 and related X1.Ninja/vault evidence research may continue in parallel but do not block the flagship ROBERTA roadmap.

## Core sync rule

**CMIS verifies changing chain facts, freshness, and warning evidence. X1 Scout validates and composes accepted CMIS contracts. ROBERTA orchestrates and explains them. Human and Machine ROBERTA share the same Canonical Decision Object. No layer above CMIS may silently recompute facts/freshness/warning states, convert missing evidence into values, or infer execution authority.**

`execution_authorized=false`
