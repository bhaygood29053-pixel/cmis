# Roberta ↔ CMIS Accepted Baseline

Last reconciled: 2026-08-23 (America/New_York)

## Purpose

This document records CMIS trust-layer semantics accepted on `main` and safe for Roberta/Chain Scout interface design.

It does **not** make internal CMIS primitives directly callable by Roberta. Public service eligibility is determined by the live Scout ↔ CMIS capability manifest, and Roberta reaches CMIS through the relevant Chain Scout.

`ROBERTA_INTEGRATION_CONTRACT.md` remains the primary authority-boundary document.

## Canonical hierarchy

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

Roberta coordinates and explains. Chain Scouts investigate/interpret within chain scope. CMIS owns deterministic facts, evidence, proof quality, risk, capability state, and bounded analysis-only pre-trade calculations.

Roberta Learning System sources, Pyramid training state, LangGraph checkpoints, HXMP memory, policy state, and human review do not override CMIS for freshness-sensitive market/blockchain facts.

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
- one separately promoted read-only X1 intelligence service: `concentration_change_intelligence/v1`.

Accepted internal/non-promoted deterministic foundations additionally include:

- descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership semantics;
- concentration-threshold alert evidence completed by Issue #263 / PR #264.

None of those internal foundations adds a capability-manifest service or Scout dispatch authority.

Roberta does not call capability discovery directly; Scouts validate exact capability state before CMIS dispatch.

## Accepted Roberta-facing service surface

Depending on exact chain capability state, CMIS exposes services including:

```text
asset_lookup
market_report
rank
historical_compare
tokenomics
risk_check
pre_trade_check
verification_evidence
concentration_change_intelligence
```

The live capability manifest is authoritative. A service available for one chain is never inferred to exist for another chain.

## First promoted Verified Intelligence service — ACCEPTED / BOUNDED X1 ONLY

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1 only
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
read_only = true
execution_authorized = false
```

The service is callable only when the live manifest proves the exact promotion fields and the request supplies an exact X1 asset plus canonical CMIS-owned intelligence evidence id.

CMIS resolves and revalidates the evidence internally. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state are not accepted as trust shortcuts.

The service does **not**:

- promote the underlying Phase 11 foundation as a whole;
- promote the later classification/relationship/alert foundations;
- establish unique-holder or beneficial-owner semantics;
- convert Proof Score into risk;
- add whale/insider/bot/intent/ownership labels;
- authorize execution.

Solana remains unavailable/non-promoted for this service until a separate accepted contract says otherwise.

Roberta has separately adopted this exact service through X1 Scout with fail-closed CMIS 1.9 promotion checks and readiness coverage. That adoption does not broaden CMIS scope.

## Accepted evidence semantics

Roberta-facing interfaces may preserve these CMIS meanings when returned by an accepted service:

- `AGREEMENT` — comparable same-fact observations agree under the applicable verifier;
- `CONFLICT` — accepted comparison evidence disagrees; do not average or choose a preferred value unless a fact-specific CMIS contract says so;
- `INSUFFICIENT_EVIDENCE` — required comparable evidence is missing/invalid; do not reinterpret this as a negative fact;
- explicit data/proof quality with reasons and unresolved categories;
- Evidence Receipts preserving source/provenance, scope, freshness, disagreements, limitations, and unresolved fields;
- Proof Scores that remain separate from market risk.

Roberta may explain these meanings but must not recompute CMIS verification/proof to manufacture a different result.

## Source independence baseline

CMIS source-independence semantics are explicitly tri-state where applicable:

```text
true  = accepted fact-specific independence proof exists
false = independence was explicitly disproven / structurally impossible
null  = independence remains unknown or unproven
```

Distinct provider/source names alone do not prove independence.

Same-fact agreement and source independence remain separate evidence dimensions. Positive independent-agreement credit requires both accepted same-fact agreement and accepted independence for the relevant reported/verifier observation pair.

Roberta must not infer independence from branding, labels, or the presence of multiple URLs.

## `verification_evidence` baseline

`verification_evidence` is an accepted callable service where the manifest permits.

Accepted trust path:

```text
fact-specific verifier
  -> sanitized verification envelope
  -> content-addressed evidence ledger
  -> exact lookup
  -> CMIS verification_evidence
  -> Chain Scout
  -> Roberta
