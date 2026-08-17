# Roberta Verification Consumption Boundary

## Purpose

This document narrows the Roberta ↔ CMIS boundary for verification and provenance data while the CMIS trust stack remains under active development.

It supplements `ROBERTA_INTEGRATION_CONTRACT.md`; it does not make any draft CMIS capability production-ready.

## Current capability status

The current accepted integration baseline does not yet expose CMIS reserve verification as a Roberta-callable production service.

Open CMIS draft work may define or test:

- evidence/provenance records
- deterministic agreement, conflict, and insufficient-evidence outcomes
- data-quality levels
- direct X1 RPC token-account balance collection
- pool/vault/mint identity proofs
- raw X1.Ninja pool-detail contract observation
- explicit provider semantic-proof gates

Roberta may use these draft contracts for interface planning only. It must not present their outputs as accepted production facts until the relevant CMIS changes are accepted and exposed through a supported service contract.

## What Roberta may consume

When CMIS eventually returns verification evidence through an accepted service contract, Roberta may consume and explain:

- verified fact identity
- normalized value and unit when CMIS has verified both
- source identity and source role
- observation timestamps
- block or slot provenance when available
- calculation/service version
- identity, semantic, unit, and freshness verification flags
- CMIS comparison outcome
- CMIS data-quality level and reasons
- CMIS promotion state

Roberta must preserve these values as CMIS-produced specialist evidence. It may summarize them for the user, but it must not recompute or reinterpret them into a stronger verification claim.

## What Roberta must not treat as verification

The following are not independently sufficient proof and must not be promoted by Roberta:

- a provider field whose name merely contains words such as `reserve`
- a raw provider response with undocumented field roles or units
- an identifier-looking provider field that has not been bound to proven pool/vault/mint identity
- an external semantic-proof manifest merely because it exists
- two values that look numerically similar but have unproven identity, units, semantics, or freshness
- two observations whose labels differ but whose independence has not been established by CMIS
- a low-quality, conflicting, or insufficient-evidence result

Provider field discovery is observation, not semantic proof.

A semantic-proof manifest is evidence supplied to CMIS for deterministic validation; it is not self-authenticating truth. Roberta must rely on CMIS to determine whether that manifest passed the required identity, field-path, unit, semantic, and evidence-reference gates.

## Required status preservation

When CMIS returns a verification state, Roberta must preserve its meaning:

- `AGREEMENT` — CMIS has determined that the compared observations satisfy the verifier's required identity, unit, semantic, and value rules.
- `CONFLICT` — qualifying evidence disagrees; Roberta must surface the disagreement rather than choose or average a value.
- `INSUFFICIENT_EVIDENCE` — CMIS cannot prove the requested fact from the available qualifying evidence; Roberta must not treat this as either confirmation or rejection of the fact.

If CMIS marks a fact as non-promotable, Roberta may explain why but must not convert it into a verified market fact.

## Scout and Roberta responsibilities

CMIS / Liquidity Scout owns:

- deterministic provider contract checks
- pool/vault/mint identity verification
- provider field/semantic/unit verification
- source-independence determination
- comparison and disagreement rules
- data-quality classification
- promotion or fail-closed decisions
- provenance creation

Roberta owns:

- deciding which specialist service to call
- combining accepted specialist outputs with broader context
- explaining verification state and uncertainty to the user
- coordinating follow-up specialist queries
- preserving user policy and human approval boundaries

Roberta must not create a parallel reserve verifier, infer undocumented provider semantics, or manufacture an independent second source from the same underlying evidence.

## Execution boundary

Verification evidence is informational. Neither `AGREEMENT`, high data quality, nor CMIS promotion authorizes a transaction.

Roberta must keep verification, recommendation, approval, transaction preparation, signing, and broadcasting as distinct states. Human approval and future execution safeguards remain separate requirements.

## Promotion rule for this document

This boundary may guide Roberta interface design now, but any service names or fields described here remain provisional until the underlying CMIS capability is accepted into the integration baseline and the Roberta-facing wrapper is implemented and tested.
