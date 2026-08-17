# Roberta ↔ CMIS Accepted Runtime Baseline

## Purpose

This companion contract records the accepted runtime boundary for Roberta consumption after CMIS PRs #87 and #88.

It supplements `ROBERTA_INTEGRATION_CONTRACT.md`. It does not widen Roberta's execution authority and does not make draft provider work production-ready.

## Accepted CMIS runtime capability

On accepted CMIS `main`, `verification_evidence` is now exposed through the production CMIS HTTP runtime.

The accepted path is:

```text
fact-specific verifier
  -> verification_evidence wrapper
  -> sanitized content-addressed evidence ledger
  -> exact read-only lookup
  -> verification_evidence gateway
  -> RuntimeCMISGateway
  -> POST /v1/cmis
```

PR #87 accepted the exact gateway selector boundary.

PR #88 accepted the HTTP/runtime composition and internal evidence-ledger configuration.

The accepted post-merge baseline is CMIS `main` SHA `08ac97810163168048192665d314cce90f5b89fa`.

## Exact selector boundary

A `verification_evidence` request may select evidence using exactly one of these modes:

1. stable `evidence_id`; or
2. exact `fact_type` + `subject_id` for the latest stored record for that fact.

Roberta must not replace those selectors with:

- a free-form asset name;
- symbol guessing;
- pool discovery;
- a database path;
- a ledger object;
- raw provider payloads;
- raw verifier objects;
- caller-selected verification state;
- caller-selected confidence or data quality;
- caller-selected `cmis_promotable` state.

CMIS owns evidence identity, storage validation, exact fact selection, and verification semantics.

## Internal ledger boundary

The runtime configures the verification-evidence ledger internally.

The database path may be selected by deployment configuration, including `CMIS_VERIFICATION_EVIDENCE_DB`, but it is not an HTTP request parameter.

Roberta must not know, choose, or depend on the ledger file path.

A valid runtime route does not imply that a requested evidence record exists. An empty or missing ledger record remains explicit `unavailable`.

## Roberta runtime eligibility

**CMIS HTTP status:** accepted and production-runtime eligible on the CMIS side.

**Roberta typed-client status:** not established by this repository contract alone.

Roberta may add a typed `verification_evidence` operation only when its own client/Scout boundary preserves the accepted exact-selector contract and deterministic failure semantics.

Until that Roberta-side adapter is accepted, Roberta must not bypass its typed CMIS client by calling internal Liquidity Scout Python modules directly.

## Required Roberta client behavior

A future Roberta client operation must:

- name the target chain explicitly;
- send `service="verification_evidence"`;
- send no free-form top-level asset selector for evidence lookup;
- accept exactly one supported selector mode;
- preserve CMIS response status without strengthening it;
- preserve evidence identity and provenance returned by CMIS;
- preserve `AGREEMENT`, `CONFLICT`, and `INSUFFICIENT_EVIDENCE` semantics;
- preserve deterministic data-quality level and reasons;
- preserve identity, semantics, unit, freshness, and observation-scope state when present;
- preserve `cmis_promotable` as a CMIS trust decision;
- preserve `unavailable` when no stored evidence exists;
- fail closed on malformed or identity-mismatched CMIS responses.

Roberta must not recalculate evidence hashes, re-run CMIS comparison math, average conflicts, or manufacture a promoted value from observations.

## Scout orchestration boundary

The safe specialist path remains:

```text
Roberta
  -> Chain Scout
    -> typed CMIS client
      -> CMIS HTTP runtime
```

`verification_evidence` should initially be explicit-only at the Scout planning boundary unless a later accepted planning contract proves a safe deterministic reason to make evidence lookup autonomous.

A model must not invent an evidence selector from an asset name or add raw-provider verification work to a plan.

## Verification and promotion semantics

Roberta must preserve the distinction between numerical agreement and promotion eligibility.

- `AGREEMENT` + `cmis_promotable: true`: CMIS accepted the required proof gates for the scoped fact.
- `AGREEMENT` + `cmis_promotable: false`: comparable observations agree, but at least one required trust gate remains unsatisfied. Roberta must not manufacture a promoted fact.
- `CONFLICT`: comparable evidence disagrees. Roberta must surface the conflict rather than choose or average sources.
- `INSUFFICIENT_EVIDENCE`: evidence is missing, structurally invalid, semantically incomparable, stale under the applicable rule, or otherwise unusable. Roberta must not reinterpret this as a positive or negative fact.

## Provenance and data quality

When returned by CMIS, Roberta should preserve audit-relevant fields such as:

- chain;
- fact type and subject identity;
- normalized value and unit when CMIS permits promotion;
- source identity and source role;
- observation time;
- block/slot provenance;
- raw fact identifier;
- identity/semantics/unit/freshness verification state;
- deterministic comparison outcome;
- deterministic data-quality level and reasons;
- calculation/service version;
- warnings and errors;
- `cmis_promotable`;
- evidence reference, including stable `evidence_id` and `recorded_at` when lookup-backed.

Roberta may explain this evidence. It must not convert deterministic CMIS quality into a more precise-looking invented score.

## Risk boundary

Acceptance of `verification_evidence` does not make the Scout Risk Engine complete.

The authoritative integration contract still governs whether `risk_check` and `pre_trade_check` are production-callable. Evidence agreement, high data quality, or `cmis_promotable: true` must not be converted into a synthetic risk classification.

Reserve evidence, supply evidence, price evidence, or holder evidence may inform future accepted risk services, but Roberta must not build a parallel deterministic risk engine from those components.

## Execution and approval boundary

Verification evidence is read-only intelligence.

It never authorizes:

- transaction construction;
- signing;
- broadcasting;
- trading;
- swaps;
- bridge transfers;
- wallet permissions;
- value movement.

Any future consequential action remains behind separate risk controls and explicit human approval gates.

## Cross-chain boundary

The accepted runtime service contract is provider-neutral, but accepted provider coverage remains chain-specific.

Open Solana PRs #79–#85 are draft provider/source/evidence/cross-check development. They do not make Solana a production Roberta CMIS chain.

Roberta must not infer live Solana eligibility from the existence of provider-neutral `verification_evidence` infrastructure.

No fallback from an unsupported Solana request to X1 is permitted.

## Open X1 trust work

Current open X1 trust PRs remain draft until merged and accepted. This includes holder semantics/coverage, total token-account completeness, reserve observation-scope evidence, history/streaming redundancy, and related provider probes.

Roberta may design provider-neutral interfaces around established CMIS meanings, but it must not present open PR results as accepted market truth.

## Integration status summary

The correct boundary after PR #88 is:

- verification wrapper: accepted;
- sanitized content-addressed ledger: accepted;
- exact lookup: accepted;
- gateway dispatch: accepted;
- HTTP runtime composition: accepted;
- request-controlled ledger configuration: forbidden;
- automatic evidence backfill/persistence for every fact producer: not implied;
- Roberta typed-client eligibility: separate Roberta-side acceptance required;
- autonomous evidence-selection planning: not established;
- Solana production provider eligibility: not established;
- autonomous execution: forbidden.

## Core rule

**CMIS determines and preserves the verification state of supported facts.**

**Chain Scouts request and interpret only accepted CMIS operations.**

**Roberta coordinates those specialist results and explains them without recreating CMIS trust logic.**
