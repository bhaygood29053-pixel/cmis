# Roberta ↔ CMIS X1 Reserve Consumption Contract

## Purpose

This companion contract defines how Roberta may consume X1 reserve-verification semantics produced by the accepted CMIS trust core on `main`.

It does **not** make reserve verification or `verification_evidence` directly callable by Roberta and does not replace `ROBERTA_INTEGRATION_CONTRACT.md`.

## Accepted CMIS capability

The accepted CMIS core includes `x1_reserve_crosscheck`, a deterministic, transport-free two-leg reserve verification orchestrator.

It composes already-established inputs through the accepted proof chain:

1. explicit reserve semantic proof,
2. deterministic reserve evidence adaptation,
3. exact same-fact verification for the asset reserve leg,
4. exact same-fact verification for the counter reserve leg.

The orchestrator does not discover pools or vaults, infer provider field meanings, infer units, fetch live state, invent freshness, or apply a tolerance.

The accepted verification-evidence baseline now also includes:

- PR #73 — a sanitized standard `verification_evidence` envelope builder over an already-produced CMIS verifier result;
- PR #74 — a persistent sanitized, content-addressed evidence ledger;
- PR #75 — a read-only exact lookup adapter over that ledger.

These are accepted CMIS internals. Their acceptance does **not** by itself make `verification_evidence` a gateway-callable Roberta service.

## Accepted evidence lookup boundary

The accepted lookup supports exactly two selector modes:

1. stable `evidence_id`; or
2. exact `fact_type` + `subject_id` for the latest stored record for that fact.

The modes are mutually exclusive. Free-form asset-name evidence selection, raw verifier objects, raw provider responses, and arbitrary evidence queries are not accepted selectors.

Before releasing a stored record, CMIS revalidates the sanitized envelope and verifies its content-addressed evidence identity, chain identity, service identity, fact identity, and recorded timestamp. Roberta must treat those checks as CMIS responsibilities and must not reproduce them as a second verification implementation.

## Roberta-facing status

**CMIS reserve implementation status:** accepted core.

**Verification-envelope status:** accepted internal wrapper on `main`.

**Evidence persistence status:** accepted internal content-addressed ledger on `main`.

**Exact evidence lookup status:** accepted internal read-only adapter on `main`.

**Roberta invocation status:** unavailable.

The current `CMISGateway.SUPPORTED_SERVICES` does not register `verification_evidence`, and the current gateway does not inject the evidence ledger or dispatch exact evidence selectors. Therefore Roberta must not call `verification_evidence`, call internal Python helpers directly, or present reserve verification as a production service.

## Output semantics Roberta must preserve

A future callable service may expose the following CMIS-produced meanings:

- `overall_verification`: `AGREEMENT`, `CONFLICT`, or `INSUFFICIENT_EVIDENCE`;
- per-role evidence and verification for `asset` and `counter` reserve legs;
- `observation_scope_verified`;
- semantic-proof state and rejection reasons;
- deterministic data-quality results and reasons;
- warnings and errors;
- `cmis_promotable`;
- a stable evidence reference when returned from the accepted ledger lookup.

The accepted verification wrapper establishes an important presentation rule: a normalized fact value/unit is exposed as the promoted fact only for a CMIS-promotable agreement. A non-promotable agreement may retain agreeing observation values as evidence while leaving the promoted fact value/unit empty.

The accepted lookup may add an evidence reference containing the stable `evidence_id` and ledger `recorded_at` value. It otherwise preserves the stored CMIS verification result rather than recalculating or strengthening it.

Roberta may summarize or explain these fields. Roberta must not recompute them to obtain a preferred result.

## Promotion rule

Roberta must treat `cmis_promotable` as a CMIS trust decision, not as a confidence score.

A reserve result is not promotable merely because provider and RPC values numerically agree.

Roberta must preserve these distinctions:

- `AGREEMENT` + `cmis_promotable: true` — CMIS has accepted the supplied proof chain for the scoped observation;
- `AGREEMENT` + `cmis_promotable: false` — numerical/normalized agreement exists, but at least one required trust gate is still unverified; no promoted fact value may be manufactured from it;
- `CONFLICT` — comparable evidence disagrees; Roberta must surface the conflict rather than average or choose a source;
- `INSUFFICIENT_EVIDENCE` — required evidence is missing or unusable; Roberta must not convert this into a negative or positive reserve fact.

## Freshness and observation scope

The accepted reserve cross-check does not infer freshness from wall-clock proximity, provider timestamps, or RPC slot closeness.

`observation_scope_verified` is supplied CMIS proof state. If that state is absent or cannot be tied to an auditable observation time, the result remains non-promotable.

Roberta must not create its own freshness threshold, infer a common observation window, or mark observation scope verified from nearby timestamps or slots.

