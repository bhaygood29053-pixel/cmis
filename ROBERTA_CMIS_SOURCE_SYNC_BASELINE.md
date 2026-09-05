# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-05 (America/New_York)

This file is the cross-project checkpoint for accepted public and protected repository state. Implementation contracts, capability manifests, issue acceptance criteria, and protected-core documents remain authoritative for their own scopes.

## Authority invariant

- Public product: **ROBERTA — Verified On-Chain Intelligence**.
- Canonical path: `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration and final synthesis.
- Chain Scouts consume and interpret accepted CMIS contracts; they do not manufacture chain facts.
- CMIS owns deterministic facts, freshness, evidence, Evidence Receipts, Proof Scores, risk, historical intelligence, burn arithmetic, warning evidence, bridge qualification, bridge-flow evidence, and provider semantic verification.
- Missing evidence remains unknown/unavailable.
- Proof Score, warning state, bridge qualification, liquidity fact-time, USD-equivalence, and risk remain separate claims.
- Controlled Execution remains locked. `execution_authorized=false`.

## Exact four-repository checkpoint

```text
CMIS public main
e3fcaa28c32143de03a88bebe1f3626e22a46573

CMIS protected core main
e84a352f12fa2b5291a98de61603f8dece577d44

ROBERTA public main
548bf70360ecb928002b8d9fce6cc8a673b1919e

ROBERTA protected core main
6627e756427f6270a7f32a243e40ad4db4df3c71
```

The documentation checkpoint commit that contains this file advances the repository on which it is written beyond the recorded implementation head above. The SHAs intentionally identify the accepted implementation state being checkpointed.

## CMIS #461 / liquidity evidence state

PR #465 is merged and establishes the stable fact-time milestone:

```text
verified_revaluation_event_count=5
verified_revaluation_pool_count=5
same_fact_reference_event_count=5
same_fact_reference_pool_count=5
liquidity_fact_time_verified=true
```

This does **not** yet establish final USD-liquidity semantics:

```text
current_usdcx_usd_equivalence_verified=false
x1_ninja_liquidity_usd_semantics_verified=false
liquidity_freshness_verified=false
source_independence_verified=false
cmis_promotable=false
execution_authorized=false
```

PR #466 is the active bridge-parity follow-up. Exact Solana USDC Warp-vault identity, exact X1 USDC.X mint and Warp authority, equal six-decimal units, and current reserve sufficiency have been observed. Historical retained Warp message accounts are not accepted as current in-flight liabilities merely because they remain enumerable.

The next valid USDC.X proof must establish current value-equivalence without using a stale-retention shortcut, then compose that result with a fresh exact-mint USDC/USD observation under the accepted policy.

## ROBERTA synchronized state

- ROBERTA Opinion v1 remains accepted.
- ROBERTA Claim Integrity v1 is accepted for X1 asset intelligence and X1 Compare.
- Compare Claim Integrity is accepted on public/protected main.
- The next ROBERTA Truth Gate expansion is standalone History, followed by Burn, Discovery, and remaining specialist products.
- ROBERTA does not yet promote the #461 X1.Ninja USD-liquidity claim. Until CMIS completes its remaining USD-equivalence and freshness gates, ROBERTA must preserve the unavailable/unverified boundary.

## Protected-core state

- `cmis-core` remains the protected deterministic runtime beneath the public CMIS shell. Its current accepted main includes X1 RPC market corroboration across protected scan/risk freshness routes.
- `roberta-core` remains the protected orchestration/synthesis runtime beneath the public ROBERTA shell. Its current accepted main includes Claim Integrity and repaired Compare claim-boundary handling.
- No protected source is moved back into the public repositories for convenience.
- Public evidence-contract work does not automatically imply a protected-runtime promotion.

## Core sync rule

**CMIS verifies the evidence. X1 Scout composes only accepted CMIS contracts. ROBERTA explains the same canonical evidence. No upper layer may silently recompute or upgrade facts, freshness, USD equivalence, warnings, bridge truth, risk, coverage, or execution authority.**

`execution_authorized=false`
