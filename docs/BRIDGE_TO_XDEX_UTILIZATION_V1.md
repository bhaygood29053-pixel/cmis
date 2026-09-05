# Bridge-to-XDEX Utilization Intelligence v1

Issue: CMIS #410

Contract: `bridge_to_xdex_utilization/v1`

## Goal

Measure how much verified bridged capital is represented in verified XDEX liquidity and current 24-hour trading activity without treating bridge activity as liquidity, volume, adoption, risk, or causality.

## First bounded implementation slice

The deterministic contract composes four already-separated evidence classes:

1. accepted `warp_bridge_flow_integration/v1` bridge supply + 24h flow;
2. exact XDEX pool-universe evidence for the X1 representation mint;
3. verified/fresh per-pool liquidity and rolling 24h volume facts;
4. a verified/fresh representation-value basis.

The contract does not discover or fetch those facts itself.

## Required same-unit rule

The core metric is:

```text
bridge_to_xdex_liquidity_ratio =
    verified_xdex_liquidity_value
    /
    verified_bridged_supply_value
```

The denominator is converted from exact bridged token units into USD only through the supplied verified/fresh representation price basis.

The numerator is accepted only when every exact pool metric has verified USD liquidity semantics and freshness.

Therefore this contract never performs:

```text
USD liquidity / raw token supply
```

## Exact pool-universe closure

The ratio is blocked when:

- the exact representation pool universe is not verified;
- any pool remains unresolved;
- a pool metric lies outside the universe;
- any exact pool is missing a metric;
- duplicate pool metrics exist;
- a metric references the wrong representation mint.

## Freshness

Both the representation value basis and every pool metric must be current relative to the bridge-flow `as_of`.

Default bounds:

```text
max_market_age_seconds = 300
max_future_skew_seconds = 30
```

Freshness booleans alone are insufficient; the observed timestamp must also satisfy the bound.

## Outputs

When all required inputs pass:

- exact XDEX pool count and addresses;
- verified total XDEX liquidity value;
- verified total rolling 24h XDEX volume value;
- verified bridged supply raw amount and token amount;
- verified bridged supply USD value;
- current 24h bridge inflow/outflow/net/gross USD values;
- bridge-to-XDEX liquidity ratio;
- gross bridge-flow-to-XDEX-volume ratio;
- net bridge-flow-to-XDEX-volume ratio;
- deterministic evidence hash.

The flow/volume ratios are descriptive only.

## Zero-denominator behavior

A zero bridged-supply denominator does not become infinity or zero:

```text
bridge_to_xdex_liquidity_ratio = null
bridge_to_xdex_liquidity_ratio_state = undefined_zero_bridged_supply
```

A zero XDEX 24h-volume denominator likewise keeps flow/volume ratios unavailable.

## Explicit boundaries

The contract always preserves:

```text
causal_bridge_to_xdex_claim_authorized=false
adoption_claim_authorized=false
risk_promotion_authorized=false
public_service_promoted=false
scout_reliance_promoted=false
execution_authorized=false
```

This first slice is an internal deterministic foundation. Live pool discovery, exact wSOL.X universe closure, verified/fresh XDEX metric capture, and verified representation valuation remain the next acceptance gate before #410 can close.


## Live wSOL.X pool-universe checkpoint

The live #410 evidence path now performs two separate observations:

1. XDEX's public current pool catalogue; and
2. mint-filtered X1 RPC enumeration inside the independently verified XDEX
   program/account family.

For wSOL.X
`JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8`, both produced zero current
matching pools. The authoritative chain-side result uses an explicit opt-in
verified-zero contract:

```text
scope = verified_xdex_program_family
matching_program_state_account_count = 0
verified_program_pool_count = 0
verified_zero_set = true
current_liquidity_zero_verified = true
recognized_program_registry_globally_exhaustive = false
global_onchain_pool_discovery_proven = false
```

This proves current zero liquidity only inside the exact verified XDEX
program-family scope. It is not an all-X1-DEX claim.

Critically, a current verified-zero pool set does **not** prove a rolling 24-hour
trading-volume zero. A pool could have existed earlier in the 24-hour window, or
the rolling-volume source/window semantics could remain incomplete. Therefore:

```text
volume_24h_semantics_verified = false
volume_24h_window_coverage_verified = false
verified_xdex_volume_24h_value = null
bridge_flow_to_xdex_volume_ratio_state =
    unavailable_unverified_volume_window
issue_410_acceptance_verified = false
```

The remaining #410 acceptance work is a bounded 24-hour XDEX activity/window
proof plus a verified comparable value basis for the bridged-supply denominator.
No zero substitution is authorized.


## #410 acceptance and #482 promotion

The final #410 evidence gate is accepted through PR #469. The accepted wSOL.X
composition proves current zero XDEX liquidity and verified 24h zero XDEX
volume only inside the verified XDEX program family, together with a comparable
fresh USD value basis.

Issue #482 keeps the canonical #410 object immutable with
`public_service_promoted=false` and `scout_reliance_promoted=false`, then
adds a separate public projection that validates exact route/source/destination
identity, content hash, freshness, units, scope, and guardrails. Only that
validated service projection reports public-service and Scout-reliance
promotion. This prevents X1 Scout from becoming a second utilization
calculator.
