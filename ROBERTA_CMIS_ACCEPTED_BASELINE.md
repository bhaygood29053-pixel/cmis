# Roberta ↔ CMIS Accepted Baseline

Last reconciled: 2026-08-25 (America/New_York)

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

Roberta coordinates and explains. Chain Scouts investigate/interpret within exact chain scope. CMIS owns deterministic freshness-sensitive facts, evidence, proof quality, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.

Roberta Learning System sources, source-mastery plans, Pyramid training/learned-concept state, LangGraph checkpoints, HXMP memory, policy state, and human review do **not** override CMIS for freshness-sensitive market/blockchain facts.

## Current contract baseline

```text
schema_version = 1
global existing-service minimum = 1.8.0
current CMIS contract = 1.9.0
```

Accepted manifest semantics include:

- explicit chain/service eligibility;
- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- risk/proof separation;
- missing-evidence-is-unknown semantics;
- read-only Phase 11 `intelligence_foundation` with public-service/Scout-reliance promotion false;
- one separately promoted read-only X1 intelligence service: `concentration_change_intelligence/v1`.

Accepted internal/non-promoted deterministic foundations also include descriptive concentration-direction classification, direct wallet-relationship evidence with explicit non-ownership semantics, and concentration-threshold alert evidence.

None of those internal foundations creates a capability-manifest service or Scout dispatch authority.

## First promoted Verified Intelligence service — bounded X1 only

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
execution_authorized = false
```

CMIS resolves/revalidates canonical CMIS-owned evidence internally. Caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, behavioral labels, or replacement verification state are not trust shortcuts.

The service does not establish unique-holder totals, beneficial ownership, behavioral/intent labels, risk from Proof Score, or execution authority.

Solana remains unavailable/non-promoted for this service until a separate accepted contract says otherwise.

Roberta has adopted this exact service through X1 Scout with fail-closed CMIS 1.9 capability checks. That adoption does not broaden CMIS scope.

## Evidence semantics

Accepted CMIS meanings include:

- `AGREEMENT` — comparable same-fact observations agree under the applicable verifier;
- `CONFLICT` — accepted comparison evidence disagrees; do not average/choose a preferred value unless a fact-specific contract permits it;
- `INSUFFICIENT_EVIDENCE` — required comparable evidence is missing/invalid; do not reinterpret it as a negative fact;
- explicit proof/data-quality reasons and unresolved categories;
- Evidence Receipts preserving source/provenance, scope, freshness, disagreements, limitations, and unresolved fields;
- Proof Scores separate from market risk.

Source independence is explicit fact-specific evidence. Distinct provider names, URLs, or brands do not prove independence. Same-fact agreement and source independence remain separate dimensions.

## Accepted X1 / XDEX boundary

Where exact contracts permit, accepted X1 building blocks include identity/supply/authority evidence, pool/vault/mint identity, read-only provider transports, reserve semantic binding, provider/RPC comparison, deterministic XDEX trade verification, persisted evidence, bounded history/activity, transaction→pool membership proof, and selected exact-route pre-trade evidence.

Scope remains explicit. Program-, pool-, route-, provider-, token-account-, or sample-scoped evidence is not silently widened to asset/global truth.

Current provider-gap work remains non-promotional. Issue #30 is still open; draft PR #242 (Warp Bridge provenance) and draft PR #229 (X1Scroll authenticated RPC access) are not accepted provider capability by virtue of existing as branches.

## Solana boundary

Accepted read-only Solana components include exact-mint identity, SPL Token/Token-2022 handling, canonical supply/mint/freeze authority evidence, configured Jupiter/Helius/DEX Screener roles, deterministic cross-source checks, explicit operator-owned price tolerance, structural pair validation, canonical top-20 largest-token-account normalization, provenance-safe history, and bounded/partial service behavior.

Solana does not inherit X1 capability or promotion state.

## Pre-trade boundary

CMIS may evaluate verified trade size against verified liquidity and explicit versioned policy, plus selected route-scoped facts only when exact source/identity/freshness/semantic/unit/proof gates pass.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade. Quote tolerance is not expected execution slippage. Missing route quality, fill quality, simulation, generic execution quality, or unsupported fee semantics remain unavailable.

## Internal Verified Intelligence boundary

Accepted internal/read-only/non-promoted foundations include:

- exact top-account concentration and compatible changes;
- neutral wallet-activity facts;
- sanitized sparse historical intelligence;
- evidence-bound conclusions;
- descriptive concentration-direction classification;
- direct wallet-relationship evidence with non-ownership semantics;
- concentration-threshold alert evidence.

They remain equivalent to:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

They do not establish common/beneficial ownership, whale/insider/bot status, intent, manipulation, fraud/scam, complete graph coverage, risk severity, causality, or imminent price movement.

## Roberta Learning System / source-mastery / Pyramid interaction

Roberta now has accepted Learning System Phases 1-9, an accepted-but-unimplemented Phase 10 general retention specification, and a source-specific Pyramid mastery system.

The Pyramid can:

- bind a frozen source-specific plan to training progress;
- use source-grounded exercise banks and provenance-scoped retrieval;
- run 300-question canonical source stages while preserving historical 1,000-question audit results;
- perform source-grounded remediation and supplemental practice;
- require closed-book retention for critical-origin learning;
- persist narrowly curriculum-scoped learned concepts after exact Pyramid verification gates.

None of that changes CMIS authority.

Specifically:

- a book/whitepaper/source record cannot override fresh CMIS evidence;
- a source-mastery plan or stage PASS cannot create a market fact;
- a Pyramid PASS/PARTIAL/FAIL, grader note, expected answer, practice result, or learned concept cannot create CMIS truth;
- source-grounded reconstruction/practice cannot promote provider trust;
- curriculum-scoped learned concepts are static training aids, not current market/blockchain state;
- Phase 9 `verified_for_learning` cannot create CMIS truth;
- any future general retained lesson remains subordinate to fresh CMIS/provider evidence for freshness-sensitive state;
- learning/retention approval never becomes wallet/execution authority.

## Roberta consumption boundary

Roberta may explain accepted CMIS facts/provenance, distinguish proof quality from risk, surface conflict/insufficiency, coordinate specialists, and use accepted CMIS outputs in broader reasoning.

Roberta must not:

- infer missing provider semantics/units;
- generalize pool/route proof to a broader scope;
- convert conflict into agreement;
- convert insufficient evidence into a definitive fact;
- recalculate CMIS deterministic truth/proof to obtain a preferred answer;
- treat raw provider responses as verified on their own;
- turn internal CMIS foundations into public services;
- broaden `concentration_change_intelligence/v1` beyond its accepted X1 scope;
- treat source plans, books, Pyramid learned concepts, memory, policy, or human review as replacements for current CMIS evidence;
- treat analysis/proof/PASS/alert/human-review state as authorization for value movement.

## Execution boundary

No accepted baseline authorizes transaction construction as an execution path, signing, broadcasting, custody, live trading/swaps, bridge value transfer, autonomous execution, or autonomous value movement.

Roberta Controlled Execution remains separately locked/not started.
