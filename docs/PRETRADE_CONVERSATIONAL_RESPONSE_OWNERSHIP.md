# Roberta–CMIS Pre-Trade UX Ownership Contract

## Purpose

This document records the ownership split created after an early prototype response to:

> Is it ok to purchase $500 of AGI?

The early response exposed internal CMIS-style diagnostics directly and, at that time, carried the requested notional mostly as context rather than evaluating trade size against verified liquidity.

Both gaps have since been addressed in the accepted architecture. The historical **Liquidity Scout** name refers to the prototype/repository history; current ownership is:

1. **Roberta owns the user-facing conversational experience.**
2. **CMIS owns deterministic pre-trade calculations, evidence, proof, and fail-closed capability state.**
3. **The relevant Chain Scout requests/interprets CMIS work without reproducing provider calculations.**

```text
User
  ↓
Roberta
  ↓
X1 Scout / Solana Scout
  ↓
CMIS
  ↓
Structured deterministic evidence
  ↓
Chain Scout interpretation
  ↓
Roberta conversational synthesis
```

CMIS answers:

> What do the verified numbers, evidence contracts, and deterministic policies support?

Roberta answers:

> What does that mean for the person who asked the question?

Roberta must not become a second risk/market engine. CMIS must not become the conversational voice.

---

## Roberta responsibilities

### Conversational synthesis

Roberta should lead with the useful conclusion/caution, explain the most important evidence in plain language, distinguish risk from evidence quality, identify material uncertainty, and provide practical next steps without dumping raw service envelopes by default.

### Truth preservation

Roberta may summarize, prioritize, explain, and request additional Scout/CMIS analysis.

Roberta must not:

- invent or recompute price, liquidity, slippage, price impact, route, fees, proof strength, or deterministic risk;
- strengthen incomplete evidence;
- convert `WARN`, `BLOCK`, conflict, or insufficient evidence into a stronger result;
- average incompatible providers;
- manufacture verified facts;
- treat a provider label as CMIS-verified truth.

### Progressive disclosure

Default mode should be conversational. Technical details, evidence receipts, proof categories, source diagnostics, and structured fields should be exposed only when requested or necessary to explain a material limitation.

### Final voice

Roberta is the normal user-facing voice. Do not prefix current production answers with `Liquidity Scout reply:`. That is historical prototype wording.

---

## CMIS responsibilities

### Trade-size analysis — COMPLETE

CMIS evaluates requested notional against verified liquidity where the evidence contract permits:

```text
notional_to_liquidity_ratio = requested_notional_usd / verified_liquidity_usd
```

The ratio is calculated by CMIS and returned as structured evidence; Roberta may explain it but does not recalculate it.

### Explicit trade-size policy — COMPLETE

The production X1 path has a documented/versioned deterministic trade-size policy with explicit classification bands. Missing or conflicting liquidity fails closed. Policy thresholds are policy choices, not universal market truth.

See [`CMIS_PRETRADE_POLICY.md`](./CMIS_PRETRADE_POLICY.md).

### Route-scoped price impact and fee evidence — BOUNDED / AVAILABLE WHERE EXACT GATES PASS

CMIS now has a hardened internal route-evidence seam. Selected route-scoped price-impact and fee facts may become usable only when exact route identity, accepted source, freshness, semantic, unit, value-shape, and proof-basis gates all pass.

The route must explicitly bind:

- token-in mint;
- token-out mint;
- pool;
- AMM config.

One pool/route cannot silently become asset-wide route quality.

For the accepted pinned XENCAT/native-XNT historical scope, completed-swap evidence strongly corroborates the 2800-ppm / 0.28% execution model. The separate 3000-ppm quote baseline is not presented as a hidden execution fee.

### Slippage — STILL DISTINCT / FAIL-CLOSED

XDEX quote slippage tolerance/minimum-received semantics have bounded verified/corroborated behavior, but quote slippage tolerance is **not** an expected execution-slippage estimate.

Expected execution slippage remains unavailable until a separately accepted execution-observation contract proves it.

### Still unavailable unless separately proven

- route quality / optimality;
- fill quality;
- bridge dependency where route representation is not proven;
- transaction simulation;
- generic execution quality;
- universal execution semantics.

Missing evidence remains unavailable/null, never zero-filled or guessed.

### Execution remains separate

Current pre-trade work does not enable:

- transaction preparation for execution;
- signing;
- broadcasting;
- custody;
- autonomous trading;
- bridge transfer;
- value movement.

Every current result preserves:

```text
analysis_only = true
execution_authorized = false
```

A `PASS` means only that the checks actually performed did not produce a warning/block. It is not a statement that a trade is safe and is never authorization to trade.

---

## Shared interface principle

CMIS returns machine-readable deterministic evidence. The Chain Scout preserves/interprets the chain-specific result. Roberta explains it without recomputing trust.

Conceptual pre-trade output may include:

```text
trade:
  side
  notional_usd

market:
  verified_price_usd
  verified_liquidity_usd
  verified_volume_24h_usd

trade_size:
  notional_to_liquidity_ratio
  policy_name
  policy_version
  classification
  evidence_status

route_analysis:
  status
  route_scope
  estimated_price_impact_percent     # only when accepted proof gates pass
  estimated_slippage_percent         # unavailable unless separately proven
  estimated_fees                     # only accepted bounded fee fields

risk:
  recommendation
  evidence_quality
  missing_evidence
```

The exact schema may evolve, but ownership does not:

- **CMIS determines/verifies deterministic facts.**
- **Chain Scouts preserve chain-specific evidence and meaning.**
- **Roberta explains the result to the user.**

---

## Regression questions

Keep user-facing coverage for scenarios such as:

1. `Is it ok to purchase $50 of AGI?`
2. `Is it ok to purchase $500 of AGI?`
3. `Would $2,000 move the AGI market too much?`
4. `Should I sell $1,000 of AGI?`
5. `Show me the technical analysis for that trade.`
6. The same questions with missing liquidity evidence.
7. The same questions with conflicting evidence.
8. Exact route evidence present versus stale/mismatched route evidence.
9. Quote slippage tolerance supplied as if it were expected execution slippage—the system must reject that semantic substitution.
10. Fee evidence containing quote-layer deductions as if they were executed fees—the system must fail closed.

Roberta tests evaluate presentation and truth preservation. CMIS tests evaluate deterministic calculations, proof/scope/freshness boundaries, and fail-closed behavior.

---

## Core principle

**CMIS owns deterministic truth. Chain Scouts preserve chain-specific evidence. Roberta owns the human conversation.**
