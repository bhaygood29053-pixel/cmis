# X1.Ninja Liquidity Unit Semantics v1

Issue: #515  
Contract: `x1_ninja_liquidity_unit_semantics/v1`

## Why this contract exists

Live #513 proved that X1.Ninja's pool `liquidity` can be reproduced essentially
exactly from the provider's own XNT reference basis:

```text
provider_nominal_liquidity
  = asset_reserve * ((xnt_reserve / asset_reserve) * provider_xntPriceUsd)
  + xnt_reserve * provider_xntPriceUsd
```

For exact wrapped-XNT pools this simplifies to:

```text
2 * xnt_reserve * provider_xntPriceUsd
```

However, accepted #470 evidence also showed that the numerical
`provider_xntPriceUsd` value tracks the exact XNT/USDC.X reserve ratio.
Therefore the provider's USD-labelled liquidity field and an independently
valued external USD amount are not automatically the same number whenever
USDC/USD differs from 1.

## Separate outputs

### Provider nominal liquidity basis

The contract may verify:

```text
provider_numerical_unit = USDC.X_nominal_quote_basis
provider_nominal_liquidity_semantics_verified = true
```

only when:

- exact pool identity is verified;
- wrapped-XNT position is verified;
- provider XNT reference value matches exact XNT/USDC.X reference evidence;
- provider liquidity matches the two-sided reserve valuation under that same
  provider basis.

This does **not** claim independently verified external USD.

### Independent current USD liquidity

The contract separately derives:

```text
independent_xnt_usd
  = reference_usdcx_per_xnt * independently_qualified_usdc_usd

independent_liquidity_usd
  = asset_reserve * independent_asset_usd
  + xnt_reserve * independent_xnt_usd
```

This amount may legitimately differ from X1.Ninja's provider liquidity field.

## Live #513 example

For OGX/XNT:

```text
provider liquidity       = 725.7858651168269
provider xntPriceUsd     = 0.3517496668516707
XNT reserve              = 1031.679534501

derived provider nominal = 725.7858651168269159802816414
```

At the same live run, independently qualified USDC/USD was:

```text
0.99988399
```

which produced:

```text
independent liquidity USD = 725.7016666986146690586144688...
```

The difference exceeded the existing 10-bps liquidity comparison tolerance.
That is a unit-basis difference, not a pool-reserve or cache failure.

## Boundaries

This contract does not establish:

- provider fact time;
- source independence;
- global XDEX completeness;
- stable-name-implies-$1 semantics;
- execution authority.

`execution_authorized=false`.
