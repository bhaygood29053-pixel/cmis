# X1 Explorer Network Observation v1

Status: implementation candidate under CMIS Issue #475.

## Purpose

This contract adds sanitized browser/network observation beneath the merged X1 Explorer structured-discovery layer.

It exists for JavaScript-rendered X1 Explorer pages where static HTML does not contain the useful chain data. The observation layer ingests an exported HAR or equivalent normalized capture. It does not launch a browser, replay requests, retain secrets, or treat observed network responses as verified chain truth.

Contract:

`x1_explorer_network_observation/v1`

## Qualification

An observation is eligible only when:

- Referer or Origin identifies `https://explorer.mainnet.x1.xyz`;
- target URL is HTTPS;
- target host is explicitly allowlisted;
- no URL credentials are embedded;
- credential-like query keys are absent;
- response status is 2xx;
- request/response content is structurally acceptable under the bounded rules.

Initial target hosts:

- `explorer.mainnet.x1.xyz`
- `rpc.mainnet.x1.xyz`

## JSON-RPC POST handling

JSON-RPC read methods use HTTP POST. POST at the transport layer is not treated as execution authority.

Only an explicit read-only method allowlist is accepted:

- getSignatureStatuses
- getBlockTime
- getTransaction
- getSignaturesForAddress
- getMultipleAccounts
- getBlock
- getBlocks
- getSlotLeaders
- getFirstAvailableBlock
- getEpochSchedule
- getEpochInfo

Unknown methods and execution-oriented methods such as `sendTransaction` are rejected.

Request bodies are parsed only long enough to classify the method and extract bounded safe chain identifiers. Raw request bodies are not returned or retained by the candidate record.

## GET JSON handling

Same-origin X1 Explorer GET endpoints may be observed when they return JSON content. They remain non-RPC discovery observations unless a separate source-specific contract defines semantics.

## Safe identifier correlation

Known read methods may expose bounded identifier candidates:

- getTransaction → transaction signature
- getSignatureStatuses → transaction signatures
- getSignaturesForAddress → address
- getMultipleAccounts → addresses
- getBlock / getBlockTime → slot
- getBlocks → slot bounds
- getSlotLeaders → first slot

Identifiers are validated through the accepted X1 Explorer structured route contract before being emitted.

The identifiers remain unverified chain candidates.

## Sanitization

Candidate records do not retain:

- request headers;
- request cookies;
- authorization material;
- raw request bodies;
- response headers;
- response cookies;
- raw response bodies.

Candidate metadata may retain:

- exact observed target URL;
- official explorer referrer/origin;
- HTTP transport method;
- request body byte size and SHA-256 after secret-key rejection;
- recognized RPC method names;
- bounded safe chain identifiers;
- response status/content type;
- response byte size;
- response SHA-256 when bounded JSON text is present;
- whether response JSON parsing succeeded.

Credential-like query/body keys cause fail-closed rejection.

## Truth state

Every observation remains:

`discovery_state=DISCOVERED`
`official_explorer_network_observation=true`
`entity_identity_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`request_replay_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

A successful JSON parse proves only that the captured response body was valid JSON within bounds. It does not prove semantic correctness, completeness, freshness, source independence, or chain truth.

## Relationship to structured discovery

Example:

Explorer page:
`/tx/<signature>`

Browser network observation:
`getTransaction(<signature>, ...)`

CMIS Web Discovery can correlate both to the same transaction candidate.

That correlation improves discovery confidence but still requires the existing accepted X1 RPC verification/evidence contract before any field becomes CMIS verified truth.

## Non-goals

This contract does not:

- launch or control Playwright/Chromium;
- bypass site restrictions;
- replay HAR requests;
- store browser credentials;
- provide arbitrary JSON-RPC passthrough;
- send transactions;
- simulate execution;
- sign or broadcast anything;
- promote network observations to public CMIS service truth;
- authorize X1 Scout or ROBERTA reliance.

## Next extension after acceptance

After this sanitized observation layer is accepted, a later slice may add an operator-controlled browser capture utility that produces this exact sanitized contract directly, while keeping all secret-bearing browser state outside CMIS evidence records.
