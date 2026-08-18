# CMIS Pre-Trade Trade-Size Policy

Status: accepted implementation candidate for Issue #99

This policy is **analysis only**. It does not authorize transaction construction,
signing, simulation, broadcasting, custody, swaps, or autonomous value movement.

## Policy identity

- Policy contract: `pre_trade_liquidity` v2.0
- Operating policy: `cmis_x1_trade_size_conservative` v1.0
- Input ratio: `verified requested USD notional / verified asset-wide USD liquidity`

The operating thresholds are deliberately conservative CMIS policy choices. They
are **not represented as universal market truth**. Every result returns the exact
policy name, version, thresholds, verified liquidity, notional, and calculated
ratio used so a caller can audit the classification.

## Default X1 classification bands

| Ratio to verified asset-wide liquidity | Classification | Analytical action |
| --- | --- | --- |
| `< 2%` | `LOW` | `PASS` unless another pre-trade/risk gate is worse |
| `>= 2% and < 5%` | `MODERATE` | `PASS` unless another gate is worse |
| `>= 5% and < 10%` | `HIGH` | `WARN` |
| `>= 10%` | `VERY_HIGH` | `BLOCK` |

The policy remains configurable through the existing deployment/caller
`params.pre_trade_policy` contract. Custom thresholds are validated for ordering
and are returned verbatim in the result. They cannot weaken missing-evidence
gates by manufacturing liquidity or execution estimates.

## Fail-closed evidence rules

A sized trade is not classified from a provider number merely because the number
exists. The upstream CMIS risk result must mark liquidity as verified. If
liquidity is missing, conflicting, or otherwise not verified, the ratio and
classification remain `null` and the default policy returns `BLOCK`.

A zero verified-liquidity result also returns `BLOCK`; CMIS never substitutes a
small denominator or fake non-zero value.

BUY and SELL use the same market-size ratio policy. This policy says how large
the requested notional is relative to verified market liquidity; it does not
claim that buy-side and sell-side route depth are identical.

## Route, price-impact, slippage, and fee boundary

Issue #99 does not permit CMIS to derive execution estimates from reserve-looking
fields alone. The current X1 reserve-semantic gate explicitly says that a
semantic manifest is only an externally backed assertion and is not CMIS
promotable by itself. Reserve field identity therefore does **not** prove an AMM
curve, fee schedule, viable route, executable quote, expected output, or
slippage model.

Until a separately verified route/quote or pool-depth execution contract is
accepted, CMIS returns these fields as `unavailable` with `null` values:

- price impact;
- slippage;
- route quality;
- fees;
- bridge dependency where route representation is not proven;
- transaction simulation.

Missing execution evidence is never reported as zero. A caller may explicitly
require one of these capabilities; if required and unavailable, pre-trade fails
closed.

## Example using the reported AGI liquidity scenario

With verified asset-wide liquidity of `$3,380`:

- `$50 / $3,380 = 1.479...%` → `LOW`;
- `$150 / $3,380 = 4.437...%` → `MODERATE`;
- `$250 / $3,380 = 7.396...%` → `HIGH` / `WARN`;
- `$500 / $3,380 = 14.792...%` → `VERY_HIGH` / `BLOCK`;
- `$2,000 / $3,380 = 59.171...%` → `VERY_HIGH` / `BLOCK`.

These classifications apply only when the `$3,380` liquidity observation is
verified under the CMIS evidence contract. If that liquidity becomes stale,
conflicting, unavailable, or unverified, the numeric classification is withheld.

## Provenance requirement

The upstream market/risk envelope remains responsible for source, venue/pool,
observation time, evidence scope, disagreements, and verification metadata.
Pre-trade adds deterministic policy evidence; it must not erase or strengthen
upstream provenance.
