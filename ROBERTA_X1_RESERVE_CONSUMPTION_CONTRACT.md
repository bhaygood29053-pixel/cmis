# Roberta ↔ CMIS X1 Reserve Consumption Contract

## Purpose

This companion contract defines how Roberta may consume X1 reserve-verification results produced by the accepted CMIS reserve cross-check core on `main`.

It does **not** make the CMIS core directly callable by Roberta and does not replace `ROBERTA_INTEGRATION_CONTRACT.md`.

## Accepted CMIS capability

The accepted CMIS core includes `x1_reserve_crosscheck`, a deterministic, transport-free two-leg reserve verification orchestrator.

It composes already-established inputs through the accepted proof chain:

1. explicit reserve semantic proof,
2. deterministic reserve evidence adaptation,
3. exact same-fact verification for the asset reserve leg,
4. exact same-fact verification for the counter reserve leg.

The orchestrator does not discover pools or vaults, infer provider field meanings, infer units, fetch live state, invent freshness, or apply a tolerance.

## Roberta-facing status

**CMIS implementation status:** accepted core.

**Roberta invocation status:** unavailable until a supported Roberta-facing wrapper is implemented, tested, and accepted.

Roberta may design around the output semantics below, but must not call internal CMIS Python functions directly or present this as a production service merely because the core exists on `main`.

## Output semantics Roberta must preserve

A future wrapper may expose the following CMIS-produced meanings:

- `overall_verification`: `AGREEMENT`, `CONFLICT`, or `INSUFFICIENT_EVIDENCE`;
- per-role evidence and verification for `asset` and `counter` reserve legs;
- `observation_scope_verified`;
- semantic-proof state and rejection reasons;
- per-role data-quality results and reasons;
- warnings and errors;
- `cmis_promotable`.

Roberta may summarize or explain these fields. Roberta must not recompute them to obtain a preferred result.

## Promotion rule

Roberta must treat `cmis_promotable` as a CMIS trust decision, not as a confidence score.

A reserve result is not promotable merely because provider and RPC values numerically agree.

The accepted cross-check requires both reserve legs to satisfy the CMIS verifier, and promotion remains fail-closed when required observation scope, semantic proof, identity, units, or comparable evidence are not established.

Roberta must therefore preserve these distinctions:

- `AGREEMENT` + `cmis_promotable: true` — CMIS has accepted the supplied proof chain for the scoped observation;
- `AGREEMENT` + `cmis_promotable: false` — numerical/normalized agreement exists, but at least one required trust gate is still unverified;
- `CONFLICT` — comparable evidence disagrees; Roberta must surface the conflict;
- `INSUFFICIENT_EVIDENCE` — required evidence is missing or unusable; Roberta must not convert this into a negative or positive reserve fact.

## Freshness and observation scope

The accepted cross-check does not infer freshness from wall-clock proximity, provider timestamps, or RPC slot closeness.

`observation_scope_verified` is supplied proof state. If that state is absent or cannot be tied to an auditable observation time, the result remains non-promotable.

Roberta must not create its own freshness threshold or mark observation scope verified from timestamps it happens to receive.

## Provenance and data quality

When a future Roberta wrapper exposes reserve verification, it should preserve enough CMIS provenance to explain the result without exposing uncontrolled provider internals.

Relevant fields may include:

- chain and pool identity;
- reserve role (`asset` or `counter`);
- mint and vault identity where present in accepted evidence;
- provider field path and explicitly verified unit contract where present;
- RPC account and slot provenance where present;
- observation time;
- verification status and rejection reasons;
- deterministic data-quality level and reasons;
- service/version identity;
- promotion state.

Roberta must preserve CMIS data-quality levels and reasons rather than converting them into a new numeric confidence score.

## Scout / Roberta orchestration boundary

Liquidity Scout / CMIS owns:

- reserve identity and semantic gates;
- deterministic evidence normalization;
- exact reserve comparison;
- verification status;
- data-quality assessment;
- promotion eligibility.

Roberta owns:

- deciding when reserve evidence is relevant to the user's question;
- requesting the supported Liquidity Scout service once such a wrapper exists;
- coordinating reserve evidence with other specialists;
- explaining conflicts, insufficient evidence, and non-promotable agreement;
- broader reasoning and final user-facing synthesis;
- human approval boundaries for consequential actions.

Roberta must not duplicate CMIS reserve calculations as an independent second implementation.

## Risk and execution boundary

Reserve verification is evidence about market state. It is not a trade recommendation and is never execution authorization.

Roberta must not convert `cmis_promotable: true`, `AGREEMENT`, or high data quality into permission to sign, broadcast, trade, route funds, or move value.

Any future pre-trade or execution flow remains subject to separate Scout risk controls and explicit human approval gates.

## Draft CMIS capabilities that remain unavailable to Roberta

The following current development work is **not** part of this accepted Roberta consumption contract while it remains in open/draft PRs:

- RPC token-account identity transport and verifier beyond the currently accepted baseline;
- reserve promotion hardening that binds the accepted cross-check to new RPC token-account identity evidence;
- bounded live reserve evidence collection;
- deterministic live scope measurements;
- opt-in live reserve scope probes;
- sanitized reserve-scope artifact contracts;
- any holder-semantics work based on largest-token-account observations.

These capabilities may influence future interface design, but Roberta must not present them as production-ready or rely on their fields until they are accepted into `main` and the Roberta-facing contract is updated.

## Target wrapper requirement

The next Roberta-facing implementation should wrap the accepted CMIS result rather than exposing CMIS provider internals directly.

At minimum, a future machine-readable wrapper should carry:

- service identity;
- service status;
- asset/pool identity;
- overall verification status;
- per-role verification summaries;
- observation-scope state;
- data quality and reasons;
- bounded provenance references;
- warnings/errors;
- `cmis_promotable`.

Until that wrapper is accepted, Roberta must treat general X1 reserve verification as **accepted CMIS core but unavailable as a production Roberta service**.
