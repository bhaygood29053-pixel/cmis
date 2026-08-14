# Market Report Migration Checkpoint

Branch: `agent/extract-market-report-snapshot`

This slice extracts deterministic asset-level market report construction from the MoltGrid listener into `liquidity_scout.services.market_report`.

Key boundaries:

- XDEX resolution remains in `liquidity_scout.market`.
- The structured report aggregates liquidity, 24h volume, and 24h transactions across distinct matched LPs.
- Primary/deepest-pool price, price change, and safety remain pool-specific.
- Missing or malformed values are not silently promoted to verified zeroes in the structured service; completeness flags preserve uncertainty.
- Conflicting holder counts are exposed as uncertainty in the structured service. The MoltGrid compatibility adapter temporarily preserves the legacy max-holder presentation behavior.
- MoltGrid transport, AI routing, conversation state, X1 RPC logic, and trading behavior are unchanged.
- Production deployment remains on `main`; this branch requires isolated local validation before merge.
