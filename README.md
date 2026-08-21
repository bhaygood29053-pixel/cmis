# CMIS

**Cross-Chain Market Intelligence Service**

CMIS is the deterministic blockchain-intelligence backend used by chain-specific Scouts. X1 Scout and Solana Scout call CMIS for freshness-sensitive market facts, tokenomics, verification evidence, proof quality, historical intelligence, deterministic risk, and bounded pre-trade analysis. Their reports flow back to Roberta, which owns coordination, policy, reasoning, and the final user-facing response.

The repository was originally created as **Liquidity Scout**. That name describes the early prototype, not the current architecture. The GitHub repository is now `bhaygood29053-pixel/cmis`.

> Compatibility note: the Python package namespace is still `liquidity_scout`. That internal namespace is intentionally unchanged during the repository/identity migration so working imports, tests, module entry points, deployment commands, and Roberta integration are not broken.

## Architecture

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
Roberta → Chain Scout → CMIS → Chain Provider
```

Verified information flows upward:

```text
Chain Provider → CMIS → Chain Scout → Roberta
```

CMIS owns deterministic facts and evidence. Chain Scouts own chain-specific investigation and interpretation. Roberta owns user intent, policy, coordination, and final synthesis. Neither Roberta nor a Scout should reproduce CMIS/provider calculations to manufacture a second market fact.

## Current roadmap position

As of August 21, 2026:

- **CMIS Phase 10 — Solana read-only provider foundation:** complete.
- **Evidence Receipts + Proof Score milestone:** complete.
- **X1 evidence-capability boundary:** complete and fail-closed.
- **Deterministic pre-trade trade-size analysis:** complete.
- **CMIS Phase 11 — read-only Verified Intelligence foundation:** complete.
- **CMIS Phase 12 — first narrow X1 public-service / Scout-reliance promotion:** complete for `concentration_change_intelligence/v1`.
- **Deterministic descriptive intelligence classification foundation:** complete, internal/read-only/non-promoted.
- **Deterministic wallet relationship evidence foundation:** complete with explicit non-ownership semantics and no public/Scout promotion.
- **Deterministic concentration-threshold alert evidence foundation (#263/#264):** complete, internal/read-only/non-promoted.
- **CMIS deterministic engineering workflow / three-axis review:** adopted and repository-authoritative.
- **Parallel X1 provider-gap work:** Issue #30 remains open, read-only, and fail-closed.
- **Next promoted intelligence milestone:** not yet accepted; a separate contract/gate is required before any alert public-service or Scout-reliance promotion.
- **Controlled transaction execution:** not an active CMIS milestone and not authorized.

The authoritative product roadmap is [`docs/CMIS_PRODUCT_ROADMAP.md`](./docs/CMIS_PRODUCT_ROADMAP.md). The repository-authoritative engineering workflow is [`docs/CMIS_ENGINEERING_WORKFLOW.md`](./docs/CMIS_ENGINEERING_WORKFLOW.md). Phase 11 completion is documented in [`docs/PHASE_11_COMPLETION.md`](./docs/PHASE_11_COMPLETION.md).

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

Every chain/service combination is classified explicitly rather than assumed from another chain. Missing, incompatible, or non-callable capability evidence fails closed.

The current CMIS contract is `1.9.0`. It preserves the bounded read-only `intelligence_foundation` and separately advertises the exact promoted concentration-change service. The deterministic classification, wallet-relationship, and concentration-alert foundations are internal/read-only/non-promoted and therefore do not silently become public Scout services or capability-manifest operations.

## X1 / XDEX foundation

CMIS contains mature deterministic X1/XDEX capabilities including, where the evidence contract permits:

- asset and pool discovery;
- price, liquidity, volume, and ranking support;
- RPC supply and authority verification;
- deterministic XDEX trade verification;
- provider-vs-chain reconciliation;
- bounded verified-activity coverage;
- historical snapshots and comparisons;
- tokenomics and burn evidence;
- evidence receipts and proof scores;
- deterministic risk analysis;
- versioned trade-size analysis against verified liquidity;
- fail-closed XDEX quote/history semantic gates.

Provider-reported observations remain provider-reported until independently verified. Program-scoped completeness is not relabeled as global X1 completeness.

## Solana read-only foundation

Solana is implemented beneath the same CMIS contract rather than as a separate intelligence stack. Accepted components include:

- exact-mint identity through canonical Solana RPC;
- SPL Token and Token-2022 program identity handling;
- canonical token supply and mint/freeze authority evidence;
- Jupiter read-only price evidence when configured;
- Helius indexed evidence when configured;
- DEX Screener pair-scoped market evidence;
- deterministic cross-source price and supply checks;
- provenance-safe observation history;
- bounded/partial read-only CMIS services.

Solana production composition remains environment-controlled and fail-closed.

## Verified Intelligence foundation

CMIS Phase 11 established read-only deterministic primitives for:

- exact top-account concentration observations and compatible numeric changes;
- neutral verified wallet-activity facts without behavioral labels;
- sanitized sparse historical intelligence storage and compatible-series comparison;
- evidence-bound conclusions with content-addressed Evidence Receipts and recomputed Proof Scores.

Additional accepted internal deterministic foundations now include:

- descriptive classification of the exact concentration direction proven by canonical CMIS evidence, without behavioral/ownership/intent/risk interpretation;
- direct wallet-relationship evidence for verified token transfers between exact chain identities, with explicit non-ownership semantics, content-addressed evidence identity, bounded compatible aggregation, and duplicate protection;
- concentration-threshold alert evidence built from canonical concentration evidence plus explicit threshold/comparator, freshness, subject, unit, and single-observation persistence semantics, with deterministic content-addressed evidence/alert identities.

These foundations are not public CMIS services or Scout-reliance contracts. The alert foundation preserves `read_only=true`, `public_service_promoted=false`, `scout_reliance_promoted=false`, `cmis_promotable=false`, and `execution_authorized=false`. CMIS does **not** infer labels such as insider, whale, bot, accumulator, distributor, market maker, manipulator, scam, beneficial owner, common owner, risk severity, or imminent price movement from these foundations.

## Early-warning direction

Issue #263 / PR #264 completed the first deterministic concentration-threshold alert evidence foundation. It reports only the exact threshold condition supported by accepted canonical concentration evidence and explicit deterministic policy; alert state is separate from Proof Score and risk.

No alert public service, Scout-reliance path, delivery runtime, Roberta planner behavior, multi-observation persistence, or execution authority has been promoted. Any next alert/promotion slice requires a separately accepted issue/spec/roadmap gate.

## Engineering governance

CMIS Issue #259 established [`docs/CMIS_ENGINEERING_WORKFLOW.md`](./docs/CMIS_ENGINEERING_WORKFLOW.md) as the repository-authoritative process for meaningful changes. The workflow requires roadmap ownership, contract/spec-before-code, narrow tracer-bullet slices, behavior-first deterministic tests, exact-head/full-suite verification, and post-merge roadmap reconciliation.

Non-trivial PRs are reviewed independently on **Spec / Contract**, **Code / Architecture**, and **Authority / Evidence Safety**. The authority axis preserves source scope, provider-vs-verified truth, null/unknown semantics, Proof Score vs risk separation, chain identity, ownership/behavior inference boundaries, and `analysis_only=true` / `execution_authorized=false` where required.

The existing Evidence Receipt / Proof Score / provenance model remains the canonical evidence system. Reconciliation vocabulary such as `superseded`, `evolution`, `conflict`, and `unknown / insufficient` is deterministic and evidence-bound rather than LLM-authoritative. The cross-project coordinating initiative is `bhaygood29053-pixel/roberta-langgraph#97`; CMIS #259 does not add HXMP durable memory or Technology Radar implementation to CMIS.

