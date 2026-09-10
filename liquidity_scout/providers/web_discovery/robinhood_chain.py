"""Official Robinhood Chain source boundary for CMIS Web Discovery.

This provider is discovery-only. Official Robinhood Chain documentation and
block-explorer observations may identify candidate contracts, transfers,
bridges, oracle references, holders, pools, liquidity, or volume, but entering
this boundary does not promote any observation to a verified CMIS fact.

In particular, Robinhood Chain availability does not prove Robinhood Chain ->
X1 bridging, tokenized-equity deployment on X1, or shareholder rights.
"""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


ROBINHOOD_CHAIN_SOURCE = WebDiscoverySource(
    source_id="robinhood_chain",
    source_name="Robinhood Chain",
    source_role="official_robinhood_chain_discovery",
    base_urls=(
        "https://docs.robinhood.com/chain/",
        "https://robinhoodchain.blockscout.com/",
    ),
    allowed_hosts=(
        "docs.robinhood.com",
        "robinhoodchain.blockscout.com",
    ),
)


class RobinhoodChainWebDiscoveryProvider(CMISWebDiscoveryProvider):
    source = ROBINHOOD_CHAIN_SOURCE


__all__ = [
    "ROBINHOOD_CHAIN_SOURCE",
    "RobinhoodChainWebDiscoveryProvider",
]
