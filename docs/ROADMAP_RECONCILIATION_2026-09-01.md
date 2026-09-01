# CMIS Roadmap Reconciliation — 2026-09-01

This dated reconciliation advances the living CMIS product roadmap without changing any capability, provider, risk, proof, Scout-reliance, wallet, or execution authority by documentation alone.

## Roadmap state

### Complete / accepted on `main`

- X1 exact-mint identity normalization.
- X1 verified local/all-available historical comparison and pair comparison.
- Bounded verified provider-price history backfill.
- Instant X1 Scan `instant_x1_scan/v1`.
- Deterministic trade-size/pre-trade analysis under analysis-only semantics.
- Evidence Receipts and Proof Score with Proof kept separate from risk.
- Deterministic burn metrics for 1h/24h/7d/30d and period-over-period 24h/7d/30d burn change.
- Verified scanner fact-time coverage wired to burn/tokenomics evidence.
- Deterministic circulating-supply evidence contract.
- Public-shell/private-core migration and historical source cleanup.

### Active / pending acceptance

- **Burn-time valuation — PR #377.** Finish exact historical native/XNT and USD valuation with strict fact-time and completeness rules.
- **Delayed catalog-departure evidence — PR #363.** Exact-head deterministic suite is green; the live delayed-vault evidence gate is not yet green. Preserve the five-event threshold, 900-second horizon, 100-signature-per-vault cap, unique-latest-swap rule, and fail-closed ambiguity treatment.
- **Routed/automated execution diagnostics — issue #374.** PR #376 proved bounded routed target-leg topology, but no TWAP/limit/TP/SL family is accepted without family-specific evidence.
- **Discovery Ledger — public #365 + private `cmis-core` #6.** Public contract and protected implementation remain pending; private runner/startup CI is the current acceptance blocker.
- **Execution-quality evidence.** Build quote-to-executed-swap matching and realized-slippage observations before considering an expected-slippage contract.

## Ordered next actions

1. Complete and review PR #377.
2. Keep #363 collecting/validating exact-head evidence; diagnose failures instead of weakening thresholds.
3. Restore private CI for `cmis-core` #6, then accept public/private Discovery Ledger together.
4. Add a narrow Scout-facing Discovery workflow only after the ledger contract is accepted.
5. Build deterministic WHAT CHANGED? and Early Warning evidence on accepted history/Discovery primitives.
6. Build execution-quality statistics from persistent, comparable executed-trade evidence.
7. Continue provider-gap and Oracle work only through explicit evidence contracts.
8. Keep Solana read-only/secondary and execution unauthorized.

## Roberta handoff

CMIS owns evidence and deterministic facts. Roberta owns product orchestration and Human/Machine presentation. Burn, Discovery, Early Warning, and execution-quality outputs become Roberta-consumable only through separately accepted X1 Scout/CMIS contracts; roadmap intent is not capability promotion.

`execution_authorized=false`
