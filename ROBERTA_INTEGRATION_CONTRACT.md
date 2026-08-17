# Roberta ↔ CMIS Integration Contract

## Purpose

This document is the source-of-truth boundary between **Roberta**, the top-level Oracle and Agent Coordinator, and **CMIS** (the Cross-Chain Market Intelligence Service, evolved incrementally from Liquidity Scout).

Authority flows downward:

**Roberta → Chain Scout → CMIS → Chain Provider**

Verified information flows upward:

**Chain Provider → CMIS → Chain Scout → Roberta**

CMIS supplies deterministic specialist facts, evidence, risk analysis, and explicit uncertainty. Roberta owns user intent, policy, coordination, broader reasoning, approval boundaries, and final synthesis.

---

## 1. Authority Boundary

### Roberta owns

- user interaction and user intent
- user policy
- long-term context
- specialist coordination
- workflow orchestration
- cross-chain and higher-level reasoning
- final recommendations and response synthesis
- approval boundaries for consequential actions

### Chain Scouts own

- chain-specific interpretation
- deciding which CMIS checks are relevant
- requesting verified CMIS information
- preserving CMIS uncertainty and provenance
- reporting structured findings to Roberta

### CMIS owns

- asset discovery and resolution
- deterministic live market collection
- multi-LP aggregation
- volume aggregation and rankings
- historical comparisons
- tokenomics and authority verification
- burn/mint intelligence
- evidence/provenance storage
- independent-source verification
- deterministic data-quality/confidence calculations
- deterministic risk calculations
- pre-trade market-risk analysis
- source timestamps, confidence, warnings, and explicit errors

### Providers own

Chain-specific transport and parsing beneath CMIS, including X1.Ninja/XDEX, X1 RPC, Solana RPC/DEX/indexer integrations, scanners, and chain-specific verification plumbing.

Roberta and Chain Scouts must not reproduce provider or CMIS calculations in order to manufacture a second market fact.

---

## 2. Source-of-Truth Rule

For live market, liquidity, tokenomics, verification, and risk facts:

**Fresh verified CMIS/provider data overrides remembered or conversational values.**

Never invent or substitute values for unavailable:

- prices
- liquidity
- volume
- holders
- supply
- rankings
- burn/mint totals
- token or mint addresses
- pool addresses
- `#LPs`
- authority status
- verification outcomes
- risk/safety metrics
- slippage
- price impact
- routes
- execution fees

If a value cannot be verified, CMIS returns it as unavailable, unknown, unsupported, ambiguous, partial, or unverified.

Roberta preserves that state.

---

## 3. Market Aggregation Rule

When sufficient data exists, CMIS reports asset-wide market information rather than silently presenting one pool as the whole asset.

CMIS should aggregate across all relevant identified liquidity pools and use **`#LPs`** for public liquidity-pool count.

Responses should distinguish:

- asset-wide metrics
- individual-pool metrics
- partial coverage
- unavailable data

---

## 4. Current Roberta-Facing Service Surface

The current CMIS runtime supports the shared service contract for:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`

Additional internal or chain-specific services may exist, but Roberta must use only supported, tested contracts through the appropriate Chain Scout/CMIS boundary.

Supported service-level statuses are:

- `ok`
- `partial`
- `unavailable`
- `ambiguous`
- `error`

A verification result such as `AGREEMENT`, `CONFLICT`, or `INSUFFICIENT_EVIDENCE` is evidence state inside the CMIS result; Roberta must not silently rewrite it into a stronger service fact.

---

## 5. Common Response Contract

CMIS responses are structured and machine-readable and preserve the following envelope shape:

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
  "errors": []
}
```

Service-specific fields may extend `data`, `risk`, and `confidence`, but the following properties remain mandatory design goals:

- deterministic facts
- source traceability
- timestamps
- verification state where relevant
- confidence/data quality
- uncertainty
- warnings
- explicit errors

---

## 6. `verification_evidence`

**Status: accepted and runtime-callable through the exact-selector CMIS boundary.**

Accepted trust path:

**fact-specific verifier → sanitized verification envelope → content-addressed evidence ledger → exact lookup → CMIS runtime → Chain Scout/Roberta**

