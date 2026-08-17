# Roberta Pre-Trade Conversational Accepted Baseline

## Purpose

This document records the Roberta-facing integration consequence of the accepted `docs/PRETRADE_CONVERSATIONAL_RESPONSE_OWNERSHIP.md` contract on `main`.

It does **not** promote `risk_check` or `pre_trade_check` into production-callable CMIS services. The authoritative service status remains `ROBERTA_INTEGRATION_CONTRACT.md`.

## Accepted ownership boundary

CMIS / Liquidity Scout owns deterministic specialist facts and calculations. Roberta owns final user-facing synthesis.

For purchase-suitability and similar questions, Roberta may explain CMIS-returned market, tokenomics, verification, provenance, uncertainty, and risk information that is actually available from an accepted callable service. Roberta must not calculate missing deterministic trade-size, slippage, price-impact, route-quality, fee, verification, or risk results itself.

The stable ownership rule is:

```text
CMIS determines and verifies specialist facts.
Roberta explains what those facts mean to the user.
```

## Default presentation contract

When Roberta receives accepted Scout/CMIS output, the default response should be conversational rather than an internal service dump.

Roberta should:

- lead with the practical conclusion supported by the returned evidence;
- use the exact numerical values CMIS returned;
- surface material uncertainty and missing evidence in plain language;
- distinguish observed market facts from deterministic risk conclusions;
- avoid internal field names, service diagnostics, verification counters, and implementation terminology unless the user asks for technical detail;
- keep the final response in Roberta's voice rather than prefixing it as a raw Liquidity Scout reply.

Roberta may provide a technical mode when requested, but technical presentation must preserve the original CMIS statuses, values, provenance, warnings, errors, and non-promotable states exactly.

## No capability promotion

The accepted conversational ownership contract is an **interface and orchestration rule**, not a new CMIS analytical capability.

As of this baseline:

- `risk_check` remains planned;
- `pre_trade_check` remains planned;
- trade-size-to-liquidity classification remains unavailable until CMIS implements and accepts a deterministic policy;
- price-impact, slippage, route-quality, fee, and transaction-simulation results must remain unavailable unless an accepted CMIS service explicitly returns them;
- Roberta must not infer a `PASS`, `WARN`, or `BLOCK` result from ordinary market facts when CMIS did not produce that risk result.

A user-facing recommendation may still be cautious or conditional when grounded in verified market facts, but it must be phrased as Roberta's reasoning over known evidence rather than represented as a deterministic Scout risk verdict.

## Verification and provenance preservation

When CMIS returns verification or provenance semantics, Roberta must preserve them without recomputation.

In particular, Roberta must not:

- turn `CONFLICT` into agreement;
- turn `INSUFFICIENT_EVIDENCE` into a negative fact;
- strengthen low or partial data quality;
- average conflicting provider values unless CMIS explicitly returned an accepted aggregate;
- manufacture `cmis_promotable=true` or equivalent promotion state;
- infer source independence from labels alone.

## Human-approval and execution boundary

Conversational synthesis does not authorize execution.

Roberta must not interpret a market observation, verification result, future risk result, or future pre-trade analysis as permission to sign, broadcast, swap, bridge, trade, or otherwise move value. Existing human-approval boundaries remain mandatory.

## Cross-chain boundary

This baseline applies to the Roberta/Scout ownership pattern, but it does not make draft cross-chain work production-ready.

Open Solana provider, source, identity, market, supply, or cross-check PRs may inform future interface design only. Roberta must not advertise Solana CMIS support until the relevant capability is accepted on `main`, exposed through a supported callable contract, and covered by the required verification gates.

## Acceptance checks for Roberta

A future Roberta implementation of this contract should prove at least the following:

1. A normal purchase-suitability question returns a concise conversational answer by default rather than a CMIS diagnostic dump.
2. Every displayed numerical market fact exactly matches the accepted Scout/CMIS response.
3. Missing deterministic trade-impact or risk analysis remains explicit rather than being invented.
4. Technical mode can expose structured details without changing CMIS semantics.
5. Planned services are not dispatched as if they were production-callable.
6. No execution authority is inferred or added.

## Source of truth

- `ROBERTA_INTEGRATION_CONTRACT.md` remains the authoritative service-status and integration contract.
- `docs/PRETRADE_CONVERSATIONAL_RESPONSE_OWNERSHIP.md` is the accepted detailed ownership contract that motivated this baseline.
- This document records the narrow Roberta-facing consumption rule created by that accepted ownership contract and must not be used to promote unfinished CMIS roadmap work.
