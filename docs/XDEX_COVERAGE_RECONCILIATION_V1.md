# XDEX Coverage Reconciliation v1

Status: implementation candidate under CMIS Issue #488.

## Purpose

This contract closes the current XDEX direct-machine Web Discovery coverage loop after the accepted v5-v7 layers.

Contract:

`xdex_coverage_reconciliation/v1`

The reconciliation answers a repository-governance question:

> Among the XDEX surfaces currently known and referenced by CMIS, does any useful direct read-only machine endpoint remain outside accepted structured discovery?

Current expected answer:

`known_direct_readonly_gap_count=0`

This is **not** a universal claim that XDEX has no undocumented endpoint anywhere. Scope is explicitly:

`known_repository_owned_xdex_surface_inventory`

and:

`universal_xdex_endpoint_completeness_verified=false`

## Accepted direct read-only coverage

### v5 — XDEX Structured Discovery

`xdex_structured_discovery/v1`

Covers:

- `api.xdex.xyz/api/xendex/pool/list`
- `api.xdex.xyz/api/token-price/price`
- `api.xdex.xyz/api/xendex/chart/history`
- `api.xdex.xyz/api/xendex/swap/quote`
- XDEX GitBook documentation classification

### v7 — XDEX Extended Read-Only Structured Discovery

`xdex_extended_readonly_structured_discovery/v1`

Covers the three former v6 gap candidates:

- `api.xdex.xyz/api/xdex/swap/quote`
- `oracle.xdex.xyz/api/v1/token/price`
- `oracle.xdex.xyz/api/v1/token/sell-quote`

The reconciliation requires all three former gaps to remain syntactically supported by v7.

## Known direct-machine inventory

The deterministic v8 inventory contains seven direct read-only machine surfaces:

1. pool list;
2. token price;
3. price history;
4. research-route swap quote;
5. frontend-route swap quote alias;
6. XDEX Oracle token price;
7. XDEX Oracle sell quote.

A surface counts as covered only if the assigned v5/v7 parser accepts its exact deterministic fixture.

Coverage does not establish provider-response correctness or field semantics.

## Execution exclusions

The known prepare paths remain excluded:

- `api.xdex.xyz/api/xendex/swap/prepare`
- `api.xdex.xyz/api/xdex/swap/prepare`

The reconciliation checks them through the accepted v6 gap registry and requires:

`classification=execution_adjacent_excluded`
`read_only=false`
`execution_authorized=false`

If either path stops satisfying those assertions, XDEX coverage reconciliation fails closed.

## UI-only boundary

The known XDEX application route:

`https://app.xdex.xyz/swap`

remains a UI-only candidate.

The reconciliation requires:

`direct_machine_access=false`
`browser_capture_justified=false`

A UI route is not treated as a machine-data gap merely because the page exists.

Future XDEX browser capture would require a specific material fact that cannot be obtained from the accepted direct machine endpoints.

## Documentation boundary

The existing XDEX GitBook documentation route remains recognized through v5.

The CMIS Web Discovery source table is reconciled to the current explicit XDEX allowlist:

- `xdexdocs.gitbook.io`
- `api.xdex.xyz`
- `oracle.xdex.xyz`

No wildcard XDEX host authorization is introduced.

## Decision outputs

When all deterministic checks pass, the report returns:

`known_direct_readonly_gap_count=0`

`former_v6_gap_candidates_covered_by_v7=true`

`execution_exclusions_intact=true`

`ui_only_boundary_intact=true`

`documentation_surface_covered=true`

`xdex_direct_machine_coverage_complete_for_known_inventory=true`

`browser_capture_required_now=false`

`recommended_next_source=x1_ninja`

## Truth boundary

These are coverage/governance statements, not live market facts.

Every report preserves:

`discovery_state=DISCOVERED`
`provider_response_verified=false`
`semantic_verification_complete=false`
`source_independence_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`request_replay_authorized=false`
`background_monitoring_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

## Why XDEX browser capture remains unnecessary

X1 Explorer required browser/network capture because important chain views are JavaScript-rendered and their useful structured data is exposed through underlying RPC traffic.

The known XDEX situation is different.

For the repository-known useful read-only XDEX data, direct machine endpoints are already identified and now structured through v5/v7.

Therefore browser capture would add operational complexity without filling a known evidence gap.

That decision may be revisited only if a later XDEX requirement identifies a unique material fact available solely through UI/browser behavior.

## Recommended next source

After v8 acceptance:

`recommended_next_source=x1_ninja`

The next Web Discovery source-specific work should begin X1.Ninja structured discovery, reusing its existing CMIS API/evidence adapters and preserving the same DISCOVERED-to-VERIFIED handoff boundary.

## Non-goals

This contract does not:

- scan the public internet for unknown XDEX endpoints;
- claim universal XDEX API completeness;
- fetch any live endpoint;
- launch a browser;
- replay a request;
- promote provider semantics;
- establish source independence;
- call swap prepare;
- sign or broadcast transactions;
- move value;
- expose Web Discovery as a public CMIS service;
- authorize Scout reliance.