Roberta may request evidence only through exact selectors supported by the contract. Roberta must not submit raw verifier/provider objects, choose persistence paths, or reconstruct verification state.

Important behavior:

- only CMIS-promotable verified agreement may expose a promoted fact value/unit
- stale or non-promotable agreement remains non-promoted
- conflicts and insufficient evidence remain explicit
- persisted evidence is sanitized and content-addressed
- source identity, source role, timestamps, quality, and verification state are preserved

---

## 7. `risk_check`

**Status: implemented, deterministic, and runtime-callable.**

Risk outcomes are:

- `PASS`
- `WARN`
- `BLOCK`

Risk findings must remain explainable and reproducible. Roberta may interpret a CMIS risk result in broader context but must not recalculate the underlying live market facts or strengthen incomplete evidence.

A service-level `ok` can legitimately contain a risk `WARN` or `BLOCK`; service completeness and risk severity are separate concepts.

---

## 8. `pre_trade_check` — Bounded Completion Contract

**Status: implemented and runtime-callable for deterministic analysis at the currently verified evidence maturity.**

Accepted implementation checkpoint after CMIS PRs #120–#124:

- accepted CMIS main SHA: `d4ac9044d087641f94eff3f0a6e693c89b878ca2`
- exact post-merge test run: `32061851080` / run #408, successful

### 8.1 Inputs

The normal X1 runtime path receives:

- target asset
- trade side
- proposed USD notional
- internally produced `risk_check`
- optional explicit `pre_trade_policy`

`params.policy` remains risk policy.

`params.pre_trade_policy` is a separate pre-trade analysis policy. CMIS must never reinterpret risk thresholds as trade-size/freshness thresholds.

### 8.2 Deterministic calculations currently implemented

CMIS can calculate from already-verified risk evidence:

- trade notional
- verified asset-wide liquidity used by the risk result
- `notional_to_liquidity_ratio`
- explicit policy warning notional derived from a supplied warning ratio
- explicit policy hard-block notional derived from a supplied block ratio
- risk-evidence age when both evidence time and CMIS evaluation time are verified

CMIS does **not** invent default notional/liquidity or freshness thresholds.

### 8.3 Explicit pre-trade policy

The current policy can include:

- `warn_notional_to_liquidity_ratio`
- `block_notional_to_liquidity_ratio`
- `warn_on_missing_notional`
- `block_on_unverified_liquidity_for_sized_trade`
- `warn_risk_age_seconds`
- `block_risk_age_seconds`
- `block_on_unverified_timestamp_when_age_policy_set`
- `required_capabilities`

Numeric ratio/freshness thresholds are unset unless explicitly supplied.

### 8.4 Fail-closed size behavior

- Missing proposed notional is incomplete size evidence.
- A sized trade with unverified asset-wide liquidity fails closed by default.
- Verified zero liquidity blocks a sized trade.
- Explicit warn/block ratios produce deterministic `WARN`/`BLOCK` findings.
- A verified threshold breach remains a service-level `ok` finding because the evidence is complete; missing required evidence produces `partial`.

### 8.5 Fail-closed freshness behavior

CMIS uses the upstream risk envelope's observation timestamp as risk-evidence time and an internal runtime clock as evaluation time.

Caller-supplied display timestamps or `evaluated_at` fields must not replace those evidence timestamps.

When an explicit freshness policy is active:

- verified stale evidence may deterministically `WARN` or `BLOCK`
- missing/invalid/future-dated temporal evidence fails closed as incomplete/`partial`

No universal freshness window is currently asserted by CMIS.

### 8.6 Execution-estimate capability contract

The following advanced execution estimates currently have explicit capability records and are **unavailable unless/until a verified producer is implemented**:

- slippage
- price impact
- route quality
- bridge dependency
- fees
- transaction simulation

For each unavailable capability CMIS returns:

- `status: "unavailable"`
- `value: null`
- an explicit `reason_code`
- the evidence required to support that capability

CMIS must not substitute zero, a heuristic percentage, a guessed route, or an assumed fee.

If `required_capabilities` explicitly requires an unavailable capability, `pre_trade_check` fails closed with a `BLOCK` analysis and service status `partial`.

