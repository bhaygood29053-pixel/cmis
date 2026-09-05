# Current CMIS Project Status

Current reconciliation: **2026-09-05**.

Read in this order:

1. `../ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md` — mirrored four-repository status/authority baseline.
2. `CMIS_PRODUCT_ROADMAP.md` — authoritative living CMIS roadmap.
3. `CHECKPOINT_2026-09-05_FOUR_REPOS.md` — four-repository checkpoint.
4. Earlier dated reconciliation/status files — historical snapshots only.

## Accepted CMIS platform

- capability contract `1.18.0`;
- Instant X1 Scan v3;
- Burn Intelligence;
- Discovery Intelligence;
- field-scoped current-market freshness;
- pull-only Concentration Warning Intelligence;
- #409 Bridge Supply + current/prior 24h/7d/30d Flow Intelligence;
- #410 Bridge-to-XDEX Utilization Intelligence;
- internal CMIS Web Discovery v1-v5 through PR #481.

## Active flagship gates

### #482 — cross-chain public-service / Scout promotion

#410 evidence is complete. PR #469 is merged.

The next exact cross-chain task is **Issue #482**:

- promote `bridge_to_xdex_utilization/v1` through the public CMIS contract;
- preserve exact route/mint/program-family/value-basis/24h coverage evidence;
- fail closed on stale/missing/mismatched evidence;
- then authorize X1 Scout reliance without recomputation.

ROBERTA #314 is blocked only on this promotion gate.

### #461 — X1.Ninja USD liquidity

Accepted prerequisites:

- PR #465 fact-time / five-pool repeated-revaluation foundation;
- PR #466 current Warp USDC reserve backing for USDC.X;
- PR #468 current USDC.X/USD equivalence.

Active:

- PR #470 final five-pool X1.Ninja USD-liquidity semantic proof.
- Its current deterministic suite is green and the repeated-revaluation live workflow is still in progress.
- #459 remains the later liquidity/rolling-24h freshness promotion gate.

Until #470 merges, `x1_ninja_liquidity_usd_semantics_verified` remains unpromoted.

## Web Discovery

CMIS Web Discovery v1-v5 is complete internally through PR #481; Issue #483 is the active v6 XDEX network-gap registry. Issue #483 is the active v6 XDEX network-gap registry.

Current discovery stack includes:

- six-source bounded discovery;
- X1 Explorer structured discovery;
- sanitized X1 Explorer network observation;
- operator-controlled passive X1 Explorer browser capture;
- structured XDEX endpoint discovery with handoff to existing XDEX verification contracts.

Every result remains `DISCOVERED`; no Web Discovery layer creates verified market truth, source independence, risk, public-service promotion, Scout reliance, or execution authority by itself.

## Parallel work

- #444 Instant X1 Scan evidence completion.
- #459 field-scoped freshness expansion.
- #363 delayed-vault/X1.Ninja research.
- #458 X1Scroll qualification/fallback research.

`execution_authorized=false`
