# Roberta Runtime Capability Accepted Baseline

## Purpose

This document records the Roberta-facing capability boundary observed on current `main` at commit `c0fd7589cf3f113a27d2b632cb22e6e15a2a3e6f`.

It exists because `ROBERTA_INTEGRATION_CONTRACT.md` currently understates several runtime capabilities that are already present on `main`. Until the authoritative contract is synchronized, Roberta must use the narrower rules below rather than extrapolating from implementation details.

## Accepted X1 runtime services

The current CMIS gateway/runtime advertises and composes the following X1 services:

- `asset_lookup`
- `market_report`
- `rank`
- `historical_compare`
- `tokenomics`
- `risk_check`
- `pre_trade_check`
- `verification_evidence`

Additional accepted trade-verification/activity services exist in the trade-aware runtime, but they are specialist CMIS services and should not be surfaced as general Roberta capabilities unless the Roberta contract explicitly adopts them.

## `risk_check` consumption boundary

`risk_check` is implemented in the current X1 runtime and may collect bounded token-activity evidence plus a verified historical comparison before invoking the deterministic risk service.

Roberta may consume the returned CMIS risk result, including its recommendation, flags, reasons, warnings, sources, and uncertainty.

Roberta must not:

- recreate the risk score or recommendation;
- infer missing risk evidence from ordinary market facts;
- strengthen a partial result into a complete result;
- reinterpret missing provider evidence as a passing check;
- treat a risk result as execution authorization.

## `pre_trade_check` consumption boundary

`pre_trade_check` is implemented in the current X1 runtime, but its scope is narrower than the desired future trade-impact analysis described in `docs/PRETRADE_CONVERSATIONAL_RESPONSE_OWNERSHIP.md`.

The current wrapper consumes a deterministic `risk_check` result plus trade context and returns analysis-only PASS/WARN/BLOCK semantics. It does not itself perform routing, transaction simulation, wallet work, signing, broadcasting, or execution.

The accepted current implementation must **not** be represented as having completed the future roadmap requirements for deterministic trade-size-to-liquidity classification, price impact, slippage, route quality, fees, or transaction simulation unless those fields are explicitly returned by a later accepted CMIS implementation.

Roberta therefore may say that CMIS produced a pre-trade risk result, but must separately disclose unavailable trade-impact analysis when it was not evaluated.

## Conversational synthesis boundary

The accepted `docs/PRETRADE_CONVERSATIONAL_RESPONSE_OWNERSHIP.md` contract establishes the presentation rule:

```text
CMIS determines and verifies specialist facts.
Roberta explains what those facts mean to the user.
```

For normal user questions, Roberta should provide a conversational answer rather than a raw CMIS diagnostic dump. Numerical facts must match CMIS exactly, material uncertainty must remain visible, and internal service terminology should be hidden by default unless technical detail is requested.

A more natural answer does not authorize Roberta to invent missing slippage, price-impact, route, fee, simulation, verification, or risk facts.

## `verification_evidence` consumption boundary

Current `main` includes an external read-only verification-evidence gateway. The accepted selector surface is deliberately narrow:

- exact `evidence_id`; or
- exact `fact_type + subject_id`.

The service does not accept provider payloads, verifier objects, free-form asset inference, or a caller-selected database path.

Roberta may consume persisted CMIS verification evidence and preserve its verification, provenance, source-role, observation-time, data-quality, conflict, and promotion semantics.

Roberta must not:

- duplicate the verifier;
- infer source independence from labels;
- turn `CONFLICT` into agreement;
- turn `INSUFFICIENT_EVIDENCE` into a negative fact;
- manufacture a promoted fact from non-promotable evidence.

## Solana boundary

PR #101 is merged on this baseline and adds a narrowly eligible Solana `asset_lookup` path for **exact mint-address identity only**.

This capability is deployment-gated:

- an explicit Solana RPC provider must be injected;
- the default production runtime remains Solana-disabled/fail-closed;
- symbol/name discovery is unavailable;
- Solana market reports, tokenomics, history, risk, pre-trade analysis, routing, swaps, and execution remain unavailable unless separately accepted later.

Roberta may therefore model Solana exact-mint identity as a conditional capability, not as general Solana CMIS support.

If the deployment has no configured Solana RPC provider, Roberta must preserve the returned `unavailable` state rather than falling back to X1 or guessing identity.

## Service/status rule for Roberta

Roberta should distinguish three different questions:

1. **Does deterministic CMIS logic exist?**
2. **Is the service composed into the accepted runtime?**
3. **Is the capability actually available in this deployment for this chain/request?**

Only the third determines whether Roberta may claim that the capability is usable now.

An accepted runtime service can still return `unavailable`, `partial`, `ambiguous`, `conflict`, or `error`. Runtime registration alone is not proof that a requested fact is available or verified.

## Human approval and execution boundary

No accepted capability in this baseline authorizes value movement.

Roberta must not interpret market facts, risk results, pre-trade analysis, verification evidence, or Solana identity lookup as permission to sign, broadcast, swap, bridge, trade, or otherwise move value.

Human approval and future execution safeguards remain separate gates.

## Authoritative contract synchronization required

`ROBERTA_INTEGRATION_CONTRACT.md` currently still labels `risk_check` and `pre_trade_check` as planned and `verification_evidence` as wrapper-planned. Those status lines are stale relative to the current accepted runtime.

A follow-up synchronization should update the authoritative contract to:

- mark X1 `risk_check` as implemented/runtime-callable while preserving evidence-completeness rules;
- mark X1 `pre_trade_check` as implemented/runtime-callable but explicitly scope it as current risk-based analysis rather than completed trade-impact analysis;
- mark X1 `verification_evidence` as implemented/runtime-callable with exact-selector-only lookup;
- record Solana `asset_lookup` as conditional exact-mint-only capability, not general Solana support;
- preserve the conversational synthesis ownership contract;
- retain all human-approval and no-autonomous-execution boundaries.

No open/draft PR should be promoted by that synchronization unless it is first merged into `main` and its relevant validation gates are satisfied.
