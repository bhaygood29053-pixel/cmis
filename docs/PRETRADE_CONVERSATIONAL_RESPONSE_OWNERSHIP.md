# Roberta–CMIS Pre-Trade UX Ownership Contract

## Problem

A user asked Roberta on MoltGrid:

> Is it ok to purchase $500 of AGI?

The response exposed an internal CMIS-style diagnostic report directly to the user, including service statuses, verified-check counts, missing evidence, and execution-authorization language. The result was technically informative but sounded like a debug console rather than a normal assistant.

The response also revealed a separate analytical gap: CMIS carried the `$500` notional as context but did not yet evaluate whether that trade size was appropriate relative to verified liquidity, expected slippage, price impact, route quality, fees, or transaction simulation.

This issue therefore has **two owners**:

1. **Roberta owns the user-facing conversational experience.**
2. **CMIS/Liquidity Scout owns deterministic pre-trade calculations and evidence.**

Neither project should take over the other's responsibility.

---

## Architecture Rule

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
Roberta conversational synthesis
  ↓
Normal human answer
```

### CMIS answers

> What do the verified numbers and deterministic policies say?

### Roberta answers

> What does that mean for the person who asked the question?

Roberta must not become a second risk engine. CMIS must not become a conversational assistant.

---

# Roberta Responsibilities

## R1 — Add a conversational response synthesis layer

Roberta must translate Scout/CMIS structured results into a natural answer before sending a MoltGrid/Signal response.

For a question such as:

> Is it ok to purchase $500 of AGI?

Roberta should lead with a direct answer, explain the most important evidence in plain language, identify material uncertainty, and give a practical next step.

Example target style:

> I'd be cautious about buying the full $500 of AGI at once. AGI currently has about $3,380 in reported liquidity and only about $124 in 24-hour volume, so a $500 order is large relative to the current market. The token did not trigger a major safety failure in the checks I could verify, but I still need trade-impact and slippage analysis before I'd call the full $500 purchase low-risk. A smaller or staged purchase would be safer until that is checked.

The wording may vary, but it must sound like Roberta speaking to a person rather than returning an internal service report.

## R2 — Preserve CMIS truth without recomputation

Roberta may:

- summarize deterministic results;
- prioritize the most relevant facts;
- translate statuses such as `WARN`, `PARTIAL`, or `INSUFFICIENT_EVIDENCE` into normal language;
- explain uncertainty;
- request additional Scout/CMIS analysis;
- provide practical next steps that are explicitly grounded in CMIS results.

Roberta must not:

- invent slippage, price impact, route quality, or fees;
- recalculate or strengthen CMIS confidence;
- convert `WARN` or insufficient evidence into `PASS`;
- average conflicting providers;
- manufacture verified facts;
- treat a provider marketing label as deterministic truth.

## R3 — Hide internal diagnostics by default

The default user response should not expose terms such as:

- `CMIS pre-trade analysis`;
- `Market service: OK`;
- `Risk evidence verified: 6/8`;
- `risk core`;
- `cmis_promotable`;
- service envelopes;
- execution internals that are not directly relevant to the user's question.

Roberta may expose those details only when the user explicitly asks for technical details, diagnostics, evidence, or a full report.

## R4 — Support two presentation modes

### Default: Conversational Mode

Short, clear, natural, decision-oriented.

### Optional: Technical Mode

When requested, show the underlying market, tokenomics, risk, verification, trade-size, slippage, price-impact, route, and missing-evidence details without changing CMIS semantics.

## R5 — Keep the final voice as Roberta

Do not prefix normal responses with `Liquidity Scout reply:`. Roberta may say that she checked Liquidity Scout when useful, but the final response should remain in Roberta's voice.

## Roberta acceptance criteria

Roberta's task is complete when all of the following are true:

- The AGI `$500` test question returns a normal conversational answer by default.
- The answer leads with a direct recommendation or caution statement rather than a service report.
- All numerical facts used in the answer match the Scout/CMIS response exactly.
- Missing evidence remains explicit and is never silently converted into confidence.
- Internal CMIS diagnostic terminology is hidden by default.
- A technical-detail request can still expose the structured analysis.
- Existing X1 Scout/CMIS trust boundaries remain intact.
- Automated tests cover conversational and technical modes.

---

# CMIS / Liquidity Scout Responsibilities

## C1 — Make the proposed trade amount analytically meaningful

CMIS must stop merely carrying `notional_usd` as context. It should deterministically compare the requested trade size with verified market liquidity when the necessary evidence exists.

At minimum, add a deterministic field equivalent to:

```text
notional_to_liquidity_ratio = requested_notional_usd / verified_liquidity_usd
```

For the observed example:

```text
$500 / $3,380 ≈ 14.8%
```

The exact ratio should be returned as structured CMIS evidence. Roberta may explain it but must not be the component that calculates or classifies it.

## C2 — Add an explicit trade-size policy

CMIS should classify trade-size risk using documented, configurable, deterministic thresholds.

The policy must:

- have explicit thresholds;
- have no hidden defaults masquerading as universal market truth;
- fail closed when required liquidity evidence is unavailable or unverified;
- preserve the exact policy version/thresholds used in the result.

Possible labels may include `LOW`, `MODERATE`, `HIGH`, and `VERY_HIGH`, but the final thresholds must be deliberately defined and tested before production use.

## C3 — Add pool/route-level price-impact analysis

When sufficient verified pool/reserve evidence exists, CMIS should evaluate the proposed trade against viable pools/routes and return deterministic estimates for:

- available route(s);
- relevant reserves/depth;
- expected execution price;
- expected amount received;
- price impact;
- DEX/pool fees;
- route quality or explicit route insufficiency.

CMIS must not claim asset-wide route quality from one pool unless the scope is explicitly limited to that pool/venue.

## C4 — Add slippage analysis

CMIS should estimate or bound expected slippage only when the required route/reserve/quote evidence is available and its semantics are verified.

Missing quote or reserve semantics must remain `unavailable` / insufficient evidence, not zero.

## C5 — Keep execution separate

This work is analysis only. It must not enable:

- signing;
- broadcasting;
- wallet custody;
- autonomous execution;
- value movement.

Existing human-approval and future controlled-execution boundaries remain separate.

## CMIS acceptance criteria

CMIS's task is complete when all of the following are true:

- `pre_trade_check` uses the requested trade amount as an evaluated input rather than context only.
- A verified notional-to-liquidity ratio is returned when verified liquidity is available.
- Trade-size classification is deterministic, policy-backed, and versioned.
- Missing liquidity evidence fails closed.
- Price-impact and slippage fields are either deterministically evaluated from verified route/pool evidence or explicitly unavailable.
- Route/fee evidence preserves provider, pool, venue, observation time, and scope.
- No fake zeros or inferred totals are introduced.
- No execution authority is added.
- Automated tests cover small, medium, and market-large trade sizes plus missing/conflicting evidence.

---

# Shared Interface Contract

CMIS should return machine-readable evidence. Roberta should consume it without recomputing trust.

A future structured pre-trade result should be able to expose fields conceptually similar to:

```text
trade:
  side
  notional_usd

