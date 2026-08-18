# Scout ↔ CMIS Integration Contract

## Purpose

This document defines the external boundary between chain-specialist Scouts and **CMIS — Cross-Chain Market Intelligence Service**.

```text
Roberta
  ↓
X1 Scout / Solana Scout
  ↓ HTTP + JSON
CMIS Gateway
  ↓
CMIS deterministic services
  ↓
X1 / Solana providers and verified sources
```

Scouts interpret verified CMIS results. Scouts do **not** call X1.Ninja, X1 RPC, Solana RPC, DEX APIs, scanners, CMIS databases, or internal intelligence helpers directly.

## HTTP endpoints

```text
POST /v1/cmis
GET  /v1/cmis/capabilities
GET  /healthz
```

Default bind:

```text
127.0.0.1:8765
```

The compatibility Python module entry point remains:

```bash
python -m liquidity_scout.cmis.http
```

A non-loopback bind requires `CMIS_API_KEY`. CMIS never exposes provider credentials to Scouts.

## Capability handshake

The live capability manifest is authoritative for deployed service eligibility.

The current accepted Scout boundary requires capability schema `1` and CMIS contract `1.8.0` or newer compatible behavior. The Scout validates:

- public service classifications;
- callable state;
- chain requirements/limitations;
- Evidence Receipt / Proof Score declarations;
- risk/proof separation;
- missing-evidence-is-unknown behavior;
- the read-only `intelligence_foundation` non-promotion boundary.

The Phase 11 intelligence primitives are not public Scout services. They must remain outside `supported_services`, with public-service and automatic Scout-reliance promotion false.

Roberta does not perform this handshake directly; it belongs to the Scout ↔ CMIS boundary.

## Public service surface

The shared contract includes:

```text
asset_lookup
market_report
rank
historical_compare
tokenomics
risk_check
pre_trade_check
verification_evidence
```

Some internal/chain-specific services and deterministic helpers also exist inside CMIS. Their existence does not make them callable by Scouts.

## Request envelope

Typical request:

```json
{
  "service": "market_report",
  "chain": "x1",
  "asset": "AGI",
  "params": {}
}
```

The Scout must identify the chain. CMIS does not silently route an unsupported Solana request through X1 or vice versa.

## Response envelope

CMIS returns a structured envelope such as:

```json
{
  "service": "market_report",
  "chain": "x1",
  "status": "ok",
  "asset": {},
  "data": {},
  "risk": null,
  "confidence": {},
  "sources": [],
  "observed_at": null,
  "warnings": [],
  "errors": [],
  "evidence_receipt": {},
  "proof_score": {}
}
```

Common service statuses are:

```text
ok
partial
unavailable
ambiguous
error
```

A Scout must preserve source/provenance, observation time, confidence/proof state, warnings, limitations, unresolved fields, and errors when reporting upward. `partial`, `unavailable`, `ambiguous`, conflict, or insufficient evidence are meaningful states—not invitations to invent missing facts.

## X1 boundary

X1 is the mature CMIS surface. Accepted capability includes, where the exact contract permits:

- market reporting and rankings;
- tokenomics and authority evidence;
- historical comparison;
- deterministic risk;
- verification evidence lookup;
- deterministic trade/activity verification tooling;
- bounded analysis-only pre-trade behavior.

X1 evidence completeness is field- and scope-specific. A pool-, route-, provider-, program-, or sample-scoped fact must not become a global asset/X1 claim without proof.

### XDEX quote/history and execution evidence

XDEX evidence has advanced beyond the original blanket-unavailable boundary. Current accepted distinctions include:

- exact route/config identity can be verified for tested routes;
- route-scoped price impact can be independently reproduced where reserve/config evidence is accepted;
- quote slippage uses percent units for tested scope;
- quote slippage tolerance/minimum-received behavior is not expected execution slippage;
- selected 1-minute history timestamp/OHLC semantics are bounded/verified for tested scope, while unverified history fields remain unpromoted;
- a pinned XENCAT/native-XNT 23-swap state-contiguous historical sequence strongly corroborates the configured 2800-ppm execution model and strongly rejects 3000-ppm execution for that scope;
- the observed 3000-ppm quote baseline is therefore localized to the quote layer for that tested scope, without proving a hidden 0.02% collected fee or the private backend reason.

