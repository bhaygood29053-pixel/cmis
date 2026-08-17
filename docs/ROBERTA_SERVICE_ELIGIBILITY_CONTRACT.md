# Roberta Service Eligibility Contract

## Purpose

This document defines when Roberta may treat a CMIS / Liquidity Scout capability as callable during orchestration.

It supplements `ROBERTA_INTEGRATION_CONTRACT.md` and `docs/ROBERTA_VERIFICATION_CONSUMPTION_BOUNDARY.md`. It does not promote any draft CMIS capability.

## Core rule

Roberta must distinguish **design visibility** from **runtime eligibility**.

A capability may be visible in an open branch, draft PR, roadmap, test fixture, or interface document without being eligible for a real Roberta service call.

Roberta may call a capability as an accepted service only when all required eligibility gates for that capability are satisfied on the accepted integration baseline.

## Capability states

### `implemented_core`

Reusable deterministic logic exists on the accepted integration baseline and is independently testable.

This state alone does not guarantee that a stable Roberta-facing wrapper exists.

### `wrapper_planned`

The accepted core exists, but Roberta must use only an already-supported internal integration path. It must not invent a public response schema that has not been implemented.

### `draft_core`

The capability exists only in open or stacked development work.

Roberta may use it for interface planning and contract review only. It is **not callable as production capability** and must not be represented to users as available.

### `planned`

The capability is roadmap-only and is unavailable for invocation.

## Runtime eligibility gates

Before Roberta treats a CMIS capability as callable, the integration layer must be able to establish all gates that apply to that capability:

1. **Baseline gate** — the implementation is accepted into the integration baseline rather than existing only in a draft/open PR.
2. **Contract gate** — the callable input/output contract is implemented or an explicitly supported internal wrapper exists.
3. **Verification gate** — any identity, semantic, unit, freshness, source-independence, or other proof requirements for the requested fact type are satisfied by CMIS.
4. **Test gate** — the relevant deterministic tests pass on the accepted implementation.
5. **Safety gate** — the capability does not cross a human-approval or execution boundary that has not been explicitly enabled.

If any required gate is unresolved, Roberta must treat the capability as unavailable for the requested production use.

## Current examples

### Existing market and lookup capabilities

Capabilities already described as `implemented core` in `ROBERTA_INTEGRATION_CONTRACT.md` may inform supported Roberta workflows, subject to their current wrapper limitations and existing deterministic return contracts.

Roberta must not claim a final public service schema where the contract still says the wrapper is planned.

### CMIS verification / reserve work

The current evidence/provenance, reserve-verification, direct X1 RPC balance, pool-vault identity, X1.Ninja pool-detail, and reserve semantic-proof work remains in stacked draft PRs.

Therefore:

- Roberta may design around those outputs;
- Roberta may not call them as accepted production services;
- Roberta may not present their draft outputs as verified production facts;
- Roberta may not bypass the missing promotion gates by interpreting raw provider fields itself.

## Orchestration fallback behavior

When Roberta needs a capability that is not runtime-eligible, it should prefer one of these outcomes:

- use an older accepted service only if it actually answers the requested question without weakening verification;
- return `unavailable` when the required capability is not accepted or exposed;
- return `partial` when an accepted subset of the requested information is available;
- preserve `ambiguous`, `conflict`, or insufficient-evidence semantics returned by CMIS rather than forcing a definitive answer.

Roberta must not silently substitute model memory, conversation history, a raw provider response, or draft-only CMIS behavior for an unavailable deterministic service.

## Scout / Roberta boundary

CMIS / Liquidity Scout decides whether specialist facts satisfy their deterministic verification and promotion rules.

Roberta decides which **eligible** specialist capability to invoke and how to synthesize accepted outputs with broader context.

Roberta must not change capability maturity, verification state, or promotion state through orchestration logic.

## Human approval and execution

Runtime eligibility for an informational capability is not authorization for consequential action.

Verification, recommendation, approval, transaction preparation, signing, and broadcasting remain separate states.

No service becomes execution-capable merely because its informational contract is accepted.

## Promotion discipline

When a draft capability is later merged, tested, and exposed through a supported Roberta-facing contract, its status should be updated deliberately in the integration contract.

Roberta should never infer promotion from PR existence, branch age, test fixtures, documentation, or naming alone.