## Provenance and data quality

When a future Roberta-callable service exposes reserve verification, it should preserve enough CMIS provenance to explain the result without exposing uncontrolled provider internals.

Relevant fields may include:

- chain and pool identity;
- reserve role (`asset` or `counter`);
- fact type and subject identity;
- mint and vault identity where present in accepted evidence;
- provider field path and explicitly verified unit contract where present;
- RPC account and slot provenance where present;
- observation time;
- verification status and rejection reasons;
- deterministic data-quality level and reasons;
- service/version identity;
- promotion state;
- stable `evidence_id` and `recorded_at` when returned by the accepted lookup.

Roberta must preserve CMIS data-quality levels and reasons rather than converting them into a new numeric confidence score.

Roberta must also preserve the distinction between observations and a promoted fact. Observation values are provenance; they are not automatically a verified fact merely because they agree.

## Scout / Roberta orchestration boundary

Liquidity Scout / CMIS owns:

- reserve identity and semantic gates;
- deterministic evidence normalization;
- exact reserve comparison;
- verification status;
- data-quality assessment;
- promotion eligibility;
- verification-envelope construction;
- evidence sanitization and persistence;
- content-addressed evidence identity;
- exact evidence lookup and lookup validation;
- future gateway registration and service dispatch.

Roberta owns:

- deciding when reserve evidence is relevant to the user's question;
- requesting a supported Liquidity Scout service only after runtime eligibility exists;
- supplying only selectors permitted by the accepted service contract;
- coordinating returned CMIS evidence with other specialists;
- explaining conflicts, insufficient evidence, and non-promotable agreement;
- broader reasoning and final user-facing synthesis;
- human approval boundaries for consequential actions.

Roberta must not duplicate CMIS reserve calculations, evidence hashing, ledger validation, or fact verification as an independent second implementation.

Roberta must not submit raw verifier objects, provider responses, or free-form guessed evidence to manufacture `verification_evidence`.

## Risk and execution boundary

Reserve verification is evidence about market state. It is not a trade recommendation and is never execution authorization.

Roberta must not convert `cmis_promotable: true`, `AGREEMENT`, high data quality, or a valid evidence ID into permission to sign, broadcast, trade, route funds, or move value.

`risk_check` and `pre_trade_check` remain planned capabilities in the authoritative integration contract. Roberta must not synthesize those outputs from reserve evidence or other verified market facts.

Any future pre-trade or execution flow remains subject to separate Scout risk controls and explicit human approval gates.

## Current draft capabilities that remain unavailable to Roberta

The following current development work remains outside the accepted Roberta consumption surface while it is open/draft or not gateway-eligible:

- gateway registration/dispatch for `verification_evidence`;
- gateway dependency injection for the accepted evidence ledger;
- Roberta-side runtime eligibility for `verification_evidence`;
- RPC token-account identity and reserve-promotion hardening beyond the currently accepted reserve baseline;
- bounded live reserve evidence collection, scope measurements, probes, sanitized scope artifacts, and repeated-sample summaries;
- holder-semantics, total-token-account, and concentration work in the current X1 holder-verification stack;
- streaming/history/bridge source-discovery work that remains evaluation or probe-only;
- the Solana provider/source/cross-check PR stack, including PRs #79–#85.

The Solana work is particularly important to keep separate: the current gateway recognizes Solana as a planned chain but does not support it as a production chain. Open Solana RPC, Jupiter, Helius, DEX Screener, price-cross-check, and supply-cross-check work must not be represented by Roberta as accepted cross-chain CMIS service capability.

## Remaining callable-service requirement

PRs #73–#75 close the internal wrapper, persistence, and exact lookup gaps. They do **not** close the Roberta invocation gap.

Before Roberta may invoke `verification_evidence` in production, the accepted integration baseline still needs, at minimum:

1. gateway registration of `verification_evidence` through a supported service contract;
2. explicit injection of the accepted verification-evidence ledger into the gateway;
3. fail-closed dispatch that permits only accepted exact selectors;
4. rejection of free-form asset selection and unexpected/raw evidence parameters;
5. deterministic gateway eligibility and contract tests on the final accepted baseline;
6. Roberta-side runtime capability gating that refuses the service until the gateway contract is accepted.

A future machine-readable callable response should carry the accepted standard service envelope and preserve:

- service identity and service status;
- chain and exact fact identity;
- verification status;
- promoted fact value/unit only when CMIS permits promotion;
- bounded observations/provenance;
- deterministic data quality and reasons;
- warnings/errors;
- `cmis_promotable`;
- stable evidence reference when lookup-backed.

Until those gates are accepted, Roberta must treat general X1 reserve verification / `verification_evidence` as **accepted CMIS core with accepted internal evidence storage and lookup, but unavailable as a production Roberta service**.