### 8.7 Public presentation fields

For Roberta/Scout presentation, CMIS projects only already-computed evidence into:

- `data.market.verified_liquidity_usd`
- `data.trade_size.assessment`
- `data.trade_size.notional_to_liquidity_ratio`
- deterministic warn/hard-block notional thresholds when configured
- `data.route_analysis` with unavailable estimates preserved as `null`
- `data.execution_capabilities`

This projection is an alias/presentation layer, not a second market calculation.

### 8.8 Execution boundary

Every `pre_trade_check` result includes the equivalent of:

- `analysis_only = true`
- `execution_authorized = false`

A `PASS` means only that the deterministic checks actually performed did not produce a warning/block. It is **not** permission to trade.

Roberta must not reinterpret `PASS`, a verified size ratio, or any risk result as authorization to prepare, sign, broadcast, or autonomously execute a transaction.

---

## 9. Advanced Pre-Trade Work Still Future

Bounded pre-trade completion does **not** mean Phase-12 execution modeling is complete.

Future work requires separately verified evidence producers/contracts for items such as:

- AMM/pool depth-curve simulation
- verified slippage calculation
- verified price-impact calculation
- route candidate generation and comparison
- route/pool concentration analysis
- deterministic fee modeling/quotes
- canonical representation and bridge constraints
- read-only unsigned transaction simulation

Those capabilities should enter CMIS one deterministic layer at a time and must remain unavailable until proven.

---

## 10. Confidence, Data Quality, and Uncertainty

CMIS confidence/data quality may reflect:

- identity verification
- source availability
- source freshness
- units/semantics verification
- LP coverage
- RPC verification
- independent-source agreement/conflict
- historical/scanner coverage
- calculation completeness
- pre-trade size evidence completeness
- pre-trade freshness evidence completeness when required
- availability of explicitly required pre-trade capabilities

Roberta may explain confidence but must not turn low/incomplete evidence into a verified fact.

---

## 11. Provenance and Evidence Rules

Where practical, CMIS preserves:

- source name
- source role
- chain
- asset/pool identity
- observation time
- block/slot when available
- raw/normalized fact identity where safe
- calculation/service version
- verification result
- warnings/errors

Two observations are not independent merely because they carry different labels. Independence is a deterministic CMIS determination.

---

## 12. Failure Rules

CMIS and Roberta must fail safely.

They must not:

- substitute remembered values for unavailable live facts
- invent LPs, supply, holders, rankings, burns, mints, or authorities
- infer circulating supply from total supply without verification
- average conflicting facts unless a documented deterministic rule permits it
- promote a fact when required identity, units, semantics, freshness, or independence is unproven
- invent pre-trade slippage, price impact, routes, fees, or simulation results
- treat an unavailable advanced pre-trade capability as a zero-risk result

---

## 13. Roberta Consumption Rules

When Roberta requests CMIS information:

1. Roberta preserves user intent and policy.
2. The relevant Chain Scout requests the supported CMIS service.
3. CMIS/provider code collects/calculates deterministic facts.
4. CMIS returns the structured result with provenance and uncertainty.
5. The Chain Scout interprets chain-specific meaning without inventing facts.
6. Roberta synthesizes the specialist result with broader context.

For `pre_trade_check`, Roberta may phrase and explain the CMIS output but must not calculate a replacement size ratio, slippage estimate, price impact, route, fee, or risk recommendation.

If an execution estimate is unavailable, Roberta should say it is unavailable rather than filling the gap from model knowledge.

---

## 14. Execution Boundary

`pre_trade_check` is analysis only.

No current CMIS pre-trade result authorizes:

- transaction preparation
- wallet signing
- broadcasting
- autonomous live trading

Autonomous execution remains prohibited until explicit human approval gates, transaction safeguards, deterministic simulation/execution contracts, and testing are implemented.

---

## 15. Core Integration Principle

**CMIS determines what is happening in supported markets now and what its verified evidence supports.**

**Chain Scouts determine what those verified facts mean within their chains.**

**Roberta determines what the specialist findings mean in the larger user and cross-chain context.**

CMIS becomes smarter by proving more, remembering more, and calculating more from verified evidence—not by guessing more.
