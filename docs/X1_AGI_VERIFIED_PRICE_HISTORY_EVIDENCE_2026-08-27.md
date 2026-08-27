# AGI Verified XDEX Price-History Evidence — 2026-08-27

## Result

CMIS 1.12's read-only verified provider-price backfill was exercised live for:

- asset: **AGI**
- exact X1 mint: `7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER`
- requested lookback: **300 days**
- live evidence workflow: **AGI Verified History Backfill Evidence**
- workflow run: **33039035719**
- evidence artifact id: **9633137005**
- artifact digest: `sha256:8c0d33cf44e13655b7e55b9f9ee43c8fee8de49eb2d618475831e96848ead7bd`

The live proof passed.

## Verified market-price history

The production CMIS importer verified **20 usable AGI/USD price observations**.

Exact verified bounds:

```text
first verified observation = 2026-08-07T18:35:00Z
last verified observation  = 2026-08-27T04:18:00Z
first verified price       = 0.00009017313664448115 USD
last verified price        = 0.000049228605259308354 USD
```

The accepted path was:

```text
method = direct_configured_usd_stable_quote

AGI
  -> USDC.X
```

Provider pair:

```text
7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER
/
B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq
```

The direct AGI/USDC.X pool observed in the live catalog was:

```text
9cEHHQJu5JVRKnD8e65XL91fCFXqaHQfRM54UDJd6Hmo
```

The imported observations were cross-checked against the corresponding X1.Ninja OHLCV close observations under the CMIS 1.12 provider-history evidence gates. Same-timestamp conflicts remained fail-closed; the run reported zero conflicting provider timestamps.

## Independent path replay

The proof separately exercised three candidate configurations using isolated temporary SQLite stores:

| Candidate | Result | Usable observations | First verified | Last verified |
| --- | --- | ---: | --- | --- |
| Production catalog | verified partial | 20 | 2026-08-07 18:35 UTC | 2026-08-27 04:18 UTC |
| Direct AGI/USDC.X | verified partial | 20 | 2026-08-07 18:35 UTC | 2026-08-27 04:18 UTC |
| AGI/XNT × XNT/USDC.X | unavailable | 0 | — | — |

The catalog contained both legs required for the candidate two-leg route:

```text
AGI/XNT
pool = 4sn8oCQWPikDxBkyRdd1S6bJ24oYjGF16aR7ZqCSXy4v
observed liquidity ~= 2016.6553163878564 USD

XNT/USDC.X
pool = CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR
observed liquidity ~= 14895.17021 USD
```

Pool existence did **not** satisfy the complete two-leg historical evidence contract. The forced two-leg import therefore returned:

```text
status = unavailable
reason = verified_provider_usd_price_path_unavailable
provider_history_imported = false
usable observations = 0
```

CMIS consequently did not manufacture USD history from the two pools.

## Coverage conclusion

For the provider paths currently accepted by CMIS and tested inside the 300-day requested window:

```text
earliest currently defensible verified AGI price observation
= 2026-08-07T18:35:00Z
```

This is **not** proof that August 7 is AGI's first trade, launch time, or complete market-history start.

The live proof preserved:

```text
full_asset_lifetime_verified = false
continuous_coverage_verified = false
provider_range_complete_verified = false
source_independence_verified = false
historical_stable_quote_peg_verified = false
```

Therefore the correct interpretation is:

> Verified partial AGI price history exists from August 7, 2026 through the latest verified observation in this run. Earlier AGI market history remains unknown/unproven under current accepted evidence, not zero.

## Scope limitations

This proof does not verify or import:

- complete AGI asset lifetime;
- continuous historical coverage;
- provider archive/range completeness;
- provider source independence;
- historical USDC.X one-dollar peg behavior;
- historical liquidity;
- historical volume;
- historical holder totals;
- asset-wide on-chain activity.

It is a bounded, read-only provider-price history proof only.

## Safety

The workflow used read-only XDEX/X1.Ninja requests and a temporary SQLite database. It did not modify a production history database and did not prepare, construct, sign, broadcast, custody, execute, or move value.
