# Warp Issue #407 — HAR network evidence capture

Status: **read-only evidence acquisition / not semantic acceptance**

This workflow exists to resolve the remaining blocker in Issue #407 without guessing a Warp API path or weakening the existing bridge-source provenance gate.

## What it does

A browser-exported HAR can now be processed through `warp_har_network_observation/v1`.

The parser accepts only entries that are:

- initiated from the official `https://app.bridge.x1.xyz` application as established by an exact HTTPS Referer or Origin;
- exact HTTPS URLs;
- `GET` requests only;
- HTTP `200` responses;
- JSON content types;
- non-base64 response bodies containing parseable JSON.

Candidate listing is sanitized. It does **not** return request headers, cookies, authorization material, response headers, or response bodies.

A candidate is not a verified semantic contract. The selected HAR entry is submitted to the already-merged `warp_machine_contract_capture/v1` gate, which still requires explicit field mapping and timestamp-unit declaration and still returns:

```text
semantic_contract_accepted = false
accepted_registry_mutation_authorized = false
cmis_promotable = false
execution_authorized = false
```

until a separate evidence-review PR accepts the endpoint semantics.

## Operator capture procedure

1. Open `https://app.bridge.x1.xyz/info` in a clean browser session.
2. Do not connect a wallet and do not prepare, sign, or submit a transfer.
3. Open Developer Tools → Network.
4. Clear the network log.
5. Reload the Info page.
6. Filter to Fetch/XHR where helpful.
7. Save the network log as a HAR **with content**.
8. Inspect the sanitized candidate list produced by `list_warp_har_candidates(...)`.
9. Explicitly choose an `entry_index`; do not infer the winning endpoint from hostname, route text, or response shape.
10. Supply the semantic field map and timestamp-unit hypothesis to `capture_warp_machine_contract_from_har(...)`.
11. Review the resulting response hash, exact URL, field presence, field values, timestamp semantics, and blockers.
12. Only after independent semantic review and exact-head CI should a separate PR add a contract id to `ACCEPTED_ROUTE_SEMANTIC_CONTRACTS`.

## Security boundary

The HAR may contain cookies or browser credentials. This adapter deliberately reads only the minimum provenance signal required to establish that the official X1 bridge application initiated the observed request. Request headers and cookies are not returned or persisted by the candidate list.

The downstream capture gate separately rejects credential-like JSON response keys. URLs containing credential-like query parameters are rejected by the existing bridge-source provenance validator.

## Not authorized

- guessed API paths;
- POST requests;
- wallet connection as a discovery requirement;
- transaction preparation;
- signing;
- broadcast;
- value movement;
- automatic endpoint selection;
- automatic semantic acceptance;
- ROBERTA adoption;
- bridge flow intelligence;
- Bridge-to-XDEX utilization intelligence.

## Dependency state

```text
CMIS #407 = OPEN
HAR ingestion = READY FOR REVIEW
exact Warp endpoint = STILL MUST BE OBSERVED
Warp semantic contract = NOT ACCEPTED
CMIS #409 = BLOCKED
CMIS #410 = BLOCKED
ROBERTA #314 = BLOCKED ON ACCEPTED CMIS BRIDGE EVIDENCE
```
