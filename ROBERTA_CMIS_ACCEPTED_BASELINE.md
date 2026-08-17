# Roberta ↔ CMIS Accepted Baseline

## Purpose

This document records which CMIS trust-layer semantics are accepted on `main` and therefore safe for Roberta-facing interface design.

It does **not** make those CMIS primitives directly callable by Roberta. A capability can be accepted CMIS core while still lacking a supported Roberta service wrapper.

`ROBERTA_INTEGRATION_CONTRACT.md` remains the primary Roberta-facing integration contract. This document is a narrow baseline companion for trust/verification consumption.

## Accepted CMIS trust semantics on `main`

Roberta-facing interfaces may preserve the following CMIS-produced meanings when a supported wrapper eventually returns them:

- `AGREEMENT` — two same-identity, same-unit normalized observations agree exactly under the applicable CMIS verifier.
- `CONFLICT` — evidence disagrees or fails a required identity/unit comparison. Roberta must not average or choose a preferred value unless a fact-specific CMIS rule explicitly says to do so.
- `INSUFFICIENT_EVIDENCE` — the verifier cannot establish agreement or conflict because required comparable evidence is missing or invalid. Roberta must not reinterpret this as a negative fact.
- data quality `HIGH`, `MEDIUM`, or `LOW` — a deterministic CMIS assessment based on verified identity, semantics, freshness, source coverage, and verification outcome. Roberta must preserve the level and reasons rather than inventing a more precise score.

Accepted CMIS evidence records may carry provenance such as:

- chain and fact type
- subject identity
- source and source role
- observation time
- block/slot when available
- raw fact identifier and raw value
- normalized value and unit when supplied by a verified adapter
- calculation/service version
- identity, semantics, and freshness verification flags
- warnings

Roberta may explain these fields but must not recompute CMIS verification in order to manufacture a different result.

## Accepted X1 verification building blocks on `main`

The following are accepted CMIS/core building blocks, not standalone Roberta production services:

### X1 RPC token-account balance transport

A read-only `getTokenAccountBalance` transport can collect raw token-account amount, decimals, context slot, commitment, account identity, and raw response.

The transport itself does not prove that the account is a pool reserve and remains non-promotable without identity and semantic proof.

### X1 pool/vault identity adapter

CMIS can consume an already-proven canonical pool/vault coupling record and expose a compact pool, vault, mint, and owner identity only when the upstream proof is unique and complete.

This proves identity relationships only. It does not prove provider reserve-field roles, reserve units, freshness, or value agreement.

### X1.Ninja pool-detail contract probe

CMIS has a read-only X1.Ninja single-pool detail transport that preserves the raw provider response and transport-contract provenance.

Observed provider field names or values are not automatically reserve facts. Roberta must not infer reserve semantics from names such as `pooledBase`, `pooledQuote`, `reserve`, or similar labels.

### X1 reserve semantic proof gate

CMIS has a fail-closed structural gate that can bind explicit provider field paths and units to an already-verified pool/vault/mint identity when an external semantic proof manifest is supplied with evidence references.

The manifest is an asserted proof input, not self-authenticating truth. The gate does not establish freshness or cross-source value agreement and does not make the result CMIS-promotable by itself.

## Not yet Roberta-consumable as production capability

Roberta must currently treat the following as unavailable unless and until a supported Roberta-facing wrapper and all required verification gates are accepted:

- `verification_evidence` as a callable Roberta service
- X1 reserve values derived from X1.Ninja pool-detail fields
- a provider/RPC reserve comparison produced from unproven provider units
- draft reserve evidence adapters, including work that depends on proving whether provider values are token units, token base units, or another documented unit
- any CMIS capability that exists only in an open or stacked PR

In particular, an accepted low-level CMIS primitive is **not** equivalent to a production Roberta service.

## Roberta consumption boundary

When a future supported service returns CMIS verification output, Roberta may:

- explain the verified fact and its provenance
- explain why evidence is high, medium, or low quality
- surface conflicts and insufficient evidence
- coordinate other specialists based on the returned status
- use verified facts in higher-level reasoning

Roberta must not:

- infer missing provider semantics or units
- convert `CONFLICT` into agreement
- convert `INSUFFICIENT_EVIDENCE` into a definitive fact
- recalculate deterministic CMIS comparisons to obtain a preferred answer
- treat a raw provider response or semantic-proof manifest as verified on its own
- treat analysis or verification output as authorization to sign, broadcast, trade, or move value

Human approval and execution safeguards remain separate from verification.

## Current interface status

The accepted CMIS trust layer is sufficiently stable for Roberta interface **design**, but the final machine-readable Roberta verification wrapper is not yet established on `main`.

Until that wrapper exists, Roberta should continue using the currently accepted callable market/tokenomics capabilities and treat CMIS verification primitives as internal specialist infrastructure rather than a public Roberta service surface.
