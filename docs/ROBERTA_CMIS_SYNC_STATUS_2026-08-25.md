# Roberta ↔ CMIS Documentation Sync Status — 2026-08-25

This status note records the paired documentation reconciliation performed against current accepted `main` behavior.

## Verified aligned invariants

- `User -> Roberta -> Chain Scout -> CMIS -> Chain Provider`.
- Roberta owns orchestration and final synthesis.
- Chain Scouts interpret chain-specific results and do not manufacture facts.
- CMIS owns deterministic verified facts, evidence, Proof Scores, risk, capability state, historical intelligence, and bounded analysis-only pre-trade calculations.
- Providers remain beneath CMIS.
- Fresh accepted CMIS/provider facts override remembered live values.
- Missing evidence remains unknown; it is not zero.
- Proof Score remains separate from risk.
- `pre_trade_check` remains analysis-only with `execution_authorized=false`.
- `liquidity_scout` may remain as a compatibility identifier during incremental migration.
- Core Phase 11 `intelligence_foundation` remains non-promoted.
- The separately accepted Phase 12 X1 `concentration_change_intelligence/v1` wrapper remains the only promoted Verified Intelligence wrapper and matches Roberta on contract version, chain, scope, accepted conclusion, Scout reliance, read-only state, and `execution_authorized=false`.

## Current non-promoted CMIS intelligence foundations

Complete on CMIS `main` but not public/Scout-promoted:

- deterministic descriptive concentration-direction classification;
- direct wallet-relationship evidence with explicit non-ownership semantics;
- concentration-threshold alert evidence.

There is no currently accepted next public intelligence/alert promotion.

## Pending work outside this sync

Open CMIS provider-gap work remains read-only/fail-closed and is not accepted capability until merged after its evidence/review gates. Roberta Controlled Execution remains locked/not started.
