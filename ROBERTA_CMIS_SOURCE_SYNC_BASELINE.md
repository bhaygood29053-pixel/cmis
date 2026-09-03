# ROBERTA ↔ CMIS Source Sync Baseline

Last reconciled: 2026-09-03 (America/New_York)

This file is the cross-project checkpoint for accepted public repository state.
Implementation contracts, capability manifests, issue acceptance criteria, and
protected-core documents remain authoritative for their own scopes.

## Authority invariant

- Public product: **ROBERTA — Verified On-Chain Intelligence**.
- Canonical path:
  `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
- ROBERTA owns orchestration and final synthesis.
- Chain Scouts consume and interpret accepted CMIS contracts; they do not
  manufacture chain facts.
- CMIS owns deterministic facts, freshness, evidence, Evidence Receipts, Proof
  Scores, risk, historical intelligence, burn arithmetic, warning evidence,
  bridge qualification, and bridge-flow evidence.
- Missing evidence remains unknown/unavailable.
- Proof Score, warning state, bridge qualification, and risk remain separate.
- Controlled Execution remains locked. `execution_authorized=false`.

## Public heads observed for this checkpoint

```text
CMIS checkpoint base main =
fb628257a728347df5abc3d255f97da0cce2b058

ROBERTA observed main =
9f66906bbc756e4abdf1e903c22b61e45884938c
```

The CMIS checkpoint commit/PR that updates this document is expected to advance
CMIS `main` beyond the recorded checkpoint base. The SHA above intentionally
identifies the accepted state being checkpointed.

## Current synchronized capability state

- CMIS capability contract: `1.18.0`.
- Instant X1 Scan: `instant_x1_scan/v3`.
- Burn Intelligence: accepted under CMIS 1.15.
- Discovery Intelligence: accepted under CMIS 1.16.
- Field-scoped current-market freshness: accepted under CMIS 1.17.
- Concentration Warning Intelligence: accepted under CMIS 1.18 and adopted
  through X1 Scout / Canonical ROBERTA Decision Object.
- Push warning delivery: not authorized.
- Controlled Execution: not authorized.

## Warp / cross-chain accepted state

Accepted CMIS evidence now includes:

- #402 / PR #403 — `cross_chain_asset_provenance/v1`;
- #405 / PR #406 — bridge route/Warp qualification foundation;
- #407 / PR #429 — exact official Warp config semantics accepted through
  `warp_config/exact-mint-pair/v1`;
- PR #432 — `bridge_flow_intelligence/v1` deterministic calculator;
- #433 / PR #435 — exact connected History endpoint pattern preserved with
  wallet redaction;
- PR #436 — `warp_onchain_transfer_history/v1` canonical settled-event
  authority using exact OutgoingMsg/IncomingMsg pairing;
- PR #439 — wallet-history response body pinned as corroboration only;
- #437 / PR #440 — `warp_message_retention_coverage/v1` current-universe
  counter/account closure accepted.

The previous state that treated #407 as open/blocked is superseded.

## Current bridge truth boundary

```text
warp_exact_route_semantics = accepted
real_settled_transfer_pairing = accepted
wallet_history_response_semantics = accepted_corroboration
current_message_universe_counter_closure = accepted

retention_deletion_semantics_verified = false
historical_retention_complete_verified = false
requested_60d_window_coverage_verified = false
coverage_complete_verified = false
missing_history_zero_authorized = false

bridge_flow_24h_7d_30d_primary_totals = coverage_gated
verified_bridged_supply = not_accepted

public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The wallet-history API is wallet-scoped and cannot establish route-wide
coverage. Provider status labels are corroboration, not the settlement trust
root. Canonical settled-event truth remains the accepted on-chain paired
message evidence.

## Active synchronized gate

**CMIS Issue #441 — prove 60-day Warp message-account lifecycle retention for
#409.**

The required lookback covers the current 30-day window plus the immediately
preceding 30-day comparison window.

#441 must prove that the exact relevant history has not been lost through
message-account close/deletion/recycling and that the finalized read-only trace
reaches the requested lookback start without archive/pagination gaps.

Until that proof passes, missing bridge history cannot become zero.

## Downstream sequence

```text
CMIS #441
  -> finish CMIS #409 Bridge Supply + 24h/7d/30d Flow Intelligence
    -> CMIS #410 Bridge-to-XDEX Utilization
      -> ROBERTA #314 X1 Scout cross-chain adoption
```

ROBERTA #314 may prepare/adopt only after the required CMIS public-service /
Scout-reliance contracts are accepted. ROBERTA must not independently infer
Warp route, supply, flow, retention, or utilization truth.

## Parallel items

- CMIS #363 remains parallel X1.Ninja delayed-vault evidence research and is not
  the flagship cross-chain blocker.
- FortiSwap remains an accepted bounded read-only provider foundation; provider
  assertions do not override CMIS bridge truth.
- Theo remains a bounded advisory-provider boundary; live factual authority is
  fail-closed.

## Core sync rule

**CMIS verifies the evidence. X1 Scout composes only accepted CMIS contracts.
ROBERTA explains the same canonical evidence. No upper layer may silently
recompute or upgrade facts, freshness, warnings, bridge truth, risk, coverage,
or execution authority.**

`execution_authorized=false`
