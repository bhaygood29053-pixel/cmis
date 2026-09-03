# Warp Issue #407 — HAR network evidence capture

Status: **read-only evidence acquisition / not semantic acceptance**

This workflow exists to resolve the remaining blocker in Issue #407 without guessing a Warp API path or weakening the existing bridge-source provenance gate.

## What it does

A browser-exported HAR can now be processed through `warp_har_network_observation/v1`.

The parser has two fail-closed layers. `list_warp_har_observations(...)` preserves exact endpoint provenance even when Chrome omits response-body text; `list_warp_har_candidates(...)` remains stricter and requires a parseable JSON body before semantic capture.

The semantic-candidate parser accepts only entries that are:

- initiated from the official `https://app.bridge.x1.xyz` application as established by an exact HTTPS Referer or Origin;
- exact HTTPS URLs;
- `GET` requests only;
- HTTP `200` responses;
- JSON content types;
- non-base64 response bodies containing parseable JSON.

Both listings are sanitized. They do **not** return request headers, cookies, authorization material, response headers, or response bodies. Metadata-only observations explicitly return `semantic_capture_eligible=false`, `json_parse_verified=false`, and `response_sha256=null` until the actual response body is present.

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

## 2026-09-03 real Chrome HAR result

A clean official Info-page HAR established exact same-origin Warp read endpoints:

- `GET https://app.bridge.x1.xyz/api/bridge/config`
- `GET https://app.bridge.x1.xyz/api/bridge/guardians`
- `GET https://app.bridge.x1.xyz/api/bridge/tvl?chain=sol&token=<token>`

Observed TVL token values included `xencat`, `USDC`, `wSOL`, `cbBTC`, `ETH`, and `DGN`.

For the exact config endpoint, the capture recorded six repeated observations from the official `/info` page, each with HTTP 200, `application/json`, response size 7,746 bytes, and Next.js matched path `/api/bridge/[...path]`. The guardian endpoint similarly returned HTTP 200 JSON with a 4,682-byte response.

The browser export omitted `response.content.text`, so no response-body SHA-256 or field-level semantic fixture can yet be produced from that HAR alone. Response size is **not** a substitute for a response hash.

Sanitized metadata observation SHA-256:

`a1e0e4bf4bbc83f2313a6e396912fc6f509310792cc5d9e969cada87a669b9da`

This clears the exact endpoint-provenance discovery subproblem but does not clear #407 semantic acceptance:

```text
exact_official_config_url = verified_by_official_app_har
http_200_json = verified
response_body_present = false
response_sha256 = unavailable
field_semantics = not_verified
semantic_contract_accepted = false
warp_qualified = false
execution_authorized = false
```

## 2026-09-03 exact config response-body semantic fixture

A direct copy of the provenance-approved exact endpoint

`https://app.bridge.x1.xyz/api/bridge/config`

produced a parseable JSON response with:

- `fetchedAt = 1788436231329` (milliseconds; 2026-09-03T11:50:31.329Z);
- exact Warp program id on both Solana and X1: `6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD`;
- per-chain global `paused` state;
- per-token exact `mint`, `decimals`, `isNative`, and `paused` state;
- per-chain explicit `guardians` arrays and `threshold`;
- wSOL source mint `So11111111111111111111111111111111111111112`;
- X1 wSOL.X destination mint `JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8`.

Canonical JSON SHA-256:

`b8ce53645c1f9495171bea65fa4a59588dfb2bae4a36227b39a05a4ae4f38687`

The accepted semantic contract is `warp_config/exact-mint-pair/v1`. It uses exact chain-scoped mint identity, never symbol equivalence.

For one exact route, status is `paused` if either chain config or either exact token entry is paused; otherwise it is `active`.

The bounded backing semantic is the provider-declared representation topology from the exact `isNative` booleans. For Solana wSOL -> X1 wSOL.X this is:

`provider_config_native_source_to_non_native_destination`

This does **not** claim reserve sufficiency, solvency, legal custody, or a stronger lock/mint mechanism than the official config directly proves.

The bounded custody/security dependency is the explicit guardian quorum configuration. The accepted fixture shows 7 guardians and threshold 5 on each side, represented as:

`guardian_quorum:solana=5/7;x1=5/7`

This does **not** prove guardian honesty or identify a legal custodian.

The source fact time is `fetchedAt / 1000`; freshness remains fail-closed under the existing route-evidence freshness gate.

For the exact wSOL -> wSOL.X provenance fixture, the accepted semantic adapter now reaches:

```text
endpoint_semantics_verified = true
exact_route_identity_verified = true
source_timestamp_semantics_verified = true
route_status_verified = true
backing_model_verified = true
custody_dependency_verified = true
qualification_state = qualified
warp_qualified = true
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```
