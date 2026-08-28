# CMIS

**Cross-Chain Market Intelligence Service**

CMIS is the deterministic blockchain-intelligence backend used by chain-specific Scouts. X1 Scout and Solana Scout call CMIS for freshness-sensitive market facts, tokenomics, verification evidence, proof quality, historical intelligence, deterministic risk, and bounded pre-trade analysis. Their reports flow back to Roberta, which owns coordination, policy, reasoning, learning-workflow integration, and the final user-facing response.

## Product identity

**Roberta** is the canonical public-facing product name. **CMIS** remains the deterministic backend/repository identity and is not being renamed. The former working product name **X1 Intelligence Service** is retired. X1 Scout and Solana Scout remain specialist component names beneath Roberta. This naming decision does not change CMIS authority, contracts, evidence semantics, or execution boundaries.

Canonical product naming rules live in `bhaygood29053-pixel/roberta-langgraph/docs/PRODUCT_IDENTITY.md`.

The repository was originally created as **Liquidity Scout**. The canonical project identity is now **CMIS** at `bhaygood29053-pixel/cmis`.

> Compatibility note: the working Python package namespace is still `liquidity_scout`. That namespace remains an implementation compatibility detail and does not create a second authority layer.

## Canonical architecture

```text
User / transport
      ↓
Roberta — Oracle / Coordinator / user-facing voice
      ↓
Chain Scouts
  ├── X1 Scout
  └── Solana Scout
      ↓
CMIS — deterministic intelligence service
      ↓
Chain Providers
  ├── X1 / XDEX
  └── Solana
```

Authority flows downward:

```text
Roberta -> Chain Scout -> CMIS -> Chain Provider
```

Verified information flows upward:

```text
Chain Provider -> CMIS -> Chain Scout -> Roberta
```

CMIS owns deterministic facts and evidence. Chain Scouts own chain-specific investigation/interpretation. Roberta owns user intent, policy, coordination, learning-workflow coordination, and final synthesis. Neither Roberta nor a Scout should recreate CMIS/provider calculations to manufacture a second market fact.

## Current roadmap position — reconciled 2026-08-28

Accepted on `main`:

