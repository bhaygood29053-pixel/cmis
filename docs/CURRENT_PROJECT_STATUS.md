# Current CMIS Project Status

Current reconciliation: **2026-09-05**.

Read in this order:

1. `../ROBERTA_CMIS_SOURCE_SYNC_BASELINE.md` — mirrored ROBERTA ↔ CMIS authority/status baseline.
2. `CMIS_PRODUCT_ROADMAP.md` — authoritative living CMIS roadmap.
3. `CHECKPOINT_2026-09-05_FOUR_REPOS.md` — exact four-repository checkpoint.
4. Earlier dated reconciliation/status files — historical snapshots only.

## Current flagship verification

**CMIS #461 follow-through — X1.Ninja liquidity fact-time / USD semantics.**

Accepted on `main` through PR #465:

- five unique verified price-only liquidity revaluation events;
- five distinct X1 pools;
- exact same-fact X1 RPC XNT/USDC.X reserve-ratio alignment;
- no intervening reference-pool transaction for the accepted reference observations;
- `liquidity_fact_time_verified=true`.

Still not promoted:

```text
current_usdcx_usd_equivalence_verified=false
x1_ninja_liquidity_usd_semantics_verified=false
liquidity_freshness_verified=false
source_independence_verified=false
cmis_promotable=false
execution_authorized=false
```

PR #466 owns the active USDC.X bridge-parity follow-up. Current reserve sufficiency is promising, but the historical retained-message liability model failed closed and must not be used as a shortcut to current in-flight accounting.

CMIS capability contract remains `1.18.0`; existing Burn, Discovery, field-scoped freshness, Concentration Warning Intelligence, bridge foundations, and other accepted services keep their previously accepted scopes.

Canonical authority remains `User / transport -> ROBERTA -> Chain Scout -> CMIS -> Chain Provider / verified source`.
