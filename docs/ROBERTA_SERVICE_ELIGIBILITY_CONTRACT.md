# Roberta Service Eligibility Contract

## Purpose

This document defines when Roberta may treat a CMIS / Liquidity Scout capability as callable during orchestration.

It supplements `ROBERTA_INTEGRATION_CONTRACT.md`, `ROBERTA_CMIS_ACCEPTED_BASELINE.md`, and `docs/ROBERTA_VERIFICATION_CONSUMPTION_BOUNDARY.md`.

It does not make an accepted low-level CMIS primitive automatically callable by Roberta.

## Core rule

Roberta must distinguish **design visibility**, **accepted core maturity**, and **runtime eligibility**.

A capability may exist on the accepted baseline and still be unavailable as a Roberta-callable service when its wrapper, fact-specific verification, test, or safety gates are not satisfied.

Roberta may call a capability as an accepted service only when all required eligibility gates for that capability are satisfied on the accepted integration baseline.

## Capability states

### `implemented_core`

Reusable deterministic logic exists on the accepted integration baseline and is independently testable.

This state alone does not guarantee that a stable Roberta-facing wrapper exists or that every fact produced by that core is verified for every asset or pool.

### `wrapper_planned`

The accepted core exists, but the final Roberta-facing callable contract is not yet implemented.

Roberta must not invent a public response schema or simulate a missing wrapper from low-level primitives.

### `draft_core`

The capability exists only in open or stacked development work.

Roberta may use it for interface planning and contract review only. It is **not callable as production capability** and must not be represented to users as available.

### `planned`

The capability is roadmap-only and is unavailable for invocation.

## Runtime eligibility gates

Before Roberta treats a CMIS capability as callable, the integration layer must establish all gates that apply to that capability:

1. **Baseline gate** — the implementation is accepted into the integration baseline rather than existing only in a draft/open PR.
2. **Contract gate** — the callable input/output contract is implemented or an explicitly supported internal wrapper exists.
3. **Verification gate** — any identity, semantic, unit, freshness, source-independence, coverage, or other proof requirements for the requested fact type are satisfied by CMIS.
4. **Test gate** — the relevant deterministic tests pass on the accepted implementation.
5. **Safety gate** — the capability does not cross a human-approval or execution boundary that has not been explicitly enabled.

If any required gate is unresolved, Roberta must treat the capability as unavailable for the requested production use.

Passing the baseline gate does not imply that the contract or verification gates pass.

## Instant X1 Scan eligibility — CMIS 1.13.0

`instant_x1_scan/v1` is a bounded read-only X1 composition service for ROBERTA once CMIS 1.13.0 is deployed and advertised by the live capability manifest.

Eligibility requirements remain fail-closed:

- chain must be `x1`;
- the live manifest must advertise `instant_x1_scan` as callable with service contract `instant_x1_scan/v1`;
- exact requested asset identity and current market prerequisites must resolve through CMIS;
- component facts retain their existing verification/partial/unavailable state;
- holder-looking values are not promoted when holder semantics/coverage are unverified;
- current top-account concentration remains unavailable in scan v1 rather than being synthesized from internal Phase 11 foundations;
- the scan history profile is limited to CMIS-stored verified observations and does not trigger provider backfill or X1 RPC coverage expansion;
- Proof Score remains evidence quality only and does not alter deterministic risk;
- execution remains unauthorized.

A `partial` Instant X1 Scan is a valid production result when one or more declared fields are unverified. ROBERTA must preserve those unknown/partial fields rather than filling them from memory or inference.
## Current examples

### Existing market and lookup capabilities

Capabilities described as `implemented core` in `ROBERTA_INTEGRATION_CONTRACT.md` may inform supported Roberta workflows, subject to their current wrapper limitations and existing deterministic return contracts.

Roberta must not claim a final public service schema where the contract still says the wrapper is planned.

### Accepted CMIS verification / reserve core

The accepted integration baseline now includes the evidence/provenance foundation, deterministic reserve verifier, direct X1 RPC token-account balance transport, pool-vault identity adapter, X1.Ninja pool-detail contract probe, explicit reserve semantic-proof gate, and fail-closed reserve evidence adapter.

These are accepted CMIS core building blocks. They are not, by themselves, a Roberta-callable production verification service.

Therefore:

- Roberta may design around their accepted output semantics and preserve CMIS-produced verification/provenance when a supported wrapper eventually exposes them;
- Roberta may not invoke low-level primitives as though `verification_evidence` were already a production service;
- Roberta may not infer provider field roles, units, identity, freshness, or source independence itself;
- Roberta may not bypass fact-specific promotion gates by interpreting raw provider fields or semantic manifests;
- Roberta must preserve `AGREEMENT`, `CONFLICT`, `INSUFFICIENT_EVIDENCE`, data-quality, provenance, and non-promotable states produced by CMIS.

### XENCAT/XNT reserve proof scope

For pool `6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry`, read-only evidence established a pool-specific binding in which X1.Ninja `pool.pooledBase` and `pool.pooledQuote` matched direct X1 RPC token-unit balances for the verified XENCAT and XNT vaults.

That proof is not a global rule for every X1.Ninja pool. Other pools require their own qualifying identity, semantic, unit, freshness, and value evidence before equivalent facts are eligible for promotion.

Roberta must not generalize the XENCAT/XNT result by field-name similarity alone.

## Orchestration fallback behavior

When Roberta needs a capability that is not runtime-eligible, it should prefer one of these outcomes:

- use an older accepted service only if it actually answers the requested question without weakening verification;
- return `unavailable` when the required capability is not accepted or exposed;
- return `partial` when an accepted subset of the requested information is available;
- preserve `ambiguous`, `conflict`, or insufficient-evidence semantics returned by CMIS rather than forcing a definitive answer.

Roberta must not silently substitute model memory, conversation history, a raw provider response, low-level CMIS primitives, or draft-only CMIS behavior for an unavailable deterministic service.

## Scout / Roberta boundary

CMIS / Liquidity Scout decides whether specialist facts satisfy their deterministic verification and promotion rules.

Roberta decides which **eligible** specialist capability to invoke and how to synthesize accepted outputs with broader context.

Roberta must not change capability maturity, verification state, data-quality state, or promotion state through orchestration logic.

## Human approval and execution

Runtime eligibility for an informational capability is not authorization for consequential action.

Verification, recommendation, approval, transaction preparation, signing, and broadcasting remain separate states.

No service becomes execution-capable merely because its informational contract or underlying core is accepted.

## Promotion discipline

When an accepted core capability later gains a supported Roberta-facing wrapper, its runtime status should be updated deliberately only after the applicable contract, verification, test, and safety gates are satisfied.

When a draft capability is merged, acceptance into the baseline satisfies only the baseline gate; it does not automatically satisfy the remaining runtime gates.

Roberta should never infer promotion from PR existence, branch age, test fixtures, documentation, naming, or the existence of low-level CMIS code alone.
