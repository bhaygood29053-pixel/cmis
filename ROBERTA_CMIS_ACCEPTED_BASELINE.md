# Roberta ↔ CMIS Accepted Baseline

## Purpose

This document records CMIS trust-layer semantics accepted on `main` and safe for Roberta/Scout interface design.

It does **not** make internal CMIS primitives directly callable by Roberta. Public service eligibility is determined by the live Scout ↔ CMIS capability manifest, and Roberta reaches CMIS through the relevant Chain Scout.

`ROBERTA_INTEGRATION_CONTRACT.md` remains the primary authority-boundary document.

## Current contract baseline

Accepted CMIS capability contract:

```text
schema_version = 1
contract_version >= 1.8.0
```

The accepted manifest includes:

- public chain/service eligibility;
- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- risk/proof separation;
- missing-evidence-is-unknown semantics;
- read-only Phase 11 `intelligence_foundation` with public-service and Scout-reliance promotion false.

Roberta does not call capability discovery directly; Scouts validate it before CMIS dispatch.

## Accepted evidence semantics

Roberta-facing interfaces may preserve these CMIS meanings when returned by an accepted service:

- `AGREEMENT` — comparable same-fact observations agree under the applicable verifier;
- `CONFLICT` — accepted comparison evidence disagrees; do not average or choose a preferred value unless a fact-specific CMIS contract says so;
- `INSUFFICIENT_EVIDENCE` — required comparable evidence is missing/invalid; do not reinterpret this as a negative fact;
- deterministic data/proof quality with explicit reasons and unresolved categories;
- Evidence Receipts preserving source/provenance, scope, freshness, disagreements, limitations, and unresolved fields;
- Proof Scores that remain separate from market risk.

Roberta may explain these meanings but must not recompute CMIS verification/proof to manufacture a different result.

## `verification_evidence` — ACCEPTED CALLABLE SERVICE WHERE MANIFEST PERMITS

The earlier baseline that treated `verification_evidence` as future-only is obsolete.

Accepted trust path:

```text
fact-specific verifier
  ↓
sanitized verification envelope
  ↓
content-addressed evidence ledger
  ↓
exact lookup
  ↓
CMIS verification_evidence
  ↓
Chain Scout
  ↓
Roberta
```

Only exact accepted selectors and CMIS-promotable verified agreement may expose a promoted fact value/unit. Conflict, stale/non-promotable agreement, and insufficient evidence remain explicit.

## Accepted X1 building blocks

CMIS includes accepted read-only X1 primitives such as:

- RPC token-account balance transport;
- independently proven pool/vault/mint identity adapters;
- X1.Ninja/XDEX read-only provider transports;
- fail-closed reserve semantic binding;
- provider/RPC reserve evidence comparison;
- deterministic XDEX trade verification;
- persisted verification evidence;
- bounded historical evidence and activity primitives.

A low-level primitive is not automatically a public Scout service. Scope, identity, semantics, units, freshness, and promotion rules remain explicit.

## X1 / XDEX semantic baseline

The original XENCAT/native-XNT reserve proof remains one concrete example rather than a universal provider rule.

Since that proof, accepted XDEX evidence has advanced field-by-field:

- exact route/config identity can be verified for tested routes;
- route-scoped price impact can be independently reproduced where accepted reserve/config evidence exists;
- quote slippage uses percent units in tested scope;
- quote slippage tolerance/minimum-received semantics are distinct from expected execution slippage;
- selected 1-minute history timestamp/OHLC semantics have bounded verification/corroboration;
- the pinned XENCAT/native-XNT 2800-ppm historical execution model is strongly corroborated by a 23-swap state-contiguous sequence and 3000-ppm execution is strongly rejected for that tested sequence;
- the private backend reason for the separate 3000-ppm quote baseline remains unavailable;
- hidden/router/platform fee attribution remains unproven;
- global route optimality, fill quality, route quality, generic execution quality, and universal XDEX execution semantics remain unavailable.

Roberta must preserve these scope limits.

## Pre-trade baseline

CMIS pre-trade analysis can deterministically evaluate verified trade size against verified liquidity and explicit versioned policy.

A hardened internal route-evidence seam can additionally expose selected exact-route facts only when accepted source, identity, freshness, semantic, unit, proof-basis, and value-shape gates pass.

Current accepted distinctions:

- route-scoped price impact may be usable where exact proof gates pass;
- bounded 0.28% AMM/execution-model fee evidence may be usable for exact accepted scope;
- the 0.30% quote-side curve behavior is not presented as an executed hidden fee;
- quote slippage tolerance is not expected execution slippage;
- expected execution slippage remains unavailable without its own accepted execution observation contract;
- route quality, fill quality, transaction simulation, and execution quality remain unavailable unless separately proven.

The public HTTP gateway does not accept arbitrary caller-supplied internal route evidence as a shortcut to verification.

Every current pre-trade result remains analysis-only with execution authorization false.

## Phase 11 Verified Intelligence baseline

CMIS has accepted read-only foundations for:

- exact top-account concentration;
- numeric concentration changes under compatible scope;
- neutral wallet activity facts;
- sanitized sparse historical intelligence;
- evidence-bound conclusions with content-addressed receipts/proof;
- deterministic explicit-policy concentration-threshold evaluation.

These foundations do not authorize or prove whale, insider, bot, accumulator, distributor, market-maker, ownership, relationship, manipulation, fraud, or behavioral-intent labels.

The core Phase 11 intelligence primitives remain outside public `supported_services` and outside automatic Scout reliance.

## Roberta consumption boundary

Roberta may:

- explain verified facts and provenance;
- explain proof quality separately from risk;
- surface conflicts and insufficient evidence;
- coordinate specialists based on accepted service output;
- use verified CMIS facts in broader reasoning;
- provide answer-first conversational synthesis.

Roberta must not:

- infer missing provider semantics/units;
- generalize pool/route-specific proof to another scope;
- convert conflict into agreement;
- convert insufficient evidence into a definitive fact;
- recalculate deterministic CMIS comparisons to obtain a preferred answer;
- treat raw provider responses or asserted proof labels as verified on their own;
- turn internal intelligence foundations into public services;
- treat analysis, proof, PASS, or human review as authorization to execute value movement.

## Execution boundary

No accepted baseline authorizes transaction construction, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or autonomous value movement.

Roberta's future Controlled Execution milestone remains separately locked/not started.