- **CMIS Phase 10 — Solana read-only provider foundation:** complete.
- **Evidence Receipts + Proof Score:** complete.
- **X1 evidence-capability boundary:** complete and fail-closed.
- **Deterministic pre-trade trade-size analysis:** complete.
- **CMIS Phase 11 — read-only Verified Intelligence foundation:** complete.
- **CMIS Phase 12 — first narrow X1 public-service / Scout-reliance promotion:** complete for `concentration_change_intelligence/v1`.
- **Deterministic descriptive intelligence classification:** complete, internal/read-only/non-promoted.
- **Deterministic direct wallet-relationship evidence:** complete, internal/read-only/non-promoted, explicit non-ownership semantics.
- **Deterministic concentration-threshold alert evidence (#263/#264):** complete, internal/read-only/non-promoted.
- **Repository-authoritative deterministic engineering workflow / three-axis review:** adopted.
- **CMIS capability contract:** `1.12.0`.
- **Oracle V2 read-only evidence:** deployed contract shape and Unix-ms timestamp semantics are verified; the explicit freshness policy is selected and applied, while current-price authority remains unpromoted because the latest live slots are stale.
- **Roberta adoption/readiness of the promoted X1 concentration-change service:** complete through X1 Scout.
- **Paired Roberta PR #226 / CMIS PR #269 source-of-truth reconciliation:** merged on both projects.
- **Roberta autonomous Learning Plane dependency:** accepted on Roberta `main` via PR #228; its post-merge source/roadmap state is synchronized through Roberta PR #231.

Not accepted/promoted:

- no public alert service;
- no Scout-reliance promotion for the internal classification/relationship/alert foundations;
- no Solana promotion of `concentration_change_intelligence/v1`;
- no behavioral/ownership/intent/fraud/manipulation inference from the internal foundations;
- no Ethereum provider milestone without a separate accepted gate;
- no Controlled Execution or value movement.

### Strategic product focus — 2026-08-28

CMIS now prioritizes the verified X1 services needed for Roberta's flagship product: Instant X1 Scan fields, fresh validation of the documented X1.Ninja developer API as a candidate provider, explicit holder/wallet intelligence promotion, an immutable Discovery Ledger, Early Warning service contracts, deterministic Compare support, bounded X1 ecosystem/network brief inputs, and a later developer intelligence API. Solana remains maintained for accepted read-only capability and portability testing, but Solana product expansion and release work are deferred to a future phase. This is a roadmap reprioritization only and does not promote internal services, verify a new provider, change the capability contract, or authorize execution.


The authoritative roadmap is [`docs/CMIS_PRODUCT_ROADMAP.md`](./docs/CMIS_PRODUCT_ROADMAP.md). The repository-authoritative engineering process is [`docs/CMIS_ENGINEERING_WORKFLOW.md`](./docs/CMIS_ENGINEERING_WORKFLOW.md). The accepted Roberta-facing trust baseline is [`ROBERTA_CMIS_ACCEPTED_BASELINE.md`](./ROBERTA_CMIS_ACCEPTED_BASELINE.md). The compact paired cross-project baseline is [`ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md`](./ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md). The current dated status snapshot is [`docs/PROJECT_STATUS_2026-08-27.md`](./docs/PROJECT_STATUS_2026-08-27.md).

## Active provider-gap work — not accepted capability

Issue #30 remains the parallel read-only/fail-closed X1 provider-gap track.

Current provider-gap state:

- **X1Scroll — removed from CMIS integration scope.** PR #229 is closed. The credential-backed verification workflow failed at the missing `X1SCROLL_API_KEY` repository-secret gate before any provider request was sent. No X1Scroll provider module or live workflow exists on `main`, and X1Scroll is no longer an active provider candidate. Reconsideration requires a new explicit verification issue with reproducible access evidence.
- **PR #242 — Warp Bridge proof-origin binding:** closed as not currently verifiable because no exact X1-owned machine-readable read contract was established. No guessed bridge endpoint is accepted.
- **PR #227 — FortiBlox provider contract research:** closed/archive candidate research. Exact provider-owned Explorer/Nexus endpoint and response contracts remain unverified; no FortiBlox adapter is accepted.
- **Issue #272 — Oracle V2 read-only X1 price evidence:** structural identity/layout and Unix-ms timestamp semantics are verified, and the explicit current-price freshness policy is now selected/applied. The latest live policy run classified all 30 relay slots stale, so current price use, price correctness, source independence, CMIS-provider promotion, public-service promotion, and Scout reliance remain false. Relay count is not independent-source count.
- **Issue #301 — self-hosted X1 read-only node history/streaming redundancy:** deterministic contract/probes remain available on `main` via PR #302, but live self-hosted deployment verification is deferred because the selected production path uses the Official X1 RPC. No RPC redundancy or independent market-source claim is inferred.

Closed research branches and failed verification attempts do not create provider capability on `main`.

Other current X1 provider-gap observations remain non-promotional:

- the tested X1.Ninja SSE credential returned HTTP 403 / access denied;
- **Issue #304 — holder semantics correction: complete via PR #305.** X1.Ninja holder-looking values, official X1 RPC token-account counts, and unique token-account-authority counts remain distinct evidence classes; raw provider `holders` values do not become verified asset-wide holder counts without counted-entity and coverage proof;
- those observations do not establish holder totals, wallet identity, beneficial ownership, provider completeness, or stream semantics;
- Warp Bridge machine-readable operational state remains unavailable until an exact provenance-approved read contract is accepted.

Current Solana field-maturity work:
- **Issue #306 — observed-pair liquidity/volume aggregation: complete via PR #307.** CMIS deterministically totals only eligible unique DEX Screener pairs returned for the verified mint. The result remains explicitly observed-pair scoped; pair-universe completeness, Solana-wide liquidity/volume verification, and market-source independence remain false.
- **Issue #308 — Solana market observation freshness semantics: complete via PR #310.** Jupiter `blockId` is accepted as the provider-documented Solana block reference for the computed price and may be mapped through canonical `getBlockTime`; CMIS collection time remains separate. Jupiter token `createdAt` and DEX Screener `pairCreatedAt` are not price-observation timestamps.
- **Issue #311 — Solana Jupiter current-price freshness policy: complete via PR #312.** CMIS applies an explicit 60-second max-age and 5-second future-skew operator policy to verified Jupiter block-time evidence.
- **Issue #313 — timestamped secondary Solana price evidence: complete via PR #314.** CMIS reads one exact USDC/USD Pyth Core sponsored push-feed fixture through canonical Solana RPC, verifies account/feed/full-verification/price/exponent/confidence/`publish_time`, applies a separate Pyth 60-second/5-second source policy, and can compare Jupiter/Pyth numerical prices plus exact fact-time delta.
- **Issue #315 — Jupiter–Pyth cross-source time identity: implemented in PR #316.** CMIS defines a separate five-second same-time operator window. Both source-specific freshness gates must be FRESH; a fact-time delta <=5 seconds may set `cross_source_time_identity_verified=true`. Source independence, price-construction equivalence, current-price promotion, and execution authority remain false.
- **Issue #317 — Jupiter/Pyth independence and methodology compatibility: deferred with the Solana product track.** The issue remains useful future evidence work, but it is not the active implementation priority while CMIS productizes X1 first.

## Roberta-facing service surface

The versioned CMIS service contract includes, depending on chain capability state:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`
- `concentration_change_intelligence` — bounded X1-only promoted service under CMIS `1.9.0`

The live capability manifest is authoritative:

```text
GET /v1/cmis/capabilities
```

The current accepted X1 normalized-identity contract is `x1_asset_identity/v1`, introduced in CMIS 1.11.0 and retained by the current 1.12.0 contract. For an externally reachable Roberta readiness deployment, keep the CMIS Python process on loopback and use the hardened HTTPS reverse-proxy profile in [`docs/CMIS_PUBLIC_HTTPS.md`](./docs/CMIS_PUBLIC_HTTPS.md).

Every chain/service combination is classified explicitly. A capability available on X1 is never assumed to exist on Solana, and vice versa.

## All-available verified history — CMIS 1.10.0

The existing `historical_compare` service now supports X1 `window`, `all_available`, and `all_available_pair` modes. The runtime CMIS gateway accumulates bounded verified market observations for price, liquidity, 24h volume, 24h transactions, and holders with duplicate throttling. Full-history output reports exact stored coverage bounds, observation counts, sampled extrema/change, sampled price drawdown, and observed gaps.

“Entire history” means **all verified history currently available to CMIS**, not automatically the asset's complete lifetime. Continuous coverage, asset inception, and external OHLCV/archive completeness remain unverified unless separately proven. Pair comparisons use only the overlapping verified window and fail closed when aligned anchors are unavailable.

## First promoted Verified Intelligence service

CMIS `1.9.0` promotes exactly one narrow X1 intelligence wrapper:

```text
service = concentration_change_intelligence
service_contract = concentration_change_intelligence/v1
chain = x1
state = bounded
callable = true
read_only = true
public_service_promoted = true
scout_reliance_promoted = true
accepted_conclusion_type = top_account_concentration_change
promotion_scope = cmis_owned_top_account_concentration_change_evidence_by_id
execution_authorized = false
```

Solana remains unavailable/non-callable/non-promoted for this service.

The wrapper resolves canonical CMIS-owned intelligence evidence internally and rejects caller-supplied intelligence bundles, Evidence Receipts, Proof Scores, provider assertions, behavioral labels, or replacement verification state as trust shortcuts.

The service does not establish unique-holder totals or beneficial owners. Optional threshold output is deterministic policy evaluation, not a risk score. Proof Score is not risk.

## Phase 11 / post-Phase-12 internal foundations

Accepted read-only foundations include:

- exact top-account concentration observations and compatible numeric changes;
- neutral verified wallet-activity facts;
- sanitized sparse historical intelligence and compatible-series comparison;
- evidence-bound conclusions with content-addressed receipts/proof;
- deterministic descriptive concentration-direction classification;
- deterministic direct wallet-relationship evidence for exact observed transfers with explicit non-ownership semantics;
- deterministic concentration-threshold alert evidence with exact subject/unit/freshness/comparator/persistence/identity rules.

The internal classification, relationship, and alert foundations remain equivalent to:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

CMIS does **not** infer insider, whale, bot, accumulator, distributor, market maker, manipulator, scam, beneficial owner, common owner, intent, causality, risk severity, or imminent price movement from those foundations.

## Evidence semantics

Core trust rules:

1. Provider-reported information remains provider-reported until accepted verification exists.
2. Missing evidence remains unknown/unavailable; it is never converted into zero or false.
3. Source independence is explicit evidence, not inferred from different provider labels.
4. Same-fact agreement and source independence are separate proof dimensions.
5. Evidence Receipt / Proof Score integrity is deterministic and content/provenance-bound.
6. Proof Score remains separate from market risk.
7. Pool/route/provider/token-account/sample scope is not silently widened to asset/global scope.
8. Chain provenance is preserved.
9. Inference requires a separately accepted contract.
10. No execution authority is created by PASS/WARN/BLOCK, alert state, Proof Score, learning state, or human review.

## X1 / XDEX foundation

Accepted X1/XDEX capabilities include, where exact evidence contracts permit:

- asset and pool discovery;
- price, liquidity, volume, and ranking support;
- RPC supply and authority verification;
- deterministic XDEX trade verification;
- provider-vs-chain reconciliation;
- bounded verified activity/history;
- tokenomics and burn evidence;
- Evidence Receipts and Proof Scores;
- deterministic risk analysis;
- versioned trade-size analysis against verified liquidity;
- selected exact-route price-impact/fee evidence where the specific proof contract passes;
- fail-closed quote/history semantic gates.

Program-, pool-, route-, provider-, token-account-, or sample-scoped evidence remains distinct from asset-wide/global truth.

## Solana read-only foundation

Solana is implemented beneath the same CMIS architecture rather than as a separate intelligence stack. Accepted components include:

- exact-mint identity through canonical Solana RPC;
- SPL Token and Token-2022 program identity handling;
- canonical token supply and mint/freeze authority evidence;
- Jupiter read-only price evidence when configured;
- Helius indexed evidence when configured;
- DEX Screener pair-scoped market evidence;
- deterministic cross-source price and supply checks;
- canonical top-20 normalization for largest-token-account results while preserving provider-returned cardinality;
- provenance-safe observation history;
- bounded/partial read-only CMIS services.

Solana production composition remains environment-controlled and fail-closed. Solana does not inherit X1 capability promotion.

## Pre-trade analysis

`pre_trade_check` remains analysis only.

Accepted behavior may evaluate requested notional against verified liquidity and explicit versioned trade-size policy and may expose selected route-scoped facts only when exact source/identity/freshness/semantic/unit/proof gates pass.

Quote tolerance is not expected execution slippage. Missing route quality, fill quality, generic execution quality, transaction simulation, bridge dependency, or other unsupported evidence remains unavailable.

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Roberta dependency/status context

Roberta Learning System Phases 1-10 are accepted on Roberta `main`. Hardened Phase 10 verified retention is implemented, and exact active retained lessons can be classified as `verified_learned_knowledge` while all operational/source/live-state/CMIS-provider/governance/wallet/execution authority remains false.

Roberta PR #228 merged on 2026-08-26 and accepted the first end-to-end autonomous source-grounded Learning Plane controller. After explicit static-source selection, Roberta can bind immutable source provenance, create or resume a frozen source-mastery plan, generate and independently verify learning targets, publish deterministic curriculum banks, run canonical exams, remediate source-grounded weaknesses, verify closed-book retention and transfer, promote only narrowly verified curriculum-scoped concepts, preserve immutable failure evidence, resume safely, and run a final source capstone.

Roberta's accepted *Mastering Blockchain, Fourth Edition* prebuilt banks reach Stage 8 / Market Structure. Stages 9-14 are not yet separately accepted prebuilt repository banks, though the accepted autonomous controller may generate missing later-stage banks at runtime under its validation contract. Bank availability is not mastery; final mastery requires every frozen required stage and capstone to pass in the authoritative ledger.

No Roberta Learning System, autonomous Learning Plane, retained lesson, learned concept, Pyramid, memory, policy, or human-review state overrides CMIS for freshness-sensitive facts, promotes CMIS/provider trust, or creates CMIS execution authority.

## Engineering governance

Meaningful CMIS changes follow [`docs/CMIS_ENGINEERING_WORKFLOW.md`](./docs/CMIS_ENGINEERING_WORKFLOW.md):

1. roadmap/issue ownership;
2. contract/spec before code when semantics/authority change;
3. narrow tracer-bullet implementation;
4. behavior-first deterministic tests;
5. exact-head/full applicable CI;
6. independent review on **Spec / Contract**, **Code / Architecture**, and **Authority / Evidence Safety**;
7. no merge while a required review axis is blocked;
8. post-merge README/roadmap/source-of-truth reconciliation.

Green CI alone is not acceptance.

## Runtime topology

```text
CMIS        127.0.0.1:8765
  ↓
Roberta     127.0.0.1:8766
  ↓
MoltGrid / Signal transport
```

Start CMIS with the compatibility namespace:

```bash
python -m liquidity_scout.cmis.http
```

The Roberta-first MoltGrid listener remains:

```bash
python -m liquidity_scout.integrations.moltgrid_roberta
```

## Installation

From WSL2 or Linux:

```bash
git clone https://github.com/bhaygood29053-pixel/cmis.git
cd cmis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Typical X1 configuration includes:

```text
AGENT_WALLET=YOUR_PUBLIC_X1_WALLET_ADDRESS
X1_NINJA_API_KEY=YOUR_X1_NINJA_API_KEY
X1_RPC_URL=https://rpc.mainnet.x1.xyz
```

Never commit secrets, private keys, signing keys, or seed phrases.

## Repository structure

```text
liquidity_scout/cmis/                     CMIS deterministic service layer
liquidity_scout/providers/x1/             X1/XDEX providers and verification
liquidity_scout/providers/solana/         Solana read-only providers
liquidity_scout/services/                 Shared service composition
liquidity_scout/market/                   Market-intelligence components
liquidity_scout/tokenomics/               Tokenomics components
liquidity_scout/integrations/             Transport / Roberta integration
```

Key documentation:

```text
docs/CMIS_CAPABILITY_CONTRACT.md
docs/CMIS_PRODUCT_ROADMAP.md
docs/CMIS_ENGINEERING_WORKFLOW.md
docs/CMIS_IDENTITY_MIGRATION.md
docs/DETERMINISTIC_INTELLIGENCE_CLASSIFICATION.md
docs/WALLET_RELATIONSHIP_EVIDENCE.md
docs/CONCENTRATION_THRESHOLD_ALERT_EVIDENCE.md
docs/PHASE_10_COMPLETION.md
docs/PHASE_11_COMPLETION.md
docs/PROJECT_STATUS_2026-08-26.md
ROBERTA_CMIS_ACCEPTED_BASELINE.md
ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md
SCOUT_CMIS_INTEGRATION_CONTRACT.md
ROBERTA_INTEGRATION_CONTRACT.md
```

## Safety boundary

CMIS is an intelligence system, not an autonomous execution engine. It does not currently authorize or perform:

- wallet signing;
- transaction broadcasting;
- private-key/seed custody;
- live swap execution;
- autonomous trading;
- bridge value movement;
- autonomous value movement.

Human review in Roberta is a review boundary, not a reusable signing credential. Learning or retention state is not a signing credential either.

## Identity migration

The project identity and GitHub repository are CMIS. Documentation and repository references are normalized to that identity while the working `liquidity_scout` Python namespace remains intact. A future package rename, if desired, requires a separate tested migration.

See [`docs/CMIS_IDENTITY_MIGRATION.md`](./docs/CMIS_IDENTITY_MIGRATION.md).

---

**CMIS verifies. Chain Scouts investigate. Roberta coordinates, learns within bounded rules, and explains.**
