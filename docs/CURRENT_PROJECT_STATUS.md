# Current CMIS Project Status

Current reconciliation: **2026-09-05 19:35 America/New_York**.

Read in this order:

1. `../ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md` — mirrored four-repository authority baseline.
2. `CMIS_PRODUCT_ROADMAP.md` — authoritative living CMIS roadmap.
3. `CHECKPOINT_2026-09-05_FOUR_REPOS.md` — earlier September 5 checkpoint.
4. Earlier dated reconciliation/status files — historical snapshots only.

## Accepted CMIS platform

- current capability contract `1.20.0`;
- Instant X1 Scan v3;
- Burn Intelligence;
- Discovery Intelligence;
- field-scoped current-market freshness v1;
- pull-only Concentration Warning Intelligence;
- #409 Bridge Supply + current/prior 24h/7d/30d Flow Intelligence;
- #410 Bridge-to-XDEX Utilization Intelligence;
- #482 public/Scout promotion of `bridge_to_xdex_utilization/v1` through public PR #487 + protected `cmis-core` PR #23;
- #491 public/Scout promotion of `cross_chain_asset_provenance/v1` through public PR #493 + protected `cmis-core` PR #24;
- #461 X1.Ninja USD-liquidity semantics through merged PR #470;
- internal CMIS Web Discovery v1-v11 through PR #497.

## Active flagship gate

### #459 — current liquidity freshness

Issue #461 is closed; liquidity semantics are no longer the blocker.

PR #500 is the active implementation candidate for a fail-closed `x1_current_market_freshness/v2` composition. It requires bounded exact contributing LP identity, fresh X1 RPC reserve reproduction for each contributing wrapped-XNT pool, same-fact XNT/USDC.X valuation, current USDC.X/USD equivalence, and aggregate reproduced-liquidity agreement.

**Current acceptance status: RED / NOT MERGE-READY.**

At the current PR #500 head `af1478fd1ab9e8e8f02671debae235dff0d27078`:

- dedicated `X1.Ninja Liquidity Freshness Evidence` failed during deterministic coverage;
- the standard `Liquidity Scout Tests` public-shell job also failed at `Test X1.Ninja aggregate liquidity freshness v1`;
- Bridge/Warp regression workflows on the same head remain green;
- rolling 24h volume and rolling transaction freshness remain unverified.

No roadmap text may promote PR #500 until its deterministic and live acceptance gates are green and the required public/protected promotion work is accepted.

## Cross-chain / ROBERTA dependency

The earlier cross-chain release chain is complete:

`#410 -> #482 -> cmis-core #23 -> #491 -> cmis-core #24 -> ROBERTA #314`

ROBERTA #314 is closed. The accepted cross-chain surfaces remain descriptive and scope-bounded; they do not imply whole-X1 DEX coverage, adoption, causality, backing/solvency, or automatic risk.

## Web Discovery

CMIS Web Discovery v1-v11 is accepted internally through PR #497.

It covers bounded discovery/reconciliation across X1 Explorer, XDEX, and X1.Ninja, but every discovery result remains subordinate to CMIS verification. Discovery does not create source independence, verified market truth, risk, public-service promotion, Scout reliance, or execution authority by itself.

## Next product intelligence

### #498 — Verified Trade Attribution + Pool Price Impact

Issue #498 is open and is the next major read-only intelligence build behind the active #459 freshness gate.

The proposed `trade_price_impact_intelligence/v1` may preserve exact transaction/wallet/pool/time, trade size, verified measured-window volume contribution, pre-trade spot price, average execution price, post-trade pool spot price, and next verified trade price when those facts are deterministically proven.

It must not widen one AMM pool's state transition into whole-market causality, real-world wallet identity, intent, whale/insider/manipulator labels, coordination, automatic risk, a recommendation, or execution.

## Parallel / maintenance work

- #444 Instant X1 Scan evidence completion;
- #458 X1Scroll historical transaction fallback qualification;
- #30 provider-gap tracking;
- #363/#381 delayed-vault research remains parallel and is not the flagship blocker.

`execution_authorized=false`