```

Only exact accepted selectors and CMIS-promotable verified agreement may expose a promoted fact value/unit. Conflict, stale/non-promotable agreement, and insufficient evidence remain explicit.

## Accepted X1 building blocks

Accepted read-only X1 primitives include, where exact contracts permit:

- RPC token-account balance/supply/authority transport;
- independently proven pool/vault/mint identity adapters;
- X1.Ninja/XDEX read-only provider transports;
- fail-closed reserve semantic binding;
- provider/RPC reserve evidence comparison;
- deterministic XDEX trade verification;
- persisted verification evidence;
- bounded historical evidence/activity;
- transaction→pool membership proof over exact verified transaction/instruction/vault evidence;
- historical provider-row binding to exact pool-membership evidence;
- field-specific source-independence/finality/completeness states.

A low-level primitive is not automatically a public Scout service. Scope, identity, semantics, units, freshness, and promotion rules remain explicit.

## Current X1 provider-gap observations — NON-PROMOTIONAL

Issue #30 remains open.

Accepted `main` observations include:

- current tested X1.Ninja SSE credential returned HTTP 403 / `access_denied` on the bounded handshake probe;
- one same-run XENCAT holder-looking comparison observed provider candidate `116`, RPC token-account candidate `180`, and unique token-account-authority candidate `174`;
- those observations do not establish stream semantics, holder totals, wallet identity, beneficial ownership, enumeration completeness, or source independence.

Current open provider-gap branches are not accepted capability:

- **PR #242** — Warp Bridge proof-origin binding; draft/open. It hardens provenance eligibility but does not approve an operational bridge read URL/path or bridge capability.
- **PR #229** — X1Scroll authenticated RPC access contract refresh; draft/open. It does not claim accepted live provider access until the credential-backed bounded probe is completed/accepted.

Roberta/Scouts must not treat either open branch as a callable or trusted provider path.

## X1 / XDEX semantic baseline

Accepted distinctions include:

- exact route/config identity may be verified for tested routes;
- route-scoped price impact may be independently reconstructed where accepted reserve/config evidence exists;
- XDEX quote-side price-impact validation uses the accepted integer-rounded quote semantic where required while keeping the continuous constant-product reconstruction as a separate consistency proof;
- quote slippage tolerance/minimum-received semantics remain distinct from expected execution slippage;
- selected 1-minute history timestamp/OHLC semantics have bounded verification/corroboration;
- the pinned XENCAT/native-XNT historical execution model is evidence-bound to its tested scope;
- hidden/router/platform fee attribution remains unproven unless separately established;
- global route optimality, fill quality, route quality, generic execution quality, and universal XDEX execution semantics remain unavailable.

Roberta must preserve these scope limits.

## Solana baseline

Accepted CMIS Solana read-only components include:

- exact-mint identity through canonical RPC;
- SPL Token / Token-2022 handling;
- canonical supply and mint/freeze authority evidence;
- configured Jupiter, Helius, and DEX Screener evidence under their accepted roles;
- deterministic cross-source price/supply checks;
- explicit deployment/operator ownership of the Solana price cross-check tolerance with no hidden CMIS default;
- structural DEX Screener pair validation taking precedence over numerical conflict classification;
- canonical top-20 normalization for `getTokenLargestAccounts`-style evidence while preserving provider-returned cardinality and token-account-only semantics;
- bounded/partial read-only service behavior.

Solana does not inherit X1 capabilities or promotion state.

## Pre-trade baseline

CMIS pre-trade analysis can deterministically evaluate verified trade size against verified liquidity and explicit versioned policy.

A hardened internal route-evidence seam may expose selected exact-route facts only when accepted source, identity, freshness, semantic, unit, proof-basis, and value-shape gates pass.

Current distinctions:

- route-scoped price impact may be usable where exact proof gates pass;
- bounded execution-model fee evidence may be usable only for exact accepted scope;
- quote-side curve behavior is not automatically an executed hidden fee;
- quote slippage tolerance is not expected execution slippage;
- expected execution slippage remains unavailable without its own accepted execution observation contract;
- route quality, fill quality, transaction simulation, and generic execution quality remain unavailable unless separately proven.

The public gateway does not accept arbitrary caller-supplied internal route evidence as a shortcut to verification.

Every current pre-trade result remains:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Phase 11 Verified Intelligence baseline

Accepted read-only foundations include:

- exact top-account concentration;
- numeric concentration changes under compatible scope;
- neutral wallet activity facts;
- sanitized sparse historical intelligence;
- evidence-bound conclusions with content-addressed receipts/proof;
- deterministic explicit-policy concentration-threshold evaluation.

The core Phase 11 primitives remain outside automatic public `supported_services` / Scout reliance. The separately promoted `concentration_change_intelligence/v1` wrapper is the only accepted public/Scout-reliance exception at this checkpoint.

## Post-Phase-12 internal Verified Intelligence foundations

### Descriptive intelligence classification

Derives only the exact concentration-direction label supported by revalidated canonical CMIS evidence. It adds no behavioral, ownership, intent, fraud, manipulation, scam, or risk interpretation.

### Direct wallet-relationship evidence

Records verified observed direct token-transfer interactions between exact chain identities, preserving direction, asset/chain identity, bounded scope, deterministic identity, duplicate protection, and explicit non-ownership semantics.

### Concentration-threshold alert evidence

Reuses the canonical concentration threshold evaluator and binds exact expected chain/asset identity, canonical concentration-change fields, `basis_points` units, GT/GTE comparison semantics, canonical timestamps/freshness, single-observation persistence, and deterministic evidence/alert identities.

All three remain:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

They do **not** establish common ownership, beneficial ownership, whale/insider/bot status, coordinated control, intent, manipulation, fraud/scam, complete graph/history coverage, risk severity, causality, or imminent price movement.

There is no accepted public alert service or Roberta/Scout alert adoption at this checkpoint.

## Roberta Learning System / Pyramid interaction

Roberta now contains accepted Learning System Phases 1-9 and an accepted-but-unimplemented Phase 10 retention specification, plus the Blockchain Reasoning Pyramid training/remediation/source-grounding path.

None of that changes this CMIS baseline.

Specifically:

- a book/whitepaper/source record cannot override fresh CMIS evidence;
- a Pyramid PASS/PARTIAL/FAIL or grader note cannot create a market fact;
- a source-grounded remediation reconstruction cannot promote CMIS/provider trust;
- a Phase 9 `verified_for_learning` result cannot create CMIS truth;
- any future retained lesson remains subordinate to fresh CMIS/provider evidence for freshness-sensitive state;
- human retention approval does not become wallet/execution authority.

## Roberta consumption boundary

Roberta may:

- explain verified facts and provenance;
- explain proof quality separately from risk;
- surface conflicts and insufficient evidence;
- coordinate specialists based on accepted service output;
- use accepted CMIS facts in broader reasoning;
- provide answer-first conversational synthesis;
- request X1 `concentration_change_intelligence/v1` through X1 Scout when the exact capability/evidence-id gates pass.

Roberta must not:

- infer missing provider semantics/units;
- generalize pool/route-specific proof to another scope;
- convert conflict into agreement;
- convert insufficient evidence into a definitive fact;
- recalculate CMIS deterministic comparisons to obtain a preferred answer;
- treat raw provider responses or asserted proof labels as verified on their own;
- turn internal classification, wallet-relationship, or alert foundations into public services;
- broaden the promoted concentration-change service beyond its exact accepted conclusion/scope;
- treat learning/training/memory/policy/human-review state as a replacement for current CMIS evidence;
- treat analysis, proof, PASS, alert state, or human review as authorization for value movement.

## Execution boundary

No accepted baseline authorizes:

- transaction construction as an execution path;
- signing;
- broadcasting;
- custody;
- live trading/swaps;
- bridge value transfer;
- autonomous execution;
- autonomous value movement.

Roberta Controlled Execution remains separately locked/not started.
