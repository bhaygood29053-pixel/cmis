# X1Scroll Archival RPC Provider v1

Status: implementation foundation for CMIS Issue #456.

## Decision

CMIS may integrate X1Scroll only as a read-only archival transaction provider
beneath the X1 Provider boundary.

Architecture:

    ROBERTA -> X1 Scout -> CMIS -> X1 Provider
                                  |- official X1 RPC
                                  '- X1Scroll archival RPC

ROBERTA and X1 Scout do not call X1Scroll directly.

## Accepted provider-owned access contract

As of 2026-09-04, X1Scroll publicly documents:

- credential-backed HTTP JSON-RPC at https://rpc.x1scroll.io/v1/<API_KEY>;
- a getTransaction request using a known transaction signature;
- a free tier advertised at 100 requests/minute;
- archival-history claims from genesis to present.

The CMIS implementation promotes only the first two items as an API foundation.
Provider claims about retention depth, completeness, no-gap coverage, account
history, or source independence are not converted into verified CMIS facts by
documentation alone.

## Implementation boundary

The adapter:

- accepts an API key only at runtime or a complete injected RPC URL;
- never includes the secret-bearing RPC URL in normalized evidence or error text;
- allows getTransaction by default;
- rejects undocumented methods, including getSignaturesForAddress, unless an
  explicit bounded probe opts in;
- normalizes transaction lookup with provider/source provenance;
- explicitly reports archive completeness and source independence as unverified.

## Intended historical use

The first production use should be fallback recovery of a transaction body when
CMIS already has a transaction signature but the canonical X1 RPC can no longer
return that historical transaction.

Signature discovery remains on accepted X1 discovery surfaces until X1Scroll
address-history methods are independently qualified.

This separation is important for token burn intelligence:

    accepted signature discovery
      -> canonical X1 getTransaction
      -> if pruned/unavailable, bounded X1Scroll getTransaction fallback
      -> existing deterministic token-instruction parser
      -> CMIS evidence / burn arithmetic

The fallback must preserve which provider supplied each transaction. CMIS must
not relabel provider archive claims as verified lifetime coverage.

## Activation gate

The adapter is safe to merge without a credential, but production fallback
remains disabled until a live X1Scroll API key is configured and a bounded live
probe proves:

1. successful known-signature retrieval;
2. response compatibility with the deterministic parser;
3. behavior for missing signatures and provider errors;
4. any requested getTransaction config fields such as jsonParsed encoding;
5. secret redaction;
6. rate-limit behavior adequate for the bounded caller.

Only after that gate should the protected CMIS runtime route historical
transaction fallback through this provider.
