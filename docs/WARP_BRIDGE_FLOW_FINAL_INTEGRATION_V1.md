# Warp Bridge Flow Final Integration v1

Contract: `warp_bridge_flow_integration/v1`

Parent: CMIS #409  
Integration issue: CMIS #454

## Purpose

Bind the already accepted evidence layers for the exact Solana wSOL -> X1
wSOL.X Warp route into the existing deterministic
`bridge_flow_intelligence/v1` calculator.

This integration does not create new bridge facts. It requires:

1. exact accepted Warp route qualification;
2. canonical settled events from `warp_onchain_transfer_history/v1`;
3. accepted bounded 60-day lifecycle retention from
   `warp_message_lifecycle_retention/v1`;
4. accepted exact bridged supply from `warp_bridged_supply_evidence/v1`.

## Coverage rule

The calculator receives `coverage_verified=true` only after the lifecycle
contract proves all required coverage flags and the exact
`missing_history_zero_scope=exact_message_universe_requested_lookback_only`.

This permits numeric zero totals for genuinely complete no-event windows. It
does not fabricate historical events and does not change the calculator's
`missing_history_zero_filled=false` invariant.

## Final verification

`integration_verified=true` requires:

- exact route qualification;
- complete canonical event pairing with zero unresolved route candidates;
- complete current and immediately-prior 24h/7d/30d windows;
- non-null totals/counts for every complete window;
- verified bridged supply;
- explicit source-independence state.

Source independence defaults false and is not inferred from multiple endpoints.

## Safety and promotion boundary

This slice remains internal/read-only:

- `provider_tvl_label_promoted=false`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`

Acceptance of #454 completes the internal #409 evidence path. Public/Scout
adoption remains a later explicit promotion decision.
