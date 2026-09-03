# Verified Bridge Route Evidence / Warp Qualification v1

Status: **internal / read-only / non-promoted**

Tracking issue: #405  
Depends on: #402 / merged PR #403  
Provider-gap parent: #30

## Purpose

This slice adds the machine-readable evidence boundary that must exist before
CMIS can treat a Warp Bridge route, its operational state, backing model,
custody dependency, or provider timestamp as verified.

Contracts:

- `bridge_route_evidence/v1`
- `warp_bridge_qualification/v1`

## Current Warp conclusion

Warp Bridge is **not qualified as a verified CMIS bridge provider yet**.

The official X1 bridge application currently exposes a Bridge UI, History UI,
and Info page. The Info page describes itself as real-time status and
configuration, and the Bridge page renders route/status/fee concepts. That is
useful source discovery, but it is not enough to establish a stable
machine-readable semantic contract.

The older `bridge-api.x1.xyz` lead remains discovery-only. Host permission,
a guessed URL, HTTP 200, or generic JSON cannot qualify a route.

Therefore the production semantic registry intentionally starts empty:

```text
accepted Warp semantic contracts = 0
warp_qualified = false
qualification_state = blocked_endpoint_semantics
```

## Evidence gates

A route can qualify only when all of these are true:

1. exact source URL provenance is accepted;
2. the exact URL has an accepted endpoint/field/timestamp semantic contract;
3. route id equals the provenance hop route id;
4. source chain + source asset id exactly match provenance;
5. destination chain + destination asset id exactly match provenance;
6. source timestamp semantics are accepted;
7. source and collection timestamps pass freshness policy;
8. route-status semantics are accepted;
9. backing-model semantics are accepted;
10. custody-dependency semantics are accepted.

Missing evidence stays unknown/unverified.

## Timestamp rule

The contract distinguishes:

- **source_observed_at** — provider fact time, usable only after the source
  timestamp field semantics are accepted;
- **collected_at** — when CMIS collected the candidate response;
- **evaluated_at** — deterministic evaluation time.

A fresh collection timestamp never upgrades a stale or semantically-unverified
provider fact time.

## Backing and custody

Candidate text can be retained for inspection, but:

```text
backing_model_verified = false
custody_dependency_verified = false
```

until the accepted semantic contract proves which exact response fields carry
those meanings.

This prevents a label such as "lock/mint", "guardian", "multisig", or
"non-custodial" from becoming CMIS truth by naming alone.

## Route status

Likewise, UI strings such as `Offline-Checking...`, `Online`, `Ready`, or
similar labels are not interpreted as route health until an accepted machine
contract defines:

- exact source field;
- exact values/enumeration;
- timestamp semantics;
- route/asset scope.

## What this slice does not authorize

- no Warp public-service promotion;
- no X1 Scout reliance;
- no ROBERTA bridge-health claim;
- no bridge supply/flow calculation;
- no transfer-history promotion;
- no capacity or fee promotion;
- no transaction preparation;
- no signing;
- no broadcast;
- no value movement.

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next acceptance action

Discover and capture an exact read-only Warp machine endpoint from an
X1-owned artifact, official application network observation, official
documentation, or independently verifiable on-chain configuration.

Then add a separate semantic-contract acceptance PR containing:

1. exact URL;
2. exact GET/read method;
3. response content type;
4. deterministic response hash/sample fixture;
5. route-id field semantics;
6. source/destination asset-id field semantics;
7. route-status field semantics;
8. backing-model field semantics;
9. custody-dependency field semantics;
10. provider timestamp field and unit semantics;
11. freshness policy;
12. fail-closed contract tests.

Only after that PR passes should a Warp semantic contract id be added to the
accepted registry.
