# Roberta ↔ Liquidity Scout Integration Contract

## Purpose

This document defines the integration boundary between **Roberta**, the X1 Oracle and Agent Coordinator, and **Liquidity Scout**, the X1 Market Intelligence & Risk Service.

Roberta may invoke Liquidity Scout whenever current X1/XDEX market, tokenomics, historical, or risk information is required.

Liquidity Scout supplies verified specialist facts.

Roberta remains responsible for broader reasoning, user policy, specialist coordination, long-term context, and final synthesis.

---

## 1. Authority Boundary

### Roberta owns

- user interaction
- user policy
- long-term context
- agent coordination
- workflow orchestration
- higher-level reasoning
- final recommendations
- final response synthesis
- approval boundaries for consequential actions

### Liquidity Scout owns

- X1.Ninja / XDEX market intelligence
- X1 RPC verification
- asset discovery and resolution
- deterministic current market metrics
- multi-LP aggregation
- rankings
- historical market comparisons
- tokenomics verification
- burn and mint intelligence
- Scout Risk Engine results when implemented
- pre-trade market-risk analysis when implemented

Liquidity Scout is a **specialist service**.

It is not the top-level Oracle.

---

## 2. Freshness and Source Authority

For live X1/XDEX market facts:

**Fresh deterministic Liquidity Scout data overrides Roberta's remembered market values.**

This applies to values including:

- price
- liquidity
- #LPs
- volume
- transaction activity
- holders
- total supply
- circulating supply only when independently verified
- rankings
- pool information
- burn totals
- mint activity
- authority status
- Scout risk metrics when available

Conversation history, model memory, or previous market reports must not override newer verified Liquidity Scout observations.

---

## 3. Deterministic Data Rule

Liquidity Scout must prefer deterministic collection and calculation for live facts.

An LLM may:

- explain verified results
- summarize results
- describe risk factors
- translate structured results into natural language

An LLM must not manufacture or estimate unavailable live market facts.

If a value cannot be verified, Liquidity Scout must return it as unavailable, unknown, unsupported, or unverified.

It must not invent a replacement value.

---

## 4. Market Aggregation Rule

Asset-level market information should represent the asset rather than a single pool whenever sufficient data is available.

Liquidity Scout should aggregate across all relevant identified liquidity pools.

Public market reports and rankings should use:

**`#LPs`**

for liquidity-pool count.

Where appropriate, responses should distinguish:

- asset-wide metrics
- individual-pool metrics
- partial aggregation
- unavailable pool data

---

## 5. Target Roberta-Callable Services and Implementation Status

This section defines the intended Roberta-facing service surface. It does **not** imply that every listed capability is already exposed through the final Roberta/API contract.

Implementation status should be interpreted as follows:

- **implemented core** — reusable deterministic Liquidity Scout logic exists and is independently testable;
- **wrapper planned** — core capability exists, but the final Roberta-facing service envelope is not yet complete;
- **planned** — capability belongs to a future roadmap phase and must not be treated as live.

### `asset_lookup`

**Status:** implemented core; Roberta-facing structured wrapper planned.

Resolves an asset from:

- symbol
- name
- mint
- pool identifier

Expected result:

- resolved asset identity
- mint address
- known LPs
- resolution confidence
- ambiguity information when applicable

### `market_report`

**Status:** implemented core; common Roberta response-envelope wrapper planned.

Returns current verified market information when available.

Possible fields include:

- asset identity
- price
- total liquidity
- #LPs
- 24h volume
- transaction activity
- holders
- price changes
- volume changes when supported by verified data
- liquidity changes when supported by verified historical data
- rankings
- source timestamps
- confidence/completeness

### `rank`

**Status:** implemented core; Roberta-facing response envelope planned.

Supported ranking dimensions may include:

- 24h volume
- liquidity
- 1h trending
- gainers
- losers
- holders
- safety

Ranking methodology should be deterministic and reproducible.

### `historical_compare`

**Status:** implemented core; Roberta-facing response envelope planned.

Input:

- asset
- metric
- period
- optional threshold
- optional direction

Returns:

- historical value
- current value
- absolute change when relevant
- percent change
- threshold result
- confidence
- observation timestamps

Historical storage must remain separate from the live market listener.

### `tokenomics`

**Status:** implemented core; activity coverage remains bounded by verified scanner coverage and the final Roberta-facing response envelope is planned.

Returns verified token information when supported.

Possible fields include:

- current total supply
- circulating supply only when independently verified
- mint authority
- freeze authority
- mint activity
- burn activity
- net issuance only when scan coverage and verification requirements are satisfied
- verification source
- confidence

Burn and mint scanning must remain separate from ordinary XDEX market polling.

### `risk_check`

**Status:** planned for the Scout Risk Engine phase.

Returns the Liquidity Scout risk assessment.

Possible fields include:

- component risks
- Scout score
- confidence
- flags
- reasons
- recommendation

