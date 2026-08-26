# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-08-26 (America/New_York)

Merge state verified 2026-08-26:

- paired Roberta PR #226 / CMIS PR #269 architecture/source-of-truth reconciliation is merged on both `main` branches;
- Roberta PR #228 autonomous source-grounded Learning Plane is merged and accepted on Roberta `main`;
- Roberta post-merge source/roadmap synchronization PR #231 is merged on Roberta `main`.

This file is the compact cross-project synchronization baseline for source-of-truth documentation. It does not replace `ROBERTA_INTEGRATION_CONTRACT.md`, `ROBERTA_CMIS_ACCEPTED_BASELINE.md`, or `docs/CMIS_PRODUCT_ROADMAP.md`.

## Canonical authority path

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

- Roberta owns orchestration, policy coordination, specialist selection, learning-workflow coordination, and final synthesis.
- Chain Scouts own chain-specific planning and interpretation; they do not manufacture facts.
- CMIS owns deterministic freshness-sensitive verified facts, evidence, Proof Scores, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.
- Providers remain beneath CMIS.
- Fresh accepted CMIS/provider facts override remembered, checkpointed, RAG/source-mastery, retained, Pyramid, or conversational live values.
- Missing evidence remains unknown/unavailable and is never converted into zero, false, or an LLM estimate.
- Proof Score remains separate from risk.
- `pre_trade_check` remains analysis-only and preserves `execution_authorized=false`.
- The working `liquidity_scout` namespace may remain during incremental migration as a compatibility identifier only.

## Current CMIS/Roberta capability baseline

```text
CMIS capability contract = 1.9.0
Phase 11 intelligence_foundation public_service_promoted = false
Phase 11 intelligence_foundation scout_reliance_promoted = false
```

The separately accepted Phase 12 wrapper is exactly:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

Solana remains unavailable/non-promoted for this service.

## Roberta Learning Plane baseline

Roberta Learning System Phases 1-10 are accepted on Roberta `main`. Phase 10 verified retention is implemented under its narrow deterministic retention contract. Exact active retained lessons may be classified as `verified_learned_knowledge`, but that classification keeps operational/source/live-state/CMIS-provider/governance/wallet/execution authority false.

The accepted autonomous Learning Plane can, after explicit static-source selection:

- bind immutable original/transcript/page/chapter-map provenance;
- create or resume a frozen source-mastery plan;
- generate source-grounded targets and independently verify support;
- build and atomically publish deterministic curriculum banks;
- run canonical source-stage examinations;
- diagnose/remediate failures from the selected source;
- require separate closed-book retention and transfer checks before curriculum-scoped promotion;
- preserve immutable failed attempts and completed-stage prefixes;
- resume from durable state/checkpoints/locks;
- run a final source capstone.

For *Mastering Blockchain, Fourth Edition*, accepted prebuilt exercise banks are present through Stage 8 / Market Structure. Stages 9-14 are not yet separately accepted prebuilt repository banks. Bank availability is not mastery, and the source is not mastered until every required frozen stage and final capstone pass in the authoritative ledger.

Learning remains a separate authority plane. It cannot self-authorize CMIS contracts, provider trust, Scout promotion, fresh chain truth, wallet permissions, transaction construction/signing/broadcasting, trading, custody, bridge transfer, or Controlled Execution.

## Internal non-promoted CMIS foundations

Accepted on CMIS `main` and safe for documentation/source synchronization, but not Scout-callable by implication:

- deterministic descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership/non-beneficial-owner semantics;
- concentration-threshold alert evidence.

All remain internal/read-only/non-promoted and do not create public-service, Scout-reliance, behavioral/ownership, risk, or execution authority.

## Provider-gap state

X1 provider-gap Issue #30 remains open under read-only/fail-closed contracts. Current open research branches include:

- PR #242 — Warp Bridge exact provenance/origin binding;
- PR #229 — bounded authenticated X1Scroll `getHealth` / `getSlot` access classification;
- PR #227 — FortiBlox provider-contract research.

None is accepted provider capability merely because the branch exists or tests pass. Exact evidence/contract/review/merge gates remain required.

## Current promotion state

There is currently **no accepted next public intelligence/alert service, Scout-reliance promotion, or broader Verified Intelligence promotion**. Any future promotion requires a separate CMIS contract/roadmap acceptance gate and a separate Roberta/Scout adoption-readiness gate.

## Execution boundary

Roberta Controlled Execution remains locked/not started. No current source material, autonomous learning state, retained lesson, Pyramid state, CMIS result, Scout report, Proof Score, risk result, alert state, pre-trade `PASS`, policy decision, or human approval authorizes transaction construction as an execution path, signing, broadcasting, custody, trading, bridge transfer, or autonomous value movement.
