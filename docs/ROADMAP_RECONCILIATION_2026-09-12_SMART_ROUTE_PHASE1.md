# CMIS Roadmap Reconciliation — X1 Smart Route Intelligence Phase 1

Date: 2026-09-12 (America/New_York)

This reconciliation records the accepted evidence boundary for CMIS #681 Phase 1. It does not promote execution, global route optimality, cross-DEX execution, or unsupported fee semantics.

## Phase 1 — accepted

`xdex_multi_hop_route_intelligence/v1` is accepted as a read-only, evidence-first XDEX multi-hop route intelligence foundation.

Accepted evidence path:

`ROBERTA -> X1 Scout -> CMIS -> X1 Provider -> X1 RPC + XDEX public multi-hop quote API`

The provider quote is candidate-route discovery evidence. Material route facts are independently corroborated from X1 mainnet state before CMIS marks them verified.

### Exact acceptance evidence

Implementation PR: #682

Accepted head: `7b4161a7d5128406eeb54b4ac825c9ee75151455`

- Liquidity Scout Tests #1966: PASS
- XDEX Multi-Hop Live Probe #24: PASS
- deterministic multi-hop contract gate: 21 tests PASS
- live X1 XDEX inventory: 1,258 decoded 637-byte pool accounts spanning 728 token mints
- accepted live route: two XDEX hops
- independent verification slot span: 6 slots, within the accepted maximum of 8

Verified for the accepted live route:

- ordered route structure;
- exact input/output mint identity;
- hop continuity;
- exact pool identity per hop;
- XDEX program ownership / pool-state layout;
- current active reserves;
- decoded AMM config identity;
- 2,800 ppm trade-fee configuration per hop;
- hop-level constant-product output arithmetic;
- provider 50-bps gross-to-net arithmetic transform;
- current-state alignment inside the bounded slot window.

Still intentionally unverified/unpromoted:

- global route optimality or exhaustive route completeness;
- provider `fee_bps` business meaning beyond the observed arithmetic transform;
- cross-DEX execution observed or verified;
- executed/fill output;
- minimum-received guarantee;
- route-level price-impact promotion beyond separately accepted evidence;
- transaction/network fee completeness;
- provider fact time as an authoritative chain timestamp;
- any transaction preparation or execution authority.

`execution_authorized=false` remains mandatory.

## Phase 2 — next exact task

Harden independent route reconstruction into a reusable route snapshot contract suitable for X1 Scout adoption.

1. Materialize one deterministic `xdex_multi_hop_route_snapshot/v1` object from the accepted parser plus X1-RPC verifier.
2. Bind every hop to exact pool/config/vault context slots and one explicit route observation window.
3. Expose separately verified pool-fee deductions, gross route output, and provider routing-fee transform without relabeling unexplained arithmetic.
4. Add route-level price-impact composition only where every contributing hop is independently bounded.
5. Add slippage/minimum-received fields only from independently accepted quote semantics; otherwise preserve EVIDENCE_REQUIRED.
6. Add stale-state and quote/state drift regression fixtures that fail closed.
7. Keep `cross_dex_configured`, `cross_dex_route_available`, `cross_dex_execution_observed`, and `cross_dex_execution_verified` separate.
8. Preserve `route_optimality_verified=false` until candidate-set completeness is independently established.
9. Preserve `execution_authorized=false`.

After Phase 2 is accepted, project the bounded contract through X1 Scout before ROBERTA #444 adoption.
