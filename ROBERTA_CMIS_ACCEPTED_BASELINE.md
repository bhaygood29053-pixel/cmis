# Roberta ↔ CMIS Accepted Baseline

Last reconciled: 2026-09-05 (America/New_York)

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

Roberta Learning System sources, autonomous source-mastery plans, Pyramid training/learned-concept state, retained lessons, LangGraph checkpoints, HXMP memory, policy state, and human review do **not** override CMIS for freshness-sensitive market/blockchain facts.

## Current contract baseline

```text
schema_version = 1
global existing-service minimum = 1.8.0
current CMIS contract = 1.18.0
```

Accepted manifest semantics include:

- explicit chain/service eligibility;
- Evidence Receipt schema `1`;
- Proof Score schema `1`;
- risk/proof separation;
- missing-evidence-is-unknown semantics;
- X1 `historical_compare` supports bounded `window`, `all_available`, and `all_available_pair` modes; all-available history is explicitly scoped to verified CMIS observations and does not imply complete asset lifetime;
- CMIS `1.11.0+` supports exact-mint X1 identity normalization under `x1_asset_identity/v1`, with the mint preserved as the canonical fungible identity root and Metaplex/XDEX descriptors kept separately sourced;
- CMIS `1.12.0+` may extend verified historical **price only** through the accepted provider-backfill contract while preserving source-independence, archive-completeness, continuity, historical stable-quote, and full-lifetime limitations;
- CMIS `1.13.0` adds X1-only `instant_x1_scan/v1` as a bounded read-only composition service for ROBERTA; its local-history path does not trigger provider backfill or RPC coverage expansion, unverified holder/concentration facts stay unknown, Proof Score remains separate from risk, and execution remains unauthorized;
- Oracle V2's exact deployed X1 program/state shape and Unix-ms timestamp semantics are verified under bounded evidence contracts; the explicit freshness policy is selected/applied and freshness evaluation is verified, but the latest live slots are all stale, so current-price use, source independence, price correctness, CMIS-provider promotion, public-service promotion, and Scout reliance remain false;
- read-only Phase 11 `intelligence_foundation` with public-service/Scout-reliance promotion false;
- one separately promoted read-only X1 intelligence service: `concentration_change_intelligence/v1`.

Accepted internal/non-promoted deterministic foundations also include descriptive concentration-direction classification, direct wallet-relationship evidence with explicit non-ownership semantics, and concentration-threshold alert evidence.

None of those internal foundations creates a capability-manifest service or Scout dispatch authority.

## September 3 cross-chain checkpoint

The accepted baseline now also includes the following bounded CMIS cross-chain
evidence stack:

- exact Warp config semantics under `warp_config/exact-mint-pair/v1`;
- deterministic bridge-flow calculation under `bridge_flow_intelligence/v1`;
- canonical settled Warp events through exact on-chain
  `warp_onchain_transfer_history/v1` OutgoingMsg/IncomingMsg pairing;
- connected wallet-history endpoint/response semantics as corroboration only;
- exact current message-universe counter/account closure;
- bounded 60-day lifecycle-retention / requested-window coverage through #441;
- verified current bridged-supply closure;
- completed #409 current/prior 24h, 7d, and 30d bridge-flow integration.

Those accepted foundations remain bounded to their exact route, evidence,
coverage, and fact-time scopes. They do **not** by themselves create a public
CMIS bridge service, Scout reliance, an adoption claim, a risk conclusion, or
execution authority.

Current promotion boundary:

```text
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

The Warp evidence sequence has advanced: #441 bounded lifecycle retention and #409 Bridge Supply + Flow Intelligence are accepted. PR #467 accepted the deterministic #410 utilization foundation and verified wSOL.X XDEX program-family pool-universe state. PR #469 is the remaining final #410 evidence slice; its current exact-head 24h activity-window and comparable-value workflows are green, but it remains unmerged. ROBERTA #314 therefore remains blocked until #469 is merged/reconciled and CMIS separately accepts the required public-service / Scout-reliance promotion.

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

Current provider-gap work remains non-promotional. Issue #30 remains open. Warp route/config, retention, supply, and #409 flow evidence are now accepted under their bounded contracts; #410 final evidence remains gated by PR #469. A bounded X1Scroll archival transaction provider foundation is accepted from PR #457, while its broader qualification remains separately gated. Web Discovery v1-v4 is accepted internally through PR #478 but remains `DISCOVERED`, non-promoted, and non-authorizing.

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

## Roberta Learning System / autonomous Learning Plane interaction

Roberta Learning System Phases 1-10 are accepted on Roberta `main`. Hardened Phase 10 verified retention is implemented as a narrow deterministic provider-neutral/in-memory retention layer, and an exact active retained lesson may be classified as `verified_learned_knowledge` with full lineage. That classification explicitly does not authorize source truth, live state, CMIS/provider trust, governance mutation, wallet activity, operational trust, or execution.

Roberta PR #228 merged on 2026-08-26 and accepted the first end-to-end autonomous source-grounded Learning Plane controller. After explicit static-source selection, the accepted controller can bind immutable source provenance, create/resume a frozen source-mastery plan, generate and independently verify source-grounded learning targets, publish deterministic curriculum banks, run canonical exams, remediate failures, perform closed-book retention and transfer checks, promote only curriculum-scoped verified concepts, preserve immutable failure evidence, resume safely, and run a final source capstone.

For *Mastering Blockchain, Fourth Edition*, accepted prebuilt exercise-bank construction reaches Stage 8 / Market Structure. Stages 9-14 are not yet separately accepted prebuilt repository banks, although the autonomous controller may generate missing banks at runtime under its validation contract. Bank availability is not mastery; mastery requires every frozen required stage and final capstone to pass in the authoritative source-mastery ledger.

None of that changes CMIS authority.

Specifically:

- a book/whitepaper/source record cannot override fresh CMIS evidence;
- an autonomous source-mastery plan, generated bank, stage PASS, or capstone PASS cannot create a market fact;
- a Pyramid PASS/PARTIAL/FAIL, grader note, expected answer, practice result, retained lesson, or learned concept cannot create CMIS truth;
- source-grounded reconstruction/practice cannot promote provider trust;
- curriculum-scoped learned concepts and `verified_learned_knowledge` are static learning state, not current market/blockchain state;
- Phase 9 `verified_for_learning` cannot create CMIS truth;
- retained lessons remain subordinate to fresh CMIS/provider evidence for freshness-sensitive state;
- learning/retention approval never becomes wallet/execution authority;
- the Learning Plane cannot self-modify CMIS contracts, provider authority, Scout-reliance promotion, prompts/tools/policies that establish runtime authority, or Controlled Execution permissions.

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
- treat source plans, books, Pyramid learned concepts, retained lessons, memory, policy, or human review as replacements for current CMIS evidence;
- treat analysis/proof/PASS/alert/learning/human-review state as authorization for value movement.

## Execution boundary

No accepted baseline authorizes transaction construction as an execution path, signing, broadcasting, custody, live trading/swaps, bridge value transfer, autonomous execution, or autonomous value movement.

Roberta Controlled Execution remains separately locked/not started.
