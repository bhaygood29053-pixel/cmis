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

The quote contract is now classified field-by-field. Some accepted proofs began with the pinned XENCAT/native-XNT route and were then corroborated against a second XNT/USDC.X market and a second AMM configuration.

Primary verified identities used in the evidence set include:

- XDEX program: `sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN`
- XENCAT mint: `DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb`
- native/wrapped-XNT market identity used by XDEX: `So11111111111111111111111111111111111111112`
- pinned XENCAT/XNT pool: `6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry`
- 2800-ppm AMM config: `2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c`
- second observed 3000-ppm AMM config: `ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x`

| Capability | State | Boundary |
|---|---|---|
| Direct XDEX quote semantics, coarse | bounded | Mint/config identity, route-scoped price impact, slippage parameter/default/transform, and tested zero-slippage quote arithmetic are independently reproduced. Business fee decomposition, route optimality, fill quality, and some minimum-output semantics remain unproven. |
| Input/output mint identity | verified | Exact tested mint identifiers are accepted and preserved by the read-only quote endpoint. |
| AMM config identity | verified | Provider `amm_config_address` can be matched to independently decoded on-chain config for verified routes. This is not route optimality. |
| AMM config trade-fee rate | verified | The pinned `2eFP...` config decodes 2800 ppm / 0.28%; the second `ECVm...` config decodes 3000 ppm / 0.30%. A config field is not automatically the complete quote-output deduction. |
| `priceImpactPct` | verified, scoped | Across the accepted pinned-route tests, XDEX `priceImpactPct` closely reproduces independent CP reserve movement using the decoded config trade fee. It remains unchanged when the accepted `slippage` parameter changes. Price impact and slippage are separate. |
| `slippage` parameter | verified | GET `/api/xendex/swap/quote` accepts `slippage` in percent units. `0.01` = 1 bp, `0.1` = 10 bps, `0.5` = 50 bps, and `1.0` = 100 bps in the tested live contract. |
| Default slippage | verified | Omitting `slippage` reproduces explicit `slippage=0.5`; current tested default is 0.5%. |
| `outputAmount` slippage transform | verified, scoped | For tested exact-in quotes, raw output follows `floor(output_raw(slippage=0) * (1 - slippage_percent / 100))` to raw-token precision. |
| Effective zero-slippage curve deduction | verified, scoped | Tested direct CP-swap routes use a 3000-ppm / 0.30% effective curve deduction before slippage across the currently observed 2800- and 3000-ppm config set. This is an arithmetic observation, not a fee/business label. |
| `outputAmount` full decomposition | bounded | The curve + slippage arithmetic is reproducible for tested routes, but the reason a 2800-ppm configured route is quoted using 3000-ppm effective curve deduction remains unlabelled. The user-facing Minimum Received label and on-chain minimum-output binding are also not fully proven. |
| All-in fee decomposition | unavailable | Do not call the 2800→3000 quote-math difference a router/platform/protocol/fund/affiliate/hidden 0.02% fee without authoritative or independently reproducible semantic evidence. |
| Slippage / minimum received | bounded | Slippage parameter units, default 0.5%, and output transform are verified. Exact binding of `outputAmount` to the user-facing Minimum Received label and eventual on-chain `minimum_amount_out` remains unproven. |
| Route quality / optimality | unavailable | Matching config/pool evidence is not proof that XDEX searched all pools, selected the globally best route, or used/avoided multi-hop routing. |
| Fill quality | unavailable | No accepted quote→actual-execution comparison exists. No execution is required or permitted by this evidence milestone. |

### Slippage proof boundary

The current read-only quote contract behaves as:

```text
zero_slippage_output_raw = provider quote with slippage=0
output_raw(s) = floor(zero_slippage_output_raw * (1 - s / 100))
```

where `s` is the `slippage` request value in percent.

Controlled tests cover explicit `slippage` values `0`, `0.01`, `0.1`, `0.5`, and `1.0`. Omitted slippage is equivalent to `0.5` for the tested current contract. Alternate names `slippage_bps`, `slippageBps`, `slippage_tolerance`, and `slippageTolerance` did not alter the quote and are not accepted semantics.

