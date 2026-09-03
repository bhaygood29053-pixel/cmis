# Warp Message Retention Coverage v1

Issue: #437  
Parent: #409

## Purpose

Determine whether Warp's currently enumerable on-chain message universe is
closed against the bridge's own counters before any missing period is allowed
to become zero in `bridge_flow_intelligence/v1`.

Contract:

`warp_message_retention_coverage/v1`

## Three-way closure

The contract compares three views acquired independently:

1. the provenance-approved official Warp config endpoint;
2. the exact on-chain Config PDA decoded through the accepted discriminator/PDA
   layout evidence;
3. the fully enumerated, exact-PDA-verified OutgoingMsg and IncomingMsg account
   universes on Solana and X1.

For each chain it compares:

- official `outSeqCounter`;
- on-chain Config `out_seq_counter`;
- verified OutgoingMsg account count;
- official `inSeqCounter`;
- on-chain Config `in_seq_counter`;
- verified IncomingMsg account count.

It also requires unique outgoing sequence keys and unique incoming
source-sequence keys.

## Critical distinction

The following can be true:

`counter_account_closure_verified=true`

while all of these remain false:

`retention_deletion_semantics_verified=false`  
`historical_retention_complete_verified=false`  
`requested_window_coverage_verified=false`  
`coverage_complete_verified=false`

Counter equality proves that the currently visible message-account population
closes against the observed counters. It does not by itself prove that historical
messages cannot be deleted, recycled, or otherwise removed while counters are
adjusted or reused.

## Why this gate matters

PR #436 proved that real wSOL <-> wSOL.X transfers can be paired exactly and fed
to `bridge_flow_intelligence/v1`. The calculator still withholds 24h/7d/30d
totals because a verified event set is not the same thing as a complete
historical event set.

This gate isolates the strongest current completeness invariant before the
remaining lifecycle-retention question is reviewed.

## Required 60-day basis

The #409 contract reports current 30-day windows plus equal prior 30-day
comparators. Therefore the source needs a complete 60-day lookback ending at the
evaluation time, unless complete bridge/message lifetime is proven and that
lifetime is shorter.

`required_flow_lookback_seconds = 5,184,000`

## Next evidence after counter closure

If exact live counter closure passes, #437 still needs one defensible retention
argument before window coverage may be promoted. Candidate evidence includes:

- authoritative/current program source proving OutgoingMsg and IncomingMsg
  cannot be closed/recycled; or
- exhaustive transaction/instruction evidence showing the lifecycle and any
  close/realloc paths; or
- another independently verifiable retention contract that makes account
  deletion impossible without causing the counter/account invariant to fail.

A third-party IDL's lack of a close instruction is useful corroboration, not
sufficient authority by itself.

## Safety

Read-only GET/RPC only.

No transfer construction, signing, broadcast, custody, or value movement.

`execution_authorized=false`.
