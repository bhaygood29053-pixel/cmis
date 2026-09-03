# CMIS GitHub Checkpoint — Warp / Bridge Flow Intelligence

Checkpoint date: 2026-09-03 (America/New_York)

## Frozen accepted baseline

```text
cmis_checkpoint_base_main = fb628257a728347df5abc3d255f97da0cce2b058
roberta_observed_main = 9f66906bbc756e4abdf1e903c22b61e45884938c
cmis_capability_contract = 1.18.0
execution_authorized = false
```

This checkpoint records the accepted repository state immediately after PR #440
and before implementation of Issue #441.

## Canonical architecture

```text
User / transport
  -> ROBERTA
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

ROBERTA owns orchestration and final synthesis. Chain Scouts consume accepted
CMIS contracts. CMIS owns deterministic verified facts/evidence/risk. Providers
remain beneath CMIS. No upper layer may silently recalculate CMIS truth.

## Accepted Warp / cross-chain state

The following are accepted on CMIS `main` at this checkpoint:

- #402 / PR #403 — `cross_chain_asset_provenance/v1`;
- #405 / PR #406 — `bridge_route_evidence/v1` and
  `warp_bridge_qualification/v1` foundation;
- #407 / PR #429 — exact official Warp config semantics accepted through
  `warp_config/exact-mint-pair/v1`;
- PR #432 — deterministic `bridge_flow_intelligence/v1` calculation
  foundation;
- #433 / PR #435 — exact official connected History endpoint pattern
  `GET /api/bridge/transactions/wallet/{wallet}?limit=100` preserved with
  wallet redaction;
- PR #436 — canonical settled-event authority through
  `warp_onchain_transfer_history/v1`, pairing exact Warp
  OutgoingMsg/IncomingMsg state;
- PR #439 — exact wallet-history response body pinned as
  `warp_wallet_history_semantics/v1` corroboration only;
- #437 / PR #440 — `warp_message_retention_coverage/v1` verifies the current
  message-account universe closes against official config counters, exact
  on-chain Config counters, and full PDA-verified OutgoingMsg/IncomingMsg
  counts.

The wallet-history API is not the canonical settlement authority. The on-chain
paired message evidence remains the trust root for settled transfer events.

## Accepted evidence distinctions

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

The accepted current-universe closure is necessary evidence for completeness,
but it is not proof that historical message state has never been closed,
deleted, or recycled.

## Active gate

**Issue #441 — Warp: prove 60-day message-account lifecycle retention for #409**

Issue #441 is the exact next CMIS gate.

Required result: prove, over the required current-30d + prior-30d lookback, that
the exact Warp message history used for Bridge Flow Intelligence has not been
lost through account close/deletion/recycling and that the finalized trace
reaches the requested lookback start without pagination/archive gaps.

Until that gate passes, CMIS must keep incomplete bridge-flow windows null and
must not turn missing history into zero.

## Remaining #409 work

After #441:

1. promote coverage only if the bounded 60-day retention condition is proven;
2. produce verified 24h/7d/30d current and prior flow totals from accepted
   settled events;
3. separately establish an accepted bridged-supply semantic contract;
4. close #409 only when its required flow + supply outputs satisfy their own
   evidence gates.

## Downstream sequence

```text
#441 lifecycle retention proof
  -> finish #409 Bridge Supply + Flow Intelligence
    -> #410 Bridge-to-XDEX Utilization
      -> ROBERTA #314 X1 Scout adoption of accepted CMIS cross-chain facts
```

ROBERTA #314 must remain blocked from live bridge-flow/utilization adoption
until the required CMIS contracts are accepted/promoted.

## Parallel work

CMIS #363 delayed-vault/X1.Ninja evidence research remains parallel and is not
the flagship cross-chain blocker.

## Safety invariant

No checkpoint item authorizes:

- transaction construction as an execution path;
- wallet signing;
- broadcasting;
- custody;
- bridge value movement;
- autonomous trading or execution.

`execution_authorized=false`
