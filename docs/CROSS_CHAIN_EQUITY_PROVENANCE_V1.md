# Cross-Chain Equity Provenance v1

`cross_chain_equity_provenance/v1` is the evidence-bound CMIS layer that sits
above the accepted structural contracts:

- `cross_chain_asset_provenance/v1`
- `tokenized_equity_provenance/v1`
- `bridge_route_evidence/v1`

Its purpose is to preserve an exact tokenized-equity lineage across chains
without collapsing token identity, bridge-route evidence, observed movement,
legal/economic equivalence, or holder rights into one claim.

## Required inputs

The builder accepts:

1. an accepted `tokenized_equity_provenance/v1` object with exact token and
   underlying-security identities plus structural cross-chain continuity; and
2. one qualified `bridge_route_evidence/v1` receipt for every cross-chain hop.

Every route receipt must match the lineage hop exactly by:

- canonical asset id;
- hop index;
- source chain / asset id / asset-id kind;
- destination chain / asset id / asset-id kind;
- bridge;
- route id;
- provider;
- accepted semantic contract; and
- accepted source URL.

All route-evidence qualification checks must pass. Caller-provided booleans are
not a substitute for an accepted CMIS route semantic contract.

## Robinhood Chain -> X1 boundary

CMIS currently has **no accepted Robinhood Chain -> X1 machine-readable route
semantic contract**. Therefore this contract rejects a Robinhood Chain -> X1
equity lineage even if a caller constructs a structurally plausible route or
reuses a semantic contract accepted for another chain path.

A future acceptance may add a Robinhood Chain -> X1 semantic contract only
after the exact route, endpoint, field, and timestamp semantics are independently
verified.

Robinhood Chain being live is not evidence that:

- Warp supports Robinhood Chain;
- a Robinhood Chain -> X1 bridge is live;
- a tokenized equity is deployed on X1; or
- an equity representation actually moved to X1.

## Route evidence is not movement evidence

A qualified bridge route proves that CMIS accepted the route/configuration
semantics for the exact hop. It does **not** prove that the tokenized-equity
representation traversed the route.

Accordingly:

- `observed_asset_movement_verified=false`
- `asset_movement_claim_authorized=false`
- `bridge_activity_equals_adoption=false`

A later movement-evidence contract is required before CMIS may say a specific
equity representation actually crossed a bridge.

## Equity / rights boundary

The contract does not authorize claims that a destination token:

- is the underlying share itself;
- grants shareholder or beneficial ownership;
- grants voting, dividend, or redemption rights;
- is legally or economically equivalent to another representation;
- has sufficient backing;
- has safe custody; or
- is low/high risk because a route exists.

Those questions belong to the planned `tokenized_equity_rights/v1` and other
evidence-bearing contracts.

## Promotion state

This slice is structural/evidence-bound but not publicly promoted:

- `read_only=true`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`

Parent roadmap: CMIS #660
Implementation issue: CMIS #666
