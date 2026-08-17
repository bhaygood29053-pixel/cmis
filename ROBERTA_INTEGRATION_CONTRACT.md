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

Roberta must not duplicate Liquidity Scout's deterministic calculations in order to manufacture a second opinion. Independent verification belongs in CMIS/Liquidity Scout, where source identity, units, semantics, freshness, and provenance can be tested deterministically.

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

- **implemented core** — reusable deterministic Liquidity Scout logic exists on the accepted integration baseline and is independently testable;
- **draft core** — reusable logic exists only in an open or stacked development branch/PR and is not yet a Roberta-consumable production capability;
- **wrapper planned** — core capability exists, but the final Roberta-facing service envelope is not yet complete;
- **planned** — capability belongs to a future roadmap phase and must not be treated as live.

A capability in **draft core** status may inform interface design and test fixtures, but Roberta must not present it to users as an available or verified production service until it is accepted into the integration baseline and its relevant verification gates pass.

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

### `verification_evidence`

**Status:** implemented core on the accepted CMIS trust baseline; Roberta-facing wrapper, sanitized evidence ledger, and exact lookup are in draft development and production invocation remains unavailable.

Target purpose:

- expose the evidence and provenance behind an important CMIS fact
- expose whether independent sources agree, conflict, or are insufficient
- expose identity, semantics, units, freshness, and verification state without forcing Roberta to reproduce CMIS calculations

Target result may include:

- fact identity
- normalized value and unit when verified
- source names and source roles
- observation timestamps
- block/slot provenance when available
- calculation/service version
- verification flags
- deterministic comparison outcome such as `AGREEMENT`, `CONFLICT`, or `INSUFFICIENT_EVIDENCE`
- explainable data-quality level and reasons
- CMIS-promotion state
- stable evidence reference when loaded from the CMIS evidence ledger

The draft service architecture keeps fact verification, persistence, and lookup separate:

```text
fact-specific CMIS verifier
        ↓
verification_evidence wrapper
        ↓
sanitized content-addressed evidence ledger
        ↓
exact read-only lookup
        ↓
future CMISGateway dispatch
        ↓
Roberta
```

The future Roberta-facing request must select evidence using exactly one of these modes:

1. a stable CMIS `evidence_id`; or
2. an exact CMIS fact identity using `fact_type` + `subject_id` to request the latest stored record for that fact.

Roberta must **not**:

- submit raw provider observations or verifier results to this service;
- choose or rewrite verification/data-quality/promotion state;
- ask CMIS to guess which evidence belongs to a free-form asset name;
- reproduce the underlying comparison to create a second opinion;
- treat a stored `CONFLICT` or `INSUFFICIENT_EVIDENCE` result as a verified value.

A future lookup response may add an `evidence_ref` containing the stable `evidence_id` and ledger `recorded_at` time. It must otherwise preserve the stored CMIS verification result rather than recalculating it.

The underlying CMIS trust primitives are accepted core and are documented in `ROBERTA_CMIS_ACCEPTED_BASELINE.md`. The wrapper/ledger/lookup development stack is not yet wired into `CMISGateway.SUPPORTED_SERVICES`; therefore Roberta must still treat `verification_evidence` as unavailable for production invocation. Draft implementation does not satisfy the runtime eligibility gate by itself.

### `risk_check`

**Status:** planned for the Scout Risk Engine phase.

Returns deterministic market-risk analysis when implemented.

Possible fields include:

- PASS / WARN / BLOCK
- reason codes
- liquidity risk
- concentration risk
- authority risk
- verification uncertainty
- anomaly warnings

### `pre_trade_check`

**Status:** planned for the execution-safety phase.

Returns deterministic pre-trade market-risk analysis when implemented.

It does **not** authorize execution.

Roberta must treat it as informational risk analysis only unless a future human-approved execution architecture explicitly defines otherwise.

---

## 6. Response Contract

Roberta-facing services should converge on a stable envelope:

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

Supported statuses:

- `ok`
- `partial`
- `unavailable`
- `ambiguous`
- `error`

A response must preserve:

- source identity
- timestamps
- confidence or uncertainty
- warnings
- explicit errors

---

## 7. Verification Boundary

Roberta may interpret verified CMIS results.

Roberta must not manufacture stronger facts than the service returned.

Examples:

- `AGREEMENT` with `cmis_promotable=true` may be consumed as the CMIS-verified fact represented by that evidence record;
- `AGREEMENT` with `cmis_promotable=false` remains non-promoted evidence even if the numerical observations match;
- `CONFLICT` must remain conflict and must not be averaged by Roberta;
- `INSUFFICIENT_EVIDENCE` must remain insufficient rather than being completed from memory or a nearby conversational value;
- missing freshness, unit semantics, identity proof, or source independence must remain explicit uncertainty.

---

## 8. Change Control

When CMIS capabilities change, update this contract in the same integration sequence:

```text
CMIS implementation / tests
        ↓
CMIS architecture / accepted baseline
        ↓
Roberta integration contract
        ↓
Roberta project synchronization
```

Roberta should consume only the accepted contract relevant to its deployment and must not silently infer capability from an open development branch.
