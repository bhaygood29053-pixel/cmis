# X1 Evidence Capability Boundary

Status date: **2026-08-18**

This document records the accepted CMIS decision for the remaining X1 evidence gaps. The machine-readable source of truth is `liquidity_scout/cmis/x1_evidence_capabilities.py` and the same records are exposed under `GET /v1/cmis/capabilities` → `chains.x1.evidence_capabilities`.

The rule is deliberately fail-closed:

- **verified** — usable as a verified fact only for the exact named scope;
- **bounded** — a deterministic evidence primitive exists, but broader semantics/coverage remain unproven;
- **unavailable** — current accepted provider contracts do not prove the fact, so CMIS must not promote it.

An unavailable capability may be reconsidered only after a new accepted evidence contract and tests. UI text, provider advertising, conventional field names, or numerical resemblance alone are not enough.

## Holder / concentration

| Capability | State | Boundary |
|---|---|---|
| Wallet / beneficial-owner holder total | unavailable | Provider counted-entity semantics and total coverage are not proven; token accounts are not equivalent to wallets or beneficial owners. |
| Token-account concentration | bounded | May describe the observed largest token accounts as a share of mint supply; must not be called holder/wallet concentration or a total holder count. |

## Historical / archival

| Capability | State | Boundary |
|---|---|---|
| Explicit requested-slot same-fact comparison | bounded | Deterministic comparison exists when source independence is explicitly established. |
| Archival history completeness | unavailable | Sparse samples do not prove continuous coverage, retention depth, finality equivalence, reconnect, or backfill. |
| Provider trade-range exhaustiveness | unavailable | Provider pagination/range completeness and full ordering/staleness semantics remain unproven. |

## XDEX history semantics

The accepted history evidence is deliberately scoped to the structurally verified **XENCAT/native-XNT** market. It does not make every compact XDEX history field globally verified.

| Capability | State | Boundary |
|---|---|---|
| Direct XDEX history semantics, coarse | bounded | Some field semantics are independently corroborated; `v`, range completeness, and gap behavior are not. |
| `t` timestamp / interval / ordering | verified | For the pinned XENCAT/native-XNT contract, `t` behaves as Unix seconds; returned bars form a continuous 60-second timeline in oldest→newest order for the tested window. This does not prove other pairs, intervals, or archival completeness. |
| Latest `c` native-XNT close price | verified | The latest XDEX `c` independently matched X1.Ninja `currentPriceNative` for the same verified pool. |
| Native-XNT OHLC semantics | bounded | OHLC values satisfy candle invariants and independently indexed `priceNative` trade evidence falls inside aligned `[l,h]`; not every historical bar has been reconstructed trade-by-trade. |
| `v` semantics | unavailable | `v` did not match X1.Ninja candle volume in the aligned live sample. Token/native/USD/cumulative/rolling meaning remains unproven. |
| Requested-range completeness / gap behavior | unavailable | The live response can be bounded to the requested seconds window, but full range exhaustiveness, retention, and forward-fill/no-trade behavior remain unproven. |

### History proof basis

The live evidence uses two different provider surfaces plus chain-aware trade semantics:

1. XDEX `/api/xendex/chart/history` for raw compact bars.
2. X1.Ninja indexed 1-minute OHLCV and individual trade history for the same pool.
3. Existing X1.Ninja semantic probes verify buy/sell arithmetic (`amountNative / amountToken == priceNative`) and cross-check transaction slot/time against X1 RPC when current history is available.

X1.Ninja remains an indexed XDEX market-history source, not a substitute for raw X1 chain history. Broader mint/burn/supply/authority/transfer history must continue to come from X1 RPC/history evidence or CMIS's own observation ledger.

## XDEX quote semantics

The accepted quote evidence is deliberately scoped to the pinned XENCAT/native-XNT CP-swap-compatible route and AMM configuration:

- XDEX program: `sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN`
- XENCAT mint: `DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb`
- native/wrapped-XNT market identity used by XDEX: `So11111111111111111111111111111111111111112`
- verified pool: `6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry`
- verified AMM config: `2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c`

