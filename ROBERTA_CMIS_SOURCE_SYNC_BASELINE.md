# Roberta ↔ CMIS Source Sync Baseline

Last reconciled: 2026-08-30 (America/New_York)

This file is the compact cross-project synchronization baseline. It is intentionally mirrored in both repositories. Repository-local architecture, capability, roadmap, and status documents remain authoritative for implementation details.

## Product identity invariant

- **ROBERTA — Verified On-Chain Intelligence** is the canonical public-facing product name.
- The former working name **X1 Intelligence Service** is retired and must not be used as the current product name.
- X1 Scout, Solana Scout, and CMIS remain component names beneath Roberta.
- This is a naming change only; the authority, evidence, risk, capability, and execution boundaries below are unchanged.

## Canonical authority path

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

- Roberta owns orchestration, policy coordination, specialist selection, learning-workflow coordination, approval boundaries, and final synthesis.
- Chain Scouts own chain-specific planning and interpretation; they do not manufacture facts.
- CMIS owns deterministic freshness-sensitive verified facts, evidence, Evidence Receipts, Proof Scores, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.
- Providers remain beneath CMIS.
- Fresh accepted CMIS/provider facts override books, static RAG, source-mastery state, Pyramid checkpoints, retained lessons, learned concepts, HXMP/other memory, and conversational live values when freshness matters.
- Missing evidence remains unknown/unavailable and is never converted into zero, false, or a model estimate.
- Proof Score remains separate from risk.
- `pre_trade_check` remains analysis-only and preserves `execution_authorized=false`.
- The `liquidity_scout` namespace may remain as a compatibility implementation detail; it is not a separate authority layer.

## Current CMIS contract baseline

```text
CMIS capability contract = 1.13.0
global existing-service minimum = 1.8.0
concentration_change_intelligence minimum = 1.9.0
all_available history minimum = 1.10.0
x1_asset_identity/v1 minimum = 1.11.0
verified provider-price backfill semantics = 1.12.0
instant_x1_scan/v1 minimum = 1.13.0
```

Accepted milestones carried by that contract line:

- CMIS `1.9.0` introduced the narrow promoted X1 `concentration_change_intelligence/v1` wrapper.
- CMIS `1.10.0` added `historical_compare` modes `all_available` and `all_available_pair`.
- CMIS `1.11.0` added normalized exact-mint X1 identity under `x1_asset_identity/v1`; the exact mint remains the fungible identity root.
- CMIS `1.12.0` permits a narrow verified provider-price backfill for historical price only. It does not prove provider source independence, archive completeness, continuous coverage, historical USD-stable peg behavior, or complete asset lifetime.
- CMIS `1.13.0` adds the promoted X1-only `instant_x1_scan/v1` composition service. It adds no new provider truth path and keeps holder/current-concentration fields fail-closed when their evidence is not verified.

The core Phase 11 `intelligence_foundation` remains read-only/non-promoted as a group. The separately accepted Phase 12 wrapper remains exactly:

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

The CMIS `1.13.0` Instant X1 Scan promotion is exactly:

```text
service = instant_x1_scan
service_contract_version = instant_x1_scan/v1
chain = x1
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
execution_authorized = false
```

It is composition-only over accepted CMIS evidence and local CMIS history. Roberta/X1 Scout must still adopt this service explicitly before it becomes a Roberta-dispatchable capability; upstream CMIS promotion alone does not create a Roberta routing path.

## Oracle V2 provider-gap status

Oracle V2 has advanced beyond repository-only candidate research, but it is still not a promoted CMIS current-price source.

Accepted/read-only evidence on CMIS `main` now establishes:

- the declared X1 program/state contract shape is live and structurally verified;
- exact program/state ownership, PDA/layout, six-asset × five-relay shape, decimals, and stored Oracle key were verified through X1 RPC;
- timestamp-unit semantics are promoted only under the accepted evidence-bound policy: raw batch timestamps may be interpreted as Unix milliseconds;
- current slot ages can be calculated deterministically from the verified timestamp unit;
- the explicit freshness policy is selected/applied with `max_age_ms=60000`, `max_future_skew_ms=5000`, and `minimum_eligible_slots=3`;
- the latest live run classified all 30 observed relay slots stale, so no current-price median was eligible.

Current freshness-governance state:

```text
freshness_policy_complete = true
freshness_policy_applied = true
freshness_verified = true
current_price_use_authorized = false
source_independence_verified = false
price_correctness_verified = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

No current slot is price-eligible in the latest live evidence because all observed relay slots were stale. Five relay slots remain same-system redundancy, not five independent market sources. The next Oracle gate resumes only when new policy-eligible live slots appear.

## Public/private runtime boundary

Both public repositories completed the protected-runtime split and Phase 6 historical cleanup on 2026-08-29. The public `roberta-langgraph` and `cmis` repositories now carry the public shell, contracts, documentation, and fail-closed integration tests; protected runtime implementation is supplied by the corresponding private-core packages at deployment/test assembly time.

The steady-state rule is fail-closed: missing or incompatible private runtime must not trigger a public fallback. The authority path remains `User -> Roberta -> Chain Scout -> CMIS -> Chain Provider`, and the split changes code placement rather than trust or execution authority.

## Roberta Learning Plane baseline

Roberta Learning System Phases 1-10 and the autonomous source-grounded Learning Plane controller are accepted on Roberta `main`.

The controller may, after explicit static-source selection:

- bind immutable source provenance;
- create/resume a frozen source-mastery plan;
- generate and independently verify source-grounded targets;
- build and atomically publish deterministic curriculum banks;
- run canonical stage exams;
- perform verified remediation/retention/transfer;
- preserve immutable failures and completed-stage prefixes;
- reuse only curriculum-scoped verified learned concepts;
- resume from durable state;
- run the final source capstone.

Learning remains a separate authority plane. It cannot self-authorize CMIS contracts, provider trust, Scout promotion, fresh chain truth, governance changes, wallet permissions, transaction construction/signing/broadcasting, trading, custody, bridge transfer, or Controlled Execution.

For *Mastering Blockchain, Fourth Edition*, accepted prebuilt repository banks remain through Stage 8 / Market Structure. Runtime-generated later-stage banks are valid only through the autonomous controller's exact provenance/verification gates; bank existence is not mastery.

## Internal non-promoted CMIS foundations

Accepted on CMIS `main` but not Scout-callable by implication:

- deterministic descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership/non-beneficial-owner semantics;
- concentration-threshold alert evidence.

No broader public intelligence/alert promotion is accepted by implication.

## Provider-gap state

The X1 provider-gap track remains read-only/fail-closed. Warp Bridge and FortiBlox research branches are closed as not currently verifiable/candidate research. X1Scroll PR #229 is closed and X1Scroll is removed from CMIS integration scope because no repository API key was available for the required credential-backed probe; no provider request was made and no X1Scroll capability is accepted on `main`. A future secondary provider requires a new explicit verification gate.

## Execution boundary

Controlled Execution remains locked/not started. No Learning Plane result, source material, retained lesson, learned concept, CMIS result, Scout report, Evidence Receipt, Proof Score, risk result, alert, pre-trade `PASS`, policy decision, or human approval authorizes transaction construction as an execution path, signing, broadcasting, custody, trading, bridge transfer, or autonomous value movement.

## Core sync rule

**Roberta may learn from static evidence and CMIS may verify changing chain facts, but neither learning nor analysis self-promotes into a new authority boundary. Fresh accepted CMIS/provider evidence wins for freshness-sensitive state, and every public-service, operational-trust, wallet, or execution promotion remains separately gated.**
