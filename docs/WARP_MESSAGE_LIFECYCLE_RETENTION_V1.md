# Warp Message Lifecycle Retention v1

Issue: #441  
Parent: #437  
Grandparent: #409

## Contract

`warp_message_lifecycle_retention/v1`

## Purpose

This contract is the bounded historical-retention gate that follows the already
accepted `warp_message_retention_coverage/v1` current-universe closure proof.
Its only job is to determine whether the exact Warp `OutgoingMsg` / `IncomingMsg`
state required for the Bridge Flow Intelligence 60-day comparison window has
been retained without deletion or recycling.

It does not prove permanent retention and it does not establish bridged-supply
semantics.

## Accepted prerequisite

The evaluator requires an already accepted
`warp_message_retention_coverage/v1` result with both:

- `counter_account_closure_verified=true`
- `current_message_universe_count_closed=true`

The exact message-PDA universe must come from
`warp_onchain_transfer_history/v1` with verified account-type and PDA identity.

## Read-only evidence path

For both Solana and X1:

1. paginate finalized `getSignaturesForAddress` for the exact Warp program;
2. continue through the requested 60-day start, or exhaust the exact program
   lifetime;
3. obtain the RPC archive floor with `getFirstAvailableBlock` + `getBlockTime`;
4. fetch finalized `getTransaction` bodies for every successful Warp-program
   transaction in scope;
5. intersect transaction account keys with the exact current message-PDA
   universe;
6. inspect pre/post lamport transitions for each exact PDA;
7. preserve bounded lifecycle-related log fragments as corroboration.

No write, signing, broadcast, custody, transfer construction, or value movement
is permitted.

## Lifecycle interpretation

For one exact current message PDA:

- `pre=0`, `post>0` -> creation
- `pre>0`, `post=0` -> closure
- `pre=0`, `post=0` while the exact PDA is touched -> ambiguous lifecycle touch;
  fail closed
- `pre>0`, `post>0` -> ordinary touch

A current PDA with more than one observed creation is treated as recreation /
recycling evidence and blocks retention acceptance.

For every current `OutgoingMsg` whose accepted source timestamp falls inside the
requested lookback, the trace must contain exactly one creation transition.
This prevents a nominally complete signature range from being accepted when the
transaction bodies needed to reconstruct message creation are incomplete.

## History-boundary rules

Normal acceptance requires the finalized Warp-program signature trace to reach
or cross the exact requested 60-day start.

A younger-program lifetime may be accepted only when all of the following hold:

- Warp-program signature pagination is exhausted;
- the RPC archive floor predates the requested start;
- the exact Warp program account creation transition is present in the fetched
  transaction trace.

Address-history exhaustion alone is never enough because it can also be caused
by a pruned provider.

## Fail-closed blockers

Any of the following keeps historical retention false:

- pagination page cap reached before the required boundary;
- repeated signature during pagination;
- missing signature block time;
- missing or failed-to-fetch successful transaction body;
- transaction account/balance vector mismatch;
- unverified message PDA;
- any message-account closure;
- more than one creation of one current message PDA;
- creation inside the window for an outgoing message whose accepted timestamp
  predates the window;
- zero-to-zero ambiguous touch of an exact message PDA;
- missing expected in-window `OutgoingMsg` creation;
- younger-program fallback without archive coverage or exact program creation.

## Promotion semantics

Only after both chains pass the full gate may the result set:

- `retention_deletion_semantics_verified=true`
- `historical_retention_complete_verified=true`
- `requested_window_coverage_verified=true`
- `coverage_complete_verified=true`
- `missing_history_zero_authorized=true`

The zero authorization is strictly bounded to:

`exact_message_universe_requested_lookback_only`

It is not permission to zero-fill unrelated bridge routes, supply, provider
history, or any interval outside the accepted evidence window.

## Still separate

Even a passing #441 result intentionally leaves:

- `bridged_supply_verified=false`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`

After #441 is accepted, #409 still must reconcile the verified coverage result
into `bridge_flow_intelligence/v1` and separately complete accepted bridged
supply semantics before #410 or ROBERTA #314 can advance.