Global route optimality, fill quality, route quality, generic execution quality, and universal XDEX semantics remain unavailable unless separately proven.

## Solana boundary

Solana Phase 10 is implemented as a separate read-only provider path beneath the same CMIS contract.

Accepted foundation includes:

- exact-mint identity through canonical Solana RPC;
- SPL Token / Token-2022 handling;
- canonical supply and mint/freeze authority evidence;
- bounded market/risk evidence;
- optional Jupiter, Helius, and DEX Screener evidence when configured;
- deterministic cross-source checks;
- provenance-safe observation history;
- narrow historical comparison.

Solana rules include:

- exact mint identity where required;
- no symbol/name substitution when identity is not proven;
- no Solana → X1 fallback;
- pair-scoped DEX values are not asset-wide totals;
- optional providers fail closed when unavailable;
- availability is service-specific, not a blanket parity claim.

Solana ranking, pre-trade execution modeling, trade verification, verified asset-wide activity, signing, broadcasting, and custody remain unavailable until separately implemented and promoted.

## `verification_evidence`

`verification_evidence` is callable where the manifest permits it.

Trust path:

```text
fact-specific verifier
  ↓
sanitized verification envelope
  ↓
content-addressed evidence ledger
  ↓
exact lookup
  ↓
CMIS
  ↓
Chain Scout
  ↓
Roberta
```

Only accepted verified/promotable agreement may expose a promoted fact value. Conflicts, stale evidence, or insufficient evidence remain explicit.

## `risk_check`

Risk outcomes are deterministic:

```text
PASS
WARN
BLOCK
```

Service status and risk outcome are separate. A service-level `ok` may legitimately contain `WARN` or `BLOCK`.

Roberta may explain CMIS risk but does not recalculate provider facts, invent a score, or strengthen incomplete evidence.

## `pre_trade_check`

`pre_trade_check` is **analysis only**.

Accepted deterministic behavior includes:

- proposed notional;
- verified liquidity where available;
- notional-to-liquidity ratio;
- explicit versioned trade-size policy;
- fail-closed missing/conflicting liquidity;
- explicit required-capability gates;
- bounded internal route evidence for selected advanced facts.

The accepted route-evidence seam is internal to CMIS. The public X1 HTTP gateway does **not** accept arbitrary caller-supplied `route_evidence` as a way to manufacture verified execution facts.

For an exact route, selected price-impact or bounded AMM/execution-model fee evidence may become usable only when all accepted source, route-identity, freshness, semantic, unit, and proof-basis requirements pass.

Important current non-promotions:

- quote slippage tolerance is not expected execution slippage;
- expected execution slippage remains unavailable without a separately accepted execution-slippage evidence contract;
- route quality, bridge dependency, fill quality, transaction simulation, and generic execution quality remain unavailable unless separately proven.

Every current pre-trade result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` is not permission to trade.

## Boundary rules

A Scout must not:

- import provider internals as a replacement for CMIS;
- submit provider rows as substitutes for CMIS collection/verification;
- manufacture missing market, liquidity, volume, supply, holder, authority, burn/mint, price-impact, fee, slippage, route, or risk facts;
- convert `partial`, `unavailable`, `ambiguous`, conflict, or insufficient evidence into verified facts;
- treat internal Phase 11 intelligence helpers as public services;
- treat `pre_trade_check` as transaction authorization.

CMIS must not:

- make Roberta's final user-facing conversational decision;
- silently substitute one chain for another;
- expose credentials;
- claim unavailable verification;
- authorize signing, broadcasting, custody, trading, or autonomous value movement.

## Core principle

**CMIS determines what the evidence supports. Chain Scouts preserve and interpret that chain-specific result. Roberta coordinates and explains it to the user.**
