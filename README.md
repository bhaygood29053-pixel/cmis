# CMIS

**Cross-Chain Market Intelligence Service**

CMIS is the deterministic blockchain-intelligence backend used by chain-specific Scouts. X1 Scout and Solana Scout call CMIS for capability-gated, freshness-sensitive market facts, tokenomics, verification evidence, proof quality, historical intelligence, deterministic risk, bounded pre-trade analysis, and promoted read-only intelligence services. Their reports flow back to Roberta, which owns coordination, policy, reasoning, and the final user-facing response.

The repository was originally created as **Liquidity Scout**. That name describes the early prototype, not the current architecture. The canonical repository is `bhaygood29053-pixel/cmis`.

> Compatibility note: the Python package namespace remains `liquidity_scout`. That internal namespace is intentionally unchanged during the staged identity migration so working imports, tests, module entry points, deployment commands, and Roberta integration are not broken.

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

Authority flows downward: `Roberta → Chain Scout → CMIS → Chain Provider`.
Verified information flows upward: `Chain Provider → CMIS → Chain Scout → Roberta`.

CMIS owns deterministic facts, evidence, proof, risk, capability eligibility, and accepted intelligence-service calculations. Chain Scouts own chain-specific investigation and interpretation. Roberta owns user intent, policy, coordination, and final synthesis. Neither Roberta nor a Scout should reproduce CMIS/provider calculations to manufacture a second market fact.

## Current roadmap position

As of August 20, 2026:

- **CMIS Phase 10 — Solana read-only provider foundation:** complete.
- **Evidence Receipts + Proof Score milestone:** complete.
- **X1 evidence-capability boundary:** complete and fail-closed.
- **Deterministic pre-trade trade-size analysis:** complete.
- **CMIS Phase 11 — read-only Verified Intelligence foundation:** complete.
- **CMIS Phase 12 — first promoted read-only Verified Intelligence service:** accepted for X1 through `concentration_change_intelligence/v1`.
- **Controlled transaction execution:** not an active CMIS milestone and not authorized.

The authoritative product roadmap is [`docs/CMIS_PRODUCT_ROADMAP.md`](./docs/CMIS_PRODUCT_ROADMAP.md). Phase 11 completion is documented in [`docs/PHASE_11_COMPLETION.md`](./docs/PHASE_11_COMPLETION.md).

## Roberta-facing service surface

CMIS contract `1.9.0` includes, depending on the live per-chain capability state:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`
- `concentration_change_intelligence`

The live capability manifest is authoritative:

```text
GET /v1/cmis/capabilities
```

Every chain/service combination is classified explicitly rather than assumed from another chain. Missing, incompatible, or non-callable capability evidence fails closed.

### Phase 11 foundation vs Phase 12 promotion

The Phase 11 `intelligence_foundation` remains read-only and deliberately unpromoted as a whole: `public_service_promoted=false` and `scout_reliance_promoted=false`.

Phase 12 promotes **exactly one narrow public service**, not the whole foundation:

```text
service: concentration_change_intelligence
contract: concentration_change_intelligence/v1
accepted conclusion: top_account_concentration_change
```

For X1, the capability is `bounded`, callable, read-only, publicly promoted, and Scout-reliance promoted. Requests bind exact X1 asset identity and a canonical CMIS-owned `intelligence_evidence_id`; caller-supplied proof objects are not trusted inputs. The service does not convert token accounts into unique holders or beneficial owners. Optional explicit/versioned concentration-threshold policy remains policy evaluation, not a market-risk or behavioral label. `risk` remains separate/null.

For Solana, `concentration_change_intelligence` is explicitly unavailable and non-callable. Solana must never inherit X1 capability by fallback.

Broader Phase 11 primitives—including raw concentration snapshots, wallet activity, generic sanitized history, and generic evidence-bound conclusions—remain non-public/non-automatic until separately promoted.

## X1 / XDEX foundation

CMIS contains mature deterministic X1/XDEX capabilities including, where the evidence contract permits, asset/pool discovery, market and ranking support, tokenomics/authority verification, transaction/trade verification, historical comparison, Evidence Receipts and Proof Scores, deterministic risk, bounded pre-trade analysis, and the promoted X1-only concentration-change intelligence service.

Provider-, program-, pool-, route-, account-, or sample-scoped evidence is not automatically asset-wide/global truth. Holder and beneficial-owner semantics must not be inferred from token-account concentration.

## Solana read-only foundation

Solana is implemented beneath the same CMIS contract rather than as a separate intelligence stack. Accepted components include exact-mint identity, SPL Token and Token-2022 handling, canonical supply/authority evidence, configured Jupiter/Helius/DEX Screener evidence, deterministic cross-source checks, provenance-safe observation history, and bounded/partial read-only services where advertised.

Solana production composition remains environment-controlled and fail-closed. It is not assumed to have X1 parity, and the Phase 12 concentration-change service is currently unavailable on Solana.

## Evidence, proof, risk, and intelligence boundaries

Evidence Receipts and Proof Scores describe evidence quality; they are not market-risk scores. Roberta and Scouts preserve source identity, scope, freshness, disagreements, limitations, unresolved fields, and proof state without recomputation.

CMIS does **not** infer labels such as insider, whale, bot, accumulator, distributor, market maker, manipulator, common owner, or beneficial owner unless a later accepted deterministic evidence/classification contract explicitly permits such a conclusion.

## Pre-trade analysis

`pre_trade_check` is analysis only. On supported paths it can evaluate requested notional against verified liquidity and deterministic policy. Advanced execution-related fields are populated only when their semantics and evidence are independently established. Missing evidence remains unavailable; it is never converted into a fake zero or guessed value.

Current analysis preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

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

These module paths are intentionally unchanged during the identity migration.

## Installation

```bash
git clone https://github.com/bhaygood29053-pixel/cmis.git
cd cmis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
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

Key documentation includes `docs/CMIS_CAPABILITY_CONTRACT.md`, `docs/CMIS_PRODUCT_ROADMAP.md`, `docs/CMIS_IDENTITY_MIGRATION.md`, `docs/PHASE_10_COMPLETION.md`, `docs/PHASE_11_COMPLETION.md`, `SCOUT_CMIS_INTEGRATION_CONTRACT.md`, and `ROBERTA_INTEGRATION_CONTRACT.md`.

## Safety boundary

CMIS is an intelligence system, not an autonomous execution engine. No current CMIS service—including `concentration_change_intelligence`—authorizes or performs transaction preparation as an execution precursor, wallet signing, broadcasting, custody, live swaps, bridge transfer, autonomous trading, or autonomous value movement.

Human review in Roberta is a review boundary, not a reusable signing credential.

## Identity migration

The project identity and GitHub repository are **CMIS**. The working `liquidity_scout` Python namespace remains a compatibility implementation detail. A future internal package rename, if desired, must be handled as a separate tested migration.

See [`docs/CMIS_IDENTITY_MIGRATION.md`](./docs/CMIS_IDENTITY_MIGRATION.md).

---

**CMIS verifies. Chain Scouts investigate. Roberta coordinates and explains.**
