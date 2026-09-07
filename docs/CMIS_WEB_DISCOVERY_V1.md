# CMIS Web Discovery v1

Status: **ACCEPTED INTERNAL FOUNDATION** via Issue #471 / PR #472. Follow-on X1 Explorer/XDEX layers through PR #489 and X1.Ninja route coverage through PR #495 are merged. Issue #496 is the active X1.Ninja semantic-coverage reconciliation gate. The entire stack remains discovery-only, non-promoted, and `execution_authorized=false`.

## Purpose

CMIS Web Discovery is a bounded, read-only multi-source discovery framework beneath CMIS.

It exists to find and preserve candidate information from public X1 ecosystem surfaces without treating a web page, explorer label, API field, documentation statement, repository file, or reporting claim as verified CMIS truth.

The authority path remains:

    User / transport
      -> Roberta
        -> Chain Scout
          -> CMIS
            -> Chain Provider / verified source

CMIS Web Discovery is a provider-side discovery capability beneath CMIS. It is not a replacement for X1 RPC, deterministic verification, Evidence Receipts, Proof Score, risk, or the existing provider contracts.

## Registered source providers

| Source id | Provider | Initial allowed hosts | Source role |
|---|---|---|---|
| x1_explorer | X1 Explorer | explorer.mainnet.x1.xyz | official_explorer_discovery |
| xdex | XDEX | xdexdocs.gitbook.io, api.xdex.xyz, oracle.xdex.xyz | protocol_native_web_api_discovery |
| x1_ninja | X1.Ninja | x1.ninja, api.x1.ninja | third_party_indexer_web_api_discovery |
| x1report | X1Report | x1report.com, www.x1report.com | third_party_reporting_discovery |
| fortiblox_app | FortiBlox App | app.fortiblox.com | third_party_x1_app_web_api_discovery |
| x1_docs | X1 Docs | docs.x1.xyz, next.x1.xyz | official_documentation_discovery |
| github | GitHub | github.com, api.github.com, raw.githubusercontent.com | public_source_repository_discovery |

The FortiBlox App source includes the root application URL plus the provider-documented `/api/x402/discovery` and `/llms.txt` GET surfaces as bounded discovery targets. This does not qualify FortiSwap execution endpoints or provider assertions as verified CMIS facts.

### FortiBlox browser/network discovery

Issue #555 extends `fortiblox_app` with two internal discovery contracts:

- `fortiblox_network_observation/v1` sanitizes browser-exported HAR-like entries;
- `fortiblox_browser_capture/v1` passively opens one explicit `app.fortiblox.com` page in an ephemeral Chromium context and immediately sanitizes eligible responses.

The network observer retains only bounded metadata and hashes. It never retains cookies, authorization headers, `PAYMENT-SIGNATURE`, `PAYMENT-REQUIRED`, raw request bodies, raw response bodies, or raw HAR records.

Eligible observations are:

- the public `GET /api/x402/discovery` and `GET /llms.txt` discovery surfaces;
- FortiSwap routes already classified as read-only observation surfaces;
- unknown same-host GET JSON/text routes as `unqualified_get_candidate` so new machine surfaces can be discovered without silently gaining authority.

Known execution routes such as transaction build/send/status are dropped. Unknown non-GET routes are also dropped. Passive observation of the already-qualified `POST /api/quote` route is allowed only as hashed metadata; the request body is not retained and the request is never replayed.

Issue #559 subsequently qualified `GET /api/ramp/availability` as an accepted read-only observation route after a bounded live semantic probe established only the response schema for provider-reported country, buy/sell availability, provider names, and optional reason. Asset/network scope, price/quote/limit semantics, freshness, independent country-code semantics, and execution remain unverified.

HTTP 402 may be recorded only as `payment_required_observed=true`. No payment header is retained, no payment is performed, and `payment_authorized=false`.

The browser capture performs zero clicks, zero form submissions, zero wallet interaction, zero authentication, and zero payments. It supplies no persistent storage state, blocks service workers, disables downloads, and preserves `execution_authorized=false`.

Different source names do not establish source independence. Source independence remains separately unverified unless an accepted CMIS contract proves it.

## Contract

Provider contract and internal service contract:

    cmis_web_discovery/v1

Every successful page observation preserves at least:

- exact source id, name, role, and host allowlist;
- requested URL and final URL;
- read-only HTTP GET retrieval method;
- observation time;
- HTTP status and content type;
- bounded body byte count;
- SHA-256 identity of the retrieved body;
- normalized content kind: HTML, JSON, or text;
- bounded title/text excerpt;
- bounded same-source links eligible for optional crawling;
- query terms and deterministic lexical match counts when a query is supplied.

