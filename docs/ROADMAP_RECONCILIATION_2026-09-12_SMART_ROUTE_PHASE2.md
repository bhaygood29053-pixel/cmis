# CMIS Roadmap Reconciliation — X1 Smart Route Intelligence Phase 2

Date: 2026-09-12 (America/New_York)

## Status

**Phase 2 ACCEPTED pending merge of PR #685.**

`xdex_multi_hop_route_snapshot/v1` converts the accepted Phase-1 provider parser plus independent X1-RPC verifier into one reusable, provider-agnostic route snapshot suitable for X1 Scout projection.

## Acceptance evidence

Implementation head: `37e18e86c92d85f5706f76215e90857c5c05d5f9`

- XDEX Multi-Hop Live Probe #27: PASS
- deterministic multi-hop suite: **34 tests PASS**
- full Liquidity Scout Tests #1970: PASS
- live snapshot: 2 XDEX hops
- live state-alignment window: 4 slots, accepted maximum 8
- aggregate hop output: VERIFIED
- provider gross-to-net 50-bps arithmetic transform: VERIFIED
- provider fee business semantics: UNVERIFIED
- price impact: EVIDENCE_REQUIRED
- minimum received / slippage: EVIDENCE_REQUIRED
- network fee: EVIDENCE_REQUIRED
- route optimality: NOT VERIFIED
- provider raw JSON exposed above provider layer: false
- cross-DEX execution observed/verified: false
- `execution_authorized=false`

## Accepted boundary

The snapshot accepts only normalized:

- `xdex_multi_hop_quote_parsed.v1`
- `xdex_multi_hop_onchain_verification.v1`

Raw provider JSON is rejected at the snapshot boundary.

The snapshot preserves exact route path, pool/config lineage, pool/config context slots, independently verified active reserves, decoded fee configuration, reconstructed per-hop output, aggregate gross output, and separately scoped provider routing-fee arithmetic.

It does not claim global route optimality, executed output, guaranteed minimum received, complete network fees, or cross-DEX execution.

## Next exact task — X1 Scout projection

Project `xdex_multi_hop_route_snapshot/v1` through X1 Scout as a read-only chain-specialist interpretation contract without weakening CMIS verification states.

Required Scout behavior:

1. accept the CMIS snapshot without parsing XDEX provider JSON;
2. preserve exact path/hop/pool/config lineage and observation window;
3. distinguish verified route facts from EVIDENCE_REQUIRED fields;
4. expose concise route-cost explanation inputs for ROBERTA;
5. preserve `route_optimality_verified=false` unless CMIS later verifies candidate-set completeness;
6. preserve cross-DEX configured/available/observed/verified states separately;
7. preserve `execution_authorized=false`.

After X1 Scout projection is accepted, proceed to ROBERTA #444 Pre-Trade adoption.