`priceImpactPct` stayed constant across the controlled slippage set. CMIS must not conflate price impact with user slippage.

### Effective curve-deduction proof boundary

For the pinned 2800-ppm config, `slippage=0` did **not** reproduce the CP output using 2800 ppm. It reproduced the same curve using 3000 ppm exactly across six bidirectional test cases.

The same behavior was independently corroborated for the selected XNT/USDC.X pool under the 2800-ppm config.

For a different live AMM config whose decoded trade fee is already 3000 ppm, `slippage=0` reproduced the config's own 3000-ppm CP output and did **not** show an additional 200-ppm deduction.

A current read-only X1 RPC inventory observed approximately 1,204 637-byte XDEX pool-state candidates and only two distinct AMM configs in that layout family: one at 2800 ppm and one at 3000 ppm. Because no >3000-ppm config is currently available in this inventory, the evidence cannot distinguish between:

```text
quote service always uses 3000 ppm for this tested route family
```

and:

```text
quote service applies a minimum/floor of 3000 ppm while preserving higher configs
```

That distinction must remain unresolved until a higher-rate config or authoritative implementation evidence exists.

### Oracle localization

For the tested XENCAT/native-XNT route, XDEX Oracle `/api/v1/token/sell-quote` `amount_out_quote` matched the independently reconstructed **no-fee** CP curve output exactly at raw-token precision across multiple sizes.

This makes the Oracle sell quote a useful curve/reference evidence surface for the tested route. It must not be presented as fee-complete, slippage-adjusted, or executable.

### Price-impact proof boundary

The accepted independent price-impact calculation for the pinned route remains an exact-in constant-product reserve movement after the decoded AMM config trade fee:

```text
trade_fee = ceil(raw_input * trade_fee_rate / 1_000_000)
amount_after_trade_fee = raw_input - trade_fee
curve_output = amount_after_trade_fee * reserve_out / (reserve_in + amount_after_trade_fee)
curve_impact_pct = amount_after_trade_fee / (reserve_in + amount_after_trade_fee) * 100
```

The live semantic gate tests multiple amounts/directions and requires the provider `priceImpactPct` to remain within the accepted tolerance of the independently reproduced value. The later slippage tests show that `priceImpactPct` is invariant to the user-slippage parameter in the tested contract.

## Native XNT

| Capability | State | Boundary |
|---|---|---|
| Canonical native-XNT translation | verified | CMIS may distinguish canonical native XNT identity from wrapped market representation and use the accepted native network-supply path. |
| Native-XNT direct-XDEX quote translation | verified, scoped | XDEX accepts and preserves `So11111111111111111111111111111111111111112` for the tested direct quote contract. This does not make that market representation the canonical native chain identity. |

## Runtime pre-trade scope guard

The field-level XDEX proofs above are **not** a generic execution-estimate producer.

Generic `pre_trade_check` must continue to report `price_impact`, `fees`, and `slippage` as unavailable until the runtime can:

1. resolve the exact requested asset and route;
2. prove the pool/config identity for that route;
3. read/verify current reserves and fee configuration;
4. establish that the accepted direct-quote semantic contract applies to that route;
5. apply the route/config-scoped calculations; and
6. preserve provenance/freshness without guessing.

Therefore the XENCAT/native-XNT and XNT/USDC.X proofs must not leak into an unrelated asset such as AGI.

## XDEX Oracle role

`oracle.xdex.xyz` is treated as a separate **provider surface within the XDEX source family**, not an independent source from XDEX itself. X1 RPC remains the independent on-chain verifier.

For the tested XENCAT/native-XNT route, Oracle `amount_out_quote` now has a verified narrow role as a no-fee CP-curve reference because it reproduced the independent no-fee reserve calculation at raw precision. This does not make it an execution quote or a source of all-in fee/slippage/fill semantics.

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
