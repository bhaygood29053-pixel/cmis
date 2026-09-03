# Bridge Flow Intelligence v1

Issue: #409

## Purpose

`bridge_flow_intelligence/v1` is the deterministic route-scoped calculation
layer that follows accepted Warp route qualification.

It computes current/prior 24h, 7d, and 30d flow windows from **already verified
settled-transfer observations** for one exact route.

The foundation does not discover Warp transaction endpoints, parse raw chain
instructions, pair source/destination events, infer bridged supply, or promote
bridge facts to Scout/ROBERTA.

## Required route gate

The service requires an accepted qualified route envelope. For the first Warp
route this is the exact wSOL -> wSOL.X route accepted through
`warp_config/exact-mint-pair/v1`.

If the route is not qualified, the flow service fails closed.

## Accepted event shape

Each candidate event must preserve:

- exact `event_id`;
- exact deterministic `transfer_id`;
- exact route id;
- exact source chain + mint;
- exact destination chain + mint;
- `direction` = `inflow` or `outflow`;
- integer `amount_raw`;
- exact decimals;
- numeric `settled_at` epoch seconds;
- `lifecycle_state=settled`;
- `settlement_verified=true`;
- `pairing_verified=true`.

Only those settled records may enter flow totals.

Refunded, failed, pending, unverified, unpaired, malformed, route-mismatched,
duplicate-event, duplicate-transfer, out-of-coverage, and mixed-decimal records
are excluded from totals and surfaced in explicit unresolved accounting.

## Window semantics

The contract computes:

- 24h current and immediately preceding 24h;
- 7d current and immediately preceding 7d;
- 30d current and immediately preceding 30d.

Intervals are start-inclusive and end-exclusive:

`[window_start, window_end)`

For each complete period:

- gross inflow raw + decimal string;
- gross outflow raw + decimal string;
- net flow raw + decimal string;
- inflow event count;
- outflow event count.

For inflow, outflow, and net flow, the contract also computes:

- prior-period raw value;
- absolute raw change;
- percentage change when the prior denominator is non-zero.

Zero-denominator states remain explicit:

- `undefined_zero_baseline` when current is non-zero and prior is zero;
- `unchanged_zero_baseline` when both are zero.

No infinity is emitted.

## Coverage rule

Time bounds alone do not prove complete history.

The caller must explicitly supply:

`coverage_verified=true`

before any interval may be treated as complete. A window is complete only when
verified coverage spans its entire interval.

If coverage is incomplete, the primary totals for that interval are `null`.
Missing history is never converted to zero.

## Bridged supply

The accepted Warp config response proves route representation topology but does
not prove current bridged supply or reserve sufficiency.

Therefore `bridged_supply` is `unavailable` unless a separate future supply
contract supplies:

- `verified=true`;
- `semantic_contract_accepted=true`;
- exact raw amount;
- exact decimals;
- explicit basis;
- observation time.

The flow service preserves such accepted supply evidence without recomputing it.

## Source independence

`source_independence_verified` is explicit and defaults false. The flow
contract does not infer independence merely because events are numerous or
because a provider returns HTTP 200.

## Determinism

The evidence identity is a canonical SHA-256 over:

- exact route;
- exact coverage;
- accepted event/transfer identities;
- unresolved counts;
- decimals;
- all current/prior windows;
- accepted supply evidence when present.

Input order does not change the evidence hash.

## Promotion state

This foundation always preserves:

```text
route_scoped_only = true
missing_history_zero_filled = false
public_service_promoted = false
scout_reliance_promoted = false
read_only = true
execution_authorized = false
```

## What remains before live Warp flow intelligence

A separate provider/source slice must still establish a provenance-approved
Warp transaction history contract and normalize its lifecycle/identity fields
into the accepted event shape above.

Until that live source is accepted, this foundation is calculation-ready but
does not claim real 24h/7d/30d Warp flow totals.
