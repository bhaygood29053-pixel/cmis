# Warp Wallet History Observation v1

Issue: #433  
Parent: #409

## Purpose

`warp_wallet_history_observation/v1` preserves the exact read-only network
pattern used by the official Warp History page without storing the connected
wallet identifier.

The accepted observed template is:

```text
GET https://app.bridge.x1.xyz/api/bridge/transactions/wallet/{wallet}?limit=100
Referer: https://app.bridge.x1.xyz/history
HTTP 200
Content-Type: application/json
```

This is endpoint-provenance evidence only. It does not yet establish transaction
field meanings, lifecycle/finality semantics, pagination completeness, or
historical coverage.

## Real official capture — 2026-09-03

A clean Chrome HAR from the connected official History page recorded three
successful calls to the exact wallet-history endpoint pattern.

Sanitized observations:

| Observation | HTTP | JSON bytes |
| --- | ---: | ---: |
| 1 | 200 | 1,269 |
| 2 | 200 | 1,269 |
| 3 | 200 | 1,203 |

All three were:

- GET/read-only;
- same-origin from `app.bridge.x1.xyz`;
- initiated while the official page was `/history`;
- routed through Next.js `/api/bridge/[...path]`;
- Vercel cache MISS;
- `application/json`.

Sanitized observation-set SHA-256:

`90a8b017b8638cdee5e57f5bbfb11b5cef5b15abfc6f86cf3993c5fab1cd6a7c`

The browser export again omitted `response.content.text`, so no response-body
hash or field-level semantic fixture can be produced from this HAR alone.

## Privacy boundary

The capture code deliberately returns only the route template:

`https://app.bridge.x1.xyz/api/bridge/transactions/wallet/{wallet}?limit=100`

It never returns or retains the observed wallet identifier or the full
wallet-bearing URL.

## Fail-closed rules

An observation is accepted only when all of these are true:

- exact HTTPS host `app.bridge.x1.xyz`;
- exact path shape `/api/bridge/transactions/wallet/{base58-wallet}`;
- exact query `limit=100` and no other query parameter;
- GET;
- exact History-page referrer;
- HTTP 200;
- JSON content type;
- non-base64 content.

If a parseable JSON body is present, the observation may become
`semantic_capture_eligible=true`, but that still does **not** accept
transaction or coverage semantics.

## Current #433 state

```text
exact_wallet_history_endpoint = verified
official_history_referrer = verified
GET_read_only = verified
HTTP_200_JSON = verified
response_body_present = false
transaction_field_semantics = not_verified
pagination_coverage_semantics = not_verified
flow_normalization_authorized = false
execution_authorized = false
```

The next evidence step is to capture/copy the JSON response body from the exact
wallet-history endpoint and review its fields before connecting live events to
`bridge_flow_intelligence/v1`.
