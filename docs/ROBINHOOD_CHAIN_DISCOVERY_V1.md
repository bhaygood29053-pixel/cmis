# Robinhood Chain Discovery v1

This CMIS Web Discovery source is a **discovery-only** boundary for official
Robinhood Chain documentation and the Robinhood Chain Blockscout explorer.

It may surface candidate evidence about contracts, transfers, holders, bridges,
oracles, pools, liquidity, and volume. Discovery does not make those claims
verified CMIS facts. RPC / chain-state corroboration is required before any
fact is promoted for Scout reliance.

Current source boundary:

- `https://docs.robinhood.com/chain/`
- `https://robinhoodchain.blockscout.com/`

Robinhood Chain availability does not establish a Robinhood Chain -> X1 bridge,
Warp support, tokenized-equity deployment on X1, shareholder ownership, voting
rights, dividend rights, redemption rights, legal/economic equivalence, or
adoption.

Promotion remains locked:

- `read_only=true`
- `discovery_only=true`
- `cmis_verified=false`
- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`
