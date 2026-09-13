# CMIS Roadmap Checkpoint — 2026-09-13

This checkpoint supersedes the active-execution ordering in `docs/CMIS_ROADMAP_CHECKPOINT_2026-09-12.md` where it conflicts with newer real-user Cohort 001 evidence. Historical accepted capability records remain unchanged.

## Current priority

**CMIS #686 — bounded X1 wallet-pair relationship discovery v1** is the current flagship CMIS gap because it was exposed by a real ROBERTA Cohort 001 failure.

The accepted `wallet_relationship_intelligence/v1` remains valid and unchanged: it verifies one caller-selected finalized direct token transfer. It does not answer the broader fixed cohort question asking whether two wallets directly interacted and what bounded evidence connects them.

## Required #686 result

For an exact X1 wallet pair, provide bounded deterministic read-only discovery that can report only what accepted evidence proves, including where available:

- observed direct-interaction presence within the covered evidence;
- exact connecting signatures/transactions;
- direction, asset mint, amount/units when verified;
- bounded interaction count;
- earliest/latest verified observed interaction within coverage;
- explicit coverage, completeness, pagination/truncation, provenance, and evidence limitations.

Absence must mean `NO_OBSERVED_INTERACTION_IN_COVERED_EVIDENCE`, not “never interacted,” unless complete history is separately proven.

Do not infer ownership, identity, coordination, intent, manipulation, bot/whale status, risk severity, or complete relationship graphs.

## Downstream handoff

After #686 is independently accepted and promoted:

`CMIS #686 -> ROBERTA #472 -> X1 Scout handshake/projection -> protected ROBERTA adoption -> Human response -> rebuild runtime -> rerun frozen C02`

## Accepted CMIS baseline remains

- CMIS 1.30 Tokenized Equity / RWA public/protected parity;
- Smart Route Phase 1 `xdex_multi_hop_route_intelligence/v1`;
- Smart Route Phase 2 `xdex_multi_hop_route_snapshot/v1`;
- downstream Smart Route adoption through X1 Scout / ROBERTA / Ask ROBERTA;
- cross-chain provenance / Bridge-to-XDEX;
- verified wallet trade, price-impact, Large-Trade Discovery, discovery/history/burn and other previously accepted read-only intelligence.

## Supporting / deferred

- CMIS #681 Smart Route Phase 3/4 cross-DEX comparison — future/evidence-driven, not a beta blocker.
- CMIS #317 Jupiter/Pyth independence — valuable Solana source-quality work, not the current X1 beta blocker.
- CMIS #381 delayed-departure pattern — evidence-waiting.
- CMIS #458 / PR #549 X1Scroll archival qualification — credential-dependent; do not promote without live proof.
- Theo transport #422 — blocked on exact reproducible live machine transport contract.

## Repository checkpoint

Observed pre-checkpoint `cmis` main: `3bef0574f220e94702c2df332da54bee108d93ce`.

This dated checkpoint is documentation/source-of-truth reconciliation only; it does not itself promote a provider, service, Proof Score, Scout reliance, risk conclusion, wallet authority, or execution authority.

`execution_authorized=false`.
