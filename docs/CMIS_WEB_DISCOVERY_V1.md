# CMIS Web Discovery v1

Status: implementation candidate under Issue #471. Foundation-only until accepted through the normal CMIS merge gates.

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

## Initial source providers

| Source id | Provider | Initial allowed hosts | Source role |
|---|---|---|---|
| x1_explorer | X1 Explorer | explorer.mainnet.x1.xyz | official_explorer_discovery |
| xdex | XDEX | xdexdocs.gitbook.io, api.xdex.xyz | protocol_native_web_api_discovery |
| x1_ninja | X1.Ninja | x1.ninja, api.x1.ninja | third_party_indexer_web_api_discovery |
| x1report | X1Report | x1report.com, www.x1report.com | third_party_reporting_discovery |
| x1_docs | X1 Docs | docs.x1.xyz, next.x1.xyz | official_documentation_discovery |
| github | GitHub | github.com, api.github.com, raw.githubusercontent.com | public_source_repository_discovery |

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

Issue #471 authorizes implementation of this internal foundation only.

A later gate is required before any of the following:

- adding cmis_web_discovery to GET /v1/cmis/capabilities;
- exposing it as a public CMIS service;
- allowing X1 Scout or Roberta to rely on it as promoted truth;
- creating scheduled monitoring;
- assigning Evidence Receipts / Proof Scores directly from web discovery;
- claiming any source pair is independent.

## Testing requirements

Deterministic regression coverage includes:

- all six initial source registrations;
- allowlist rejection;
- redirect escape rejection;
- bounded body-size failure;
- HTML title/text/link extraction;
- excluded script content;
- external-link omission;
- JSON parsing/normalization;
- query matching;
- crawl page/depth bounds;
- public-promotion and execution-authority invariants;
- visible per-source failure in multi-source collection.

Live source-access probes, if added, must remain separate opt-in evidence gates and must not convert transport success into semantic verification.
