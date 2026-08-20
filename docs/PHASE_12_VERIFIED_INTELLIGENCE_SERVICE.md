# CMIS Phase 12 — Verified Intelligence Service Contract

## Status

Draft read-only service contract for X1 Scout reliance.

## Purpose

Phase 11 established deterministic Verified Intelligence foundations, but those foundation objects deliberately carry:

- `public_service_promoted = false`
- `scout_reliance_promoted = false`
- `execution_authorized = false`

Phase 12 does **not** change those foundation objects. It adds a narrow wrapper service, `verified_intelligence`, that may be relied on by an X1 Scout only after CMIS deterministically rebuilds the supplied Phase 11 intelligence-evidence bundle and proves an exact match.

## Contract

Service contract: `verified_intelligence/v1`

Initial chain scope: `x1` only.

Accepted conclusion types are exactly the deterministic conclusion types already accepted by `liquidity_scout.cmis.intelligence_evidence`.

The request contains one exact `intelligence_evidence` bundle. The service:

1. rejects unsupported conclusion types;
2. reruns the existing Phase 11 deterministic evidence-bundle validator;
3. requires the caller-supplied bundle to equal the rebuilt bundle exactly;
4. preserves receipt IDs, Proof Score records, source traceability, conclusion scope, and all nested foundation flags;
5. promotes only the wrapper result for public/Scout reliance;
6. keeps risk separate from proof;
7. adds no behavioral, ownership, intent, fraud, manipulation, or execution interpretation;
8. always keeps `execution_authorized = false`.

## Promotion boundary

Wrapper-level promotion is scoped as:

`exact_revalidated_intelligence_evidence_bundle_only`

The nested Phase 11 evidence remains non-promoted. A strong Proof Score by itself does not authorize service promotion, change risk, or authorize execution.

## Unsupported scope

Solana and future chains remain unavailable for this service until a separate accepted Scout-reliance contract defines their scope.

This contract does not authorize whale, insider, bot, accumulator, distributor, market-maker, ownership, relationship, or behavioral-intent labels.

## Execution boundary

This service is read-only. It performs no provider collection, transaction construction, signing, broadcasting, custody, trading, bridge transfer, or autonomous value movement.
