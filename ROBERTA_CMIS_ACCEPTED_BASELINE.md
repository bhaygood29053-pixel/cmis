# Roberta ↔ CMIS Accepted Baseline

## Purpose

This document records CMIS trust-layer semantics accepted on `main` and safe for Roberta/Scout interface design.

It does **not** make internal CMIS primitives directly callable by Roberta. Public service eligibility is determined by the live Scout ↔ CMIS capability manifest, and Roberta reaches CMIS through the relevant Chain Scout.

`ROBERTA_INTEGRATION_CONTRACT.md` remains the primary authority-boundary document.

## Current contract baseline

Accepted CMIS capability contract:

```text
schema_version = 1
global existing-service minimum = 1.8.0
current CMIS contract = 1.9.0
```

The accepted manifest includes:

- public chain/service eligibility;
- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- risk/proof separation;
- missing-evidence-is-unknown semantics;
- read-only Phase 11 `intelligence_foundation` with public-service and Scout-reliance promotion false;
- one separately promoted read-only X1 intelligence service, `concentration_change_intelligence`, under service contract `concentration_change_intelligence/v1`.

Roberta does not call capability discovery directly; Scouts validate it before CMIS dispatch.

The promoted X1 intelligence service requires CMIS contract `1.9.0` or newer for that operation. Existing accepted services may continue to use the older global minimum where their own contract permits it.

## First promoted Verified Intelligence service — ACCEPTED / BOUNDED X1 ONLY

CMIS now exposes one narrow public/Scout-reliance wrapper over the Phase 11 foundation:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1 only
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
read_only = true
execution_authorized = false
```

The service is callable only when the live manifest proves the exact promotion fields and the request supplies an exact X1 asset plus canonical CMIS-owned `ie_<64 lowercase hex>` intelligence evidence id.

CMIS resolves and revalidates the evidence internally. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state are not accepted as a shortcut to trust.

The service does **not** promote the underlying Phase 11 foundation objects. It does not establish holder-total or beneficial-owner semantics, does not convert Proof Score into risk, does not add whale/insider/bot/intent/ownership labels, and does not authorize execution.

Solana remains unavailable/non-promoted for this service until a separate accepted contract says otherwise.

Roberta has separately adopted this exact service through X1 Scout with fail-closed CMIS 1.9 promotion checks and readiness coverage. That adoption does not broaden CMIS scope.

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

Recent live provider-gap observations remain non-promotional. The current repository X1.Ninja credential received HTTP `403` / `access_denied` on the bounded SSE handshake probe, and a same-run XENCAT holder-looking comparison observed provider candidate `116`, RPC token-account candidate `180`, and unique token-account-authority candidate `174`. Those observations do not establish stream semantics, holder totals, wallet identity, beneficial ownership, or provider/RPC completeness.

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

The core Phase 11 intelligence primitives remain outside automatic public `supported_services` / Scout reliance. The separately promoted `concentration_change_intelligence/v1` wrapper is the only accepted exception at this checkpoint and is limited to its exact X1 evidence-id scope.

## Roberta consumption boundary

Roberta may:

- explain verified facts and provenance;
- explain proof quality separately from risk;
- surface conflicts and insufficient evidence;
- coordinate specialists based on accepted service output;
- use verified CMIS facts in broader reasoning;
- provide answer-first conversational synthesis;
- request the separately promoted X1 `concentration_change_intelligence/v1` service through X1 Scout when the exact capability and evidence-id gates pass.

Roberta must not:

- infer missing provider semantics/units;
- generalize pool/route-specific proof to another scope;
- convert conflict into agreement;
- convert insufficient evidence into a definitive fact;
- recalculate deterministic CMIS comparisons to obtain a preferred answer;
- treat raw provider responses or asserted proof labels as verified on their own;
- turn the remaining internal intelligence foundations into public services;
- broaden the promoted concentration-change service beyond its exact accepted conclusion/scope;
- treat analysis, proof, PASS, or human review as authorization to execute value movement.

## Execution boundary

No accepted baseline authorizes transaction construction, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or autonomous value movement.

Roberta's future Controlled Execution milestone remains separately locked/not started.