market:
  verified_price_usd
  verified_liquidity_usd
  verified_volume_24h_usd
  lp_count

trade_size:
  notional_to_liquidity_ratio
  policy_version
  assessment
  evidence_status

route_analysis:
  status
  route_scope
  estimated_execution_price
  estimated_price_impact_percent
  estimated_slippage_percent
  estimated_fees

risk:
  recommendation
  verified_evidence
  missing_evidence
```

The exact schema may evolve, but ownership must not:

- CMIS determines and verifies these facts.
- Roberta explains them.

---

# Required Regression Questions

Both projects should use at least these user-facing scenarios:

1. `Is it ok to purchase $50 of AGI?`
2. `Is it ok to purchase $500 of AGI?`
3. `Would $2,000 move the AGI market too much?`
4. `Should I sell $1,000 of AGI?`
5. `Show me the technical analysis for that trade.`
6. Same questions with missing liquidity evidence.
7. Same questions with conflicting market evidence.

Roberta tests should evaluate **presentation and truth preservation**.

CMIS tests should evaluate **deterministic calculations, evidence scope, and fail-closed behavior**.

---

# Completion and Handoff

## Roberta is done when

The conversational synthesis and technical-detail modes meet the Roberta acceptance criteria and are merged into the accepted Roberta runtime.

## CMIS is done when

Trade-size evaluation and the agreed pre-trade intelligence fields meet the CMIS acceptance criteria and are merged into the accepted Liquidity Scout/CMIS runtime.

## Cross-project final integration is done when

Roberta consumes the new CMIS pre-trade fields without recomputing them and the `$500 AGI` regression scenario produces a natural answer grounded in the deterministic trade-size/impact evidence.

---

## Non-goal

Do not solve this problem by making CMIS write conversational prose or by allowing Roberta to independently invent market-risk calculations. The purpose of this contract is to preserve the architecture:

**CMIS owns deterministic truth. Roberta owns the human conversation.**