Recommendation states should support:

- `PASS`
- `WARN`
- `BLOCK`

Risk results must remain explainable.

### `pre_trade_check`

**Status:** planned after the required market, tokenomics, and Scout Risk Engine layers are implemented and tested.

Input:

- asset
- trade side
- proposed trade size

Returns, when available:

- current market facts
- available liquidity
- trade-size-to-liquidity relationship
- estimated price impact
- estimated slippage
- market-risk factors
- tokenomics-risk factors
- Scout risk result
- confidence
- reasons

A successful pre-trade check does not itself authorize execution.

---

## 6. Target Response Contract

Roberta-facing responses should ultimately be structured and machine-readable.

The following common response envelope is a **target interface for the Roberta Interface phase**. It is not a claim that every current reusable service already exposes this exact API shape.

```json
{
  "service": "market_report",
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

Exact schemas may evolve independently for each service, but responses should preserve the following properties:

- deterministic facts
- source traceability
- timestamps
- confidence
- uncertainty
- warnings
- explicit errors

Until the common envelope is implemented, existing reusable service return structures remain internal implementation contracts and must not be represented to Roberta as finalized public APIs.

---

## 7. Status Semantics

Recommended service-level statuses for the target Roberta-facing interface:

### `ok`

The requested result was successfully produced from sufficiently verified data.

### `partial`

Useful results were produced, but one or more requested fields could not be verified.

### `unavailable`

The required source or data was unavailable.

### `ambiguous`

The requested asset could not be uniquely resolved.

### `error`

The request could not be completed because of a service or processing failure.

Liquidity Scout should prefer explicit partial results over silently fabricating missing fields.

---

## 8. Confidence and Uncertainty

Liquidity Scout must preserve uncertainty rather than hiding it.

Confidence may reflect factors such as:

- source availability
- source freshness
- asset-resolution confidence
- LP coverage
- RPC verification
- historical-data coverage
- scanner coverage
- calculation completeness

Roberta may use confidence information as part of broader reasoning but must not reinterpret an unverified value as verified.

---

## 9. Source Traceability

Where practical, Liquidity Scout responses should identify the source category used for important facts.

Examples:

- `x1_ninja`
- `xdex`
- `x1_rpc`
- `historical_db`
- `burn_scanner`
- `mint_scanner`
- `risk_engine`

Source timestamps should be included for freshness-sensitive values.

---

## 10. Failure Rules

Liquidity Scout must fail safely.

It must not:

- substitute remembered prices for unavailable live prices
- invent missing LPs
- invent supply
- infer circulating supply from total supply without independent verification
- invent holder counts
- invent rankings
- invent burn or mint totals
- claim verified net issuance without verified scanner coverage
- report stale values as current without disclosure
- convert source failure into false certainty

When deterministic verification fails, the response should clearly expose the failure.

---

## 11. Roberta Consumption Rules

When Roberta invokes an implemented Liquidity Scout service:

1. Roberta supplies the required query or asset context.
2. Liquidity Scout resolves the asset when necessary.
3. Liquidity Scout obtains or calculates the requested specialist facts.
4. Liquidity Scout returns structured results using the currently implemented service contract.
5. Roberta consumes the returned facts as specialist evidence.
6. Roberta performs any higher-level reasoning or specialist coordination required.
7. Roberta produces the final user-facing synthesis.

Roberta must not invoke a service marked **planned** as though it were already implemented.

For freshness-sensitive market information, Roberta should not substitute remembered values for verified Liquidity Scout values.

---

## 12. Execution Boundary

Liquidity Scout may eventually support controlled execution intelligence such as:

- trade simulation
- transaction preparation
- execution-readiness checks

However:

**Liquidity Scout must not autonomously execute live trades until explicit risk controls, human approval boundaries, and execution safeguards have been implemented and tested.**

`pre_trade_check` is analysis.

It is not authorization.

---

## 13. Service Independence

Liquidity Scout should remain independently testable.

Its core market and risk services should not require Roberta to function.

This allows:

- deterministic unit testing
- API testing
- direct debugging
- service monitoring
- future use by other agents
- clean separation between specialist intelligence and orchestration

Roberta depends on Liquidity Scout's contract.

Liquidity Scout should not depend on Roberta's internal reasoning architecture.

---

## 14. Development Boundary

Liquidity Scout should be developed one layer at a time:

1. Foundation
2. Market Intelligence
3. Tokenomics
4. Scout Risk Engine
5. Roberta Interface
6. Alerts
7. Controlled Execution Intelligence

Integration work should not bypass unfinished lower-level verification layers.

Service status in this contract should be updated as each roadmap phase becomes implemented and tested.

---

## 15. Core Integration Principle

**Liquidity Scout determines what is happening in X1/XDEX markets now.**

**Roberta determines what that information means in the larger context.**

That boundary should remain stable even as both systems gain additional capabilities.
