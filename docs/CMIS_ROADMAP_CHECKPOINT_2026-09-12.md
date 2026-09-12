# CMIS Roadmap Checkpoint — 2026-09-12

This checkpoint supersedes the stale **Live checkpoint** and **Active execution order** sections dated 2026-09-10 in `docs/CMIS_PRODUCT_ROADMAP.md`. Historical evidence records and completed-work sections remain unchanged until the next consolidated rewrite.

## Current accepted CMIS state

Public CMIS main observed for this checkpoint: `503a9e29e51e83bd85c4502c620d6fc38370f943`.

Current public capability contract: **CMIS `1.30.0`**.

Accepted flagship capability includes:

- Instant X1 Scan v6 and field-scoped freshness/history adequacy;
- verified trade price-impact and Large-Trade Discovery;
- wallet-relationship intelligence with observed-transfer/non-ownership boundaries;
- X1 Daily Intelligence Brief inputs/runtime surface;
- cross-chain asset provenance and Bridge-to-XDEX;
- GENIUS Act regulatory evidence;
- Tokenized Equity / RWA intelligence under CMIS 1.30;
- X1 Smart Route Phase 1: `xdex_multi_hop_route_intelligence/v1`;
- X1 Smart Route Phase 2: `xdex_multi_hop_route_snapshot/v1`;
- accepted downstream X1 Scout + protected/public ROBERTA Smart Route adoption now means Smart Route is no longer a CMIS handoff blocker.

`execution_authorized=false` remains invariant.

## X1 Smart Route — CURRENT STATUS

CMIS #681 Phase 1 and Phase 2 are accepted.

Accepted merges:

- Phase 1 / PR #682: `1fe0aad81716d7a80ee9b7cbe2f9049e1ad0c2f8`;
- Phase 2 / PR #685: `503a9e29e51e83bd85c4502c620d6fc38370f943`.

The downstream chain is also accepted through:

`CMIS snapshot -> X1 Scout projection -> protected ROBERTA Pre-Trade -> Ask ROBERTA/website`.

Therefore the old “ACTIVE HANDOFF — X1 Scout / ROBERTA #444” wording is superseded.

Future Smart Route phases are **not current product blockers**:

- cross-DEX evidence only after independently observed/verified non-XDEX venue evidence exists;
- second bounded routing provider/venue before any meaningful multi-candidate route comparison;
- `x1_route_comparison/v1` only after at least two independently bounded candidates exist;
- any `best_route` statement remains bounded to the exact candidate set and exact trade size unless exhaustive X1-wide completeness is independently proven.

## Protected CMIS runtime

Protected `cmis-core` main observed for this checkpoint: `d1a1076192c51f682ed61aaa2dfbc480dab71872`.

Accepted protected freshness/runtime hardening now includes the staged/decoupled liquidity-refresh chain through PR #75:

- post-wait X1 RPC corroboration clock correction;
- early publication of completed liquidity freshness before expensive rolling reconstruction completes;
- independently verified split-liquidity evidence preservation;
- decoupled liquidity refresh while an older rolling reconstruction remains inflight;
- production MRO fix ensuring the decoupled manager is actually active.

These changes do not widen freshness tolerances, provider fact-time claims, source-independence claims, risk semantics, or execution authority.

## Active CMIS execution order

### 1. Support public beta from observed evidence gaps

ROBERTA Cohort 001 is the product flagship. CMIS should not start broad new intelligence work merely because it is technically possible. New CMIS work should be tied to a demonstrated missing-evidence/user-value gap or a required reliability defect.

### 2. Provider qualification / evidence gaps — SUPPORTING

Continue provider verification only where it materially closes an accepted X1 evidence gap.

- X1Scroll #458 / PR #549 remains qualification-only until the required credential-backed live archival proof passes; no production fallback is authorized by deterministic CI alone.
- Theo transport remains externally blocked until a current machine-readable transport contract can be verified.
- delayed-departure longitudinal work remains evidence-waiting rather than a release blocker.
- FortiBlox current price fact-time remains EVIDENCE_INCOMPLETE where the accepted no-payment probe could not prove field-level semantics.

### 3. Future Smart Route expansion — DEFERRED

Do not promote cross-DEX execution, route optimality, price impact, minimum-received/slippage, network fee, or provider fee business semantics without their own independent evidence gates.

### 4. Issue/source hygiene — CONTINUE

Treat historical open issue count as audit debt, not roadmap priority. Close or reconcile superseded umbrellas when accepted later contracts make their original checklist obsolete, while preserving historical evidence/non-claim boundaries.

## Product relationship

CMIS is now sufficiently broad for the first ROBERTA beta cohort. The next commercial uncertainty sits above CMIS: whether users find the accepted intelligence useful enough to return and pay.

CMIS should remain the deterministic evidence authority beneath X1 Scout and ROBERTA rather than becoming a feature factory disconnected from user proof.

Last reconciled: **2026-09-12 America/New_York**.