## Pre-trade analysis

`pre_trade_check` is analysis only. On supported paths it can evaluate requested notional against verified liquidity and deterministic trade-size policy.

Fields such as slippage, price impact, route quality, fees, bridge dependency, and simulation are only populated when their semantics are independently established. Missing evidence remains unavailable; it is never converted into a fake zero or guessed value.

Current analysis preserves the equivalent of:

```text
analysis_only = true
execution_authorized = false
```

## Runtime topology

The intended local service topology is:

```text
CMIS        127.0.0.1:8765
  ↓
Roberta     127.0.0.1:8766
  ↓
MoltGrid / Signal transport
```

Start CMIS with the existing compatibility namespace:

```bash
python -m liquidity_scout.cmis.http
```

The Roberta-first MoltGrid listener currently remains:

```bash
python -m liquidity_scout.integrations.moltgrid_roberta
```

These module paths are intentionally unchanged during Stage 2 of the identity migration.

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

The historical Python namespace remains visible in paths such as:

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
SCOUT_CMIS_INTEGRATION_CONTRACT.md
ROBERTA_INTEGRATION_CONTRACT.md
```

## Safety boundary

CMIS is an intelligence system, not an autonomous execution engine. It does not currently authorize or perform:

- wallet signing;
- transaction broadcasting;
- private-key or seed custody;
- live swap execution;
- autonomous trading;
- autonomous value movement.

Human review in Roberta is a review boundary, not a reusable signing credential.

## Identity migration

The project identity and GitHub repository have been renamed to **CMIS**. Documentation and repository references are being normalized while the working `liquidity_scout` Python namespace remains intact. A future internal package rename, if desired, must be handled as a separate tested migration.

See [`docs/CMIS_IDENTITY_MIGRATION.md`](./docs/CMIS_IDENTITY_MIGRATION.md).

---

**CMIS verifies. Chain Scouts investigate. Roberta coordinates and explains.**