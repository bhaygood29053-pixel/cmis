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

## Live GitHub reconciliation — 2026-09-01 11:20 America/New_York

This section is the authoritative live reconciliation for the current GitHub state and supersedes stale status text elsewhere in this dated note.

### Accepted on `main`
- Deterministic historical burn-time valuation is **accepted**; CMIS PR #377 merged on 2026-09-01.
- Burn metrics, period-over-period burn change, scanner fact-time coverage, circulating-supply evidence, exact-mint identity, historical compare/backfill, Instant X1 Scan, Evidence Receipts/Proof Score, and analysis-only pre-trade foundations remain accepted.
- Public-shell/private-core migration remains complete.

### Active gates
- **PR #363 — delayed catalog-departure evidence:** open, mergeable but unstable; head `7f40ca53f7ad707eaa8987f59f8627beefe77168`. Deterministic Liquidity Scout tests pass. The live **X1.Ninja Delayed Vault Departure Evidence** workflow is still in progress. Keep the 5 independent departures, 900-second lookback, max 100 signatures per exact vault, unique-latest-swap rule, fail-closed ambiguity treatment, monitoring up to 150 pools, up to 400 snapshots, and 40 price-only candidate collection target. Do not weaken the evidence threshold.
- **PR #365 + private `cmis-core` PR #6 — Discovery Ledger:** public PR #365 is clean and its public tests pass; private PR #6 is mergeable but unstable and private-core CI is failing. The pair is not accepted until the protected implementation gate passes.
- **Issue #374 — routed/automated-order families:** diagnostic only. No TWAP/limit/TP/SL family classification is promoted.
- **Execution-quality evidence:** remains future work; realized slippage must be based on comparable quote-to-executed-swap evidence before any expected-slippage contract.

### Ordered next actions
1. Keep #363 running and diagnose evidence failures without reducing thresholds.
2. Repair `cmis-core` #6 private-core CI, then accept #365/#6 together.
3. After Discovery Ledger acceptance, expose a narrow Scout-facing Discovery workflow.
4. Build deterministic WHAT CHANGED? and Early Warning evidence on accepted history/Discovery primitives.
5. Accumulate quote-to-executed-swap and realized-slippage evidence.
6. Keep Solana secondary/read-only and keep Controlled Execution unauthorized.

`execution_authorized=false`