Every observation starts with:

    discovery_state = DISCOVERED
    web_claim_verified = false
    cmis_verified = false
    source_independence_verified = false
    evidence_receipt_promoted = false
    proof_score_promoted = false
    risk_promoted = false
    public_service_promoted = false
    scout_reliance_promoted = false
    cmis_promotable = false
    execution_authorized = false

DISCOVERED is not VERIFIED.

## Bounded collection rules

The foundation uses source-specific URL boundaries and deterministic limits.

Default limits:

- timeout: 15 seconds per HTTP request;
- max response body: 256,000 bytes;
- max extracted same-source links: 100 per page;
- max pages per crawl: 5;
- default crawl depth at the service seam: 0 (explicit opt-in is required to follow links);
- maximum accepted crawl depth: 2;
- max query text: 500 characters;
- max returned normalized text excerpt: 8,000 characters.

The implementation disables automatic redirect following. Every redirect target is normalized and checked against the same source allowlist before the next GET is sent. A redirect outside the allowlist fails closed without requesting the foreign target.

Only HTTP and HTTPS URLs are accepted. URLs with embedded credentials are rejected.

Binary/unsupported content types fail closed. HTML script/style/noscript/SVG content is excluded from normalized page text. JSON is parsed structurally and normalized without inferring provider field semantics.

## Multi-source behavior

The internal CMIS service can collect one source or a bounded set of sources.

A failed source remains visibly UNAVAILABLE and does not become an empty-success observation. A successful source remains AVAILABLE but its claims still remain discovery-only.

The service does not average, vote, merge, or reconcile different source claims by itself. Any same-fact comparison or promotion to verified truth requires an existing or separately accepted CMIS verification contract for that exact identity, field, units, scope, and time basis.

## Intended uses

Candidate discovery may support later deterministic work such as:

- X1 transaction/account/program discovery;
- pool and token discovery;
- XDEX route or pool research;
- bridge/Warp evidence discovery;
- token burn candidate discovery;
- wallet/transaction tracing research;
- historical evidence location;
- official documentation/version research;
- implementation/source-code evidence location;
- disagreement detection before deterministic reconciliation.

These are discovery uses only. Existing accepted CMIS contracts remain authoritative for verification.

## Explicit non-goals

CMIS Web Discovery v1 does not:

- create a general uncontrolled internet crawler;
- perform background or autonomous web monitoring;
- bypass robots/terms/operator requirements for live deployment;
- submit forms or mutations;
- use POST to change remote state;
- authenticate as a user;
- hold browser cookies as authority;
- promote website claims to chain truth;
- infer risk, ownership, intent, fraud, manipulation, or causality;
- change the public CMIS capability manifest;
- authorize Scout reliance;
- construct, sign, broadcast, or execute transactions;
- move bridge assets or any other value.

## Verification handoff

A normal evidence path is:

    web source
      -> CMIS Web Discovery
        -> DISCOVERED candidate
          -> exact CMIS verification contract
            -> corroborated / verified evidence only if proven

Example:

    X1Report page says a token burn occurred
      -> Web Discovery records page identity + text + timestamp
      -> X1 Explorer discovery locates a transaction candidate
      -> X1 RPC verifies exact mint/instruction/balance/supply effects
      -> burn_intelligence may use the result only through its accepted contract

The webpage itself never becomes the verification authority.

## Promotion state

Issue #471 / PR #472 accepted this internal foundation. Later source-specific Web Discovery layers through PR #489 remain internal and do not change the promotion boundary.

A later gate is required before any of the following:

- adding cmis_web_discovery to GET /v1/cmis/capabilities;
- exposing it as a public CMIS service;
- allowing X1 Scout or Roberta to rely on it as promoted truth;
- creating scheduled monitoring;
- assigning Evidence Receipts / Proof Scores directly from web discovery;
- claiming any source pair is independent.

## Testing requirements

Deterministic regression coverage includes:

- all six initial source registrations plus the bounded `fortiblox_app` registration;
- allowlist rejection;
- redirect escape rejection;
- bounded body-size failure;
- HTML title/text/link extraction;
- excluded script content;
- external-link omission;
- JSON parsing/normalization;
- query matching;
- crawl page/depth bounds;
- FortiBlox same-host browser/network sanitization, 402 metadata handling, unknown-GET candidate discovery, and execution-route exclusion;
- public-promotion and execution-authority invariants;
- visible per-source failure in multi-source collection.

Live source-access probes, if added, must remain separate opt-in evidence gates and must not convert transport success into semantic verification.
