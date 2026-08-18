# CMIS Phase 11 — Sanitized Intelligence History

Status: **read-only historical intelligence foundation**

This layer persists only normalized, content-addressed CMIS observations. It does not store arbitrary raw provider payloads and it does not infer missing samples.

## Supported categories

- concentration
- wallet
- price
- liquidity
- supply
- activity

Every stored observation preserves:

- chain;
- exact subject identity;
- metric and unit;
- canonical UTC observation time;
- optional slot/block position;
- source;
- verification method;
- evidence scope;
- identity and semantics verification state;
- freshness/scope state when known;
- optional CMIS evidence-receipt/proof metadata;
- limitations;
- content-addressed observation ID.

Concentration observations additionally require an exact rational numerator/denominator. Decimal ratio text is presentation metadata and is not the comparison source of truth.

## Historical comparison boundary

`compare_first_last()` requires an exact series selector:

- chain;
- category;
- subject;
- metric;
- unit;
- evidence scope;
- source;
- verification method.

This prevents an apparent trend from being created by silently switching provider, scope, unit, or semantic contract.

Ordering uses **observation time**, not database insertion time.

If multiple distinct observations occupy a comparison boundary timestamp, the result is `AMBIGUOUS_BOUNDARY`; CMIS does not pick one arbitrarily.

## Sparse history remains sparse

The ledger always preserves:

```text
continuous_coverage_proven = false
archival_completeness_proven = false
interpolation_performed = false
missing_samples_filled = false
```

Two samples prove only two observations. They do not prove what happened between them, provider retention, archival completeness, finality equivalence, or continuous coverage.

## Evidence metadata

The ledger can preserve a content-addressed CMIS Evidence Receipt ID plus Proof Score strength/percent/method. Priority 4 owns validation and attachment of the complete Evidence Receipt / Proof Score objects to material intelligence conclusions; Priority 3 only provides a bounded storage slot for that metadata.

## Safety boundary

Read-only storage/comparison only. No transaction construction, signing, broadcasting, custody, bridge transfer, trading, autonomous execution, or value movement.