| Capability | State | Boundary |
|---|---|---|
| Direct XDEX quote semantics, coarse | bounded | Mint identity, AMM config, AMM trade fee, and route-scoped `priceImpactPct` are proven; output decomposition, all-in fees, slippage, route quality, fill quality, and freshness/expiry are not. |
| Input/output mint identity | verified | Exact XENCAT/native-XNT mint identifiers are accepted and preserved by the read-only quote endpoint in both directions. |
| AMM config identity | verified | Provider `amm_config_address` matches the independently decoded on-chain config for the verified route. This is not route optimality. |
| AMM trade fee rate | verified | On-chain AMM config decodes `2800 / 1,000,000 = 0.28%`. This is the AMM trade fee only, not an all-in fee. |
| `priceImpactPct` | verified | Across eight tested sizes/directions, XDEX `priceImpactPct` remained within 0.002 percentage points of an independent CP-curve calculation using X1 RPC reserves after the verified trade fee. This is route-scoped price impact, not user slippage. |
| `outputAmount` full decomposition | unavailable | The provider output does not reproduce the independently calculated raw CP-curve output. Both tested mints are classic SPL Token/Tokenkeg, so Token-2022 transfer fees do not explain the difference. The remaining adjustment must stay unnamed until authoritative or independently reproducible evidence exists. |
| All-in fee decomposition | unavailable | The 0.28% AMM trade fee is verified, but no accepted evidence proves whether additional router/platform/protocol/safety adjustments exist or how they enter `outputAmount`. |
| Slippage / minimum received | unavailable | No accepted contract proves a slippage-tolerance parameter, minimum-received formula, or that `outputAmount` should be interpreted as minimum received. |
| Route quality / optimality | unavailable | Matching AMM config is not evidence that XDEX searched all pools, selected an optimal route, or used/avoided multi-hop routing. |
| Fill quality | unavailable | No accepted quote→actual-execution comparison exists. No execution is required or permitted by this evidence milestone. |

### Price-impact proof boundary

The accepted independent calculation for the pinned route is an exact-in constant-product curve after the verified AMM trade fee:

```text
trade_fee = ceil(raw_input * trade_fee_rate / 1_000_000)
amount_after_trade_fee = raw_input - trade_fee
curve_output = amount_after_trade_fee * reserve_out / (reserve_in + amount_after_trade_fee)
curve_impact_pct = amount_after_trade_fee / (reserve_in + amount_after_trade_fee) * 100
```

The live semantic gate tests eight amounts/directions and requires the provider `priceImpactPct` to remain within **0.002 percentage points** of the independently reproduced value. The test separately requires the unresolved `outputAmount` mismatch to remain visible so a future contract change cannot silently promote output semantics.

## Native XNT

| Capability | State | Boundary |
|---|---|---|
| Canonical native-XNT translation | verified | CMIS may distinguish canonical native XNT identity from wrapped market representation and use the accepted native network-supply path. |
| Native-XNT direct-XDEX quote translation | verified, scoped | XDEX accepts and preserves `So11111111111111111111111111111111111111112` for the pinned XENCAT/native-XNT quote contract. This does not make that market representation the canonical native chain identity. |

## Runtime pre-trade scope guard

The field-level XDEX proofs above are **not** a generic execution-estimate producer.

Generic `pre_trade_check` must continue to report `price_impact`, `fees`, and `slippage` as unavailable until the runtime can:

1. resolve the exact requested asset and route;
2. prove the pool/config identity for that route;
3. read/verify current reserves and fee configuration;
4. apply the accepted route-specific semantic contract; and
5. preserve provenance/freshness without guessing.

Therefore the XENCAT/native-XNT proof must not leak into an unrelated asset such as AGI.

## XDEX Oracle role

`oracle.xdex.xyz` is treated as a separate **provider surface within the XDEX source family**, not an independent source from XDEX itself. It can help localize whether a quote/output adjustment occurs in a common oracle/AMM layer or only in the swap/router surface, but X1 RPC remains the independent on-chain verifier.

Oracle spot/selected-pool/sell-quote fields may be promoted only field-by-field after their semantics are independently corroborated. They must not be used to manufacture the still-unknown `outputAmount` adjustment or slippage semantics.

## SSE / live-event evidence

| Capability | State | Boundary |
|---|---|---|
| X1.Ninja SSE access handshake | bounded | The read-only classifier may report handshake/access observations only. |
| X1.Ninja live-event evidence | unavailable | Event schema, ordering, duplicate handling, reconnect/backfill, dropped-event detection, and freshness semantics are not accepted CMIS facts. |

## Warp Bridge

| Capability | State | Boundary |
|---|---|---|
| Exact candidate URL provenance gate | bounded | Can decide whether a candidate read URL has acceptable provenance; it does not discover an endpoint or validate semantics. |
| Operational state | unavailable | No provenance-approved, contract-tested machine-readable read source is accepted. |
| Supported asset/route state | unavailable | Canonical representation modeling is not proof of current bridge route support. |
| Fee/capacity | unavailable | No accepted machine-readable fee/capacity contract. |
| Transfer lifecycle/history | unavailable | No authoritative contract-tested lifecycle source. |
| Guardian state | unavailable | UI observation is not accepted machine-readable guardian/quorum/health evidence. |

## Safety boundary

This work is read-only evidence classification. It adds no transaction construction, signing, broadcasting, custody, bridge transfer, trading, autonomous execution, or value movement.
