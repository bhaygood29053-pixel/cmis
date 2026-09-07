"""FortiBlox App source boundary for CMIS Web Discovery.

This source is discovery-only. It may collect public GET-visible content from
app.fortiblox.com, including the provider's published x402 discovery catalogue
and llms.txt surface, but it does not promote provider claims into CMIS truth
and does not authorize execution routes.
"""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


FORTIBLOX_APP_SOURCE = WebDiscoverySource(
    source_id="fortiblox_app",
    source_name="FortiBlox App",
    source_role="third_party_x1_app_web_api_discovery",
    base_urls=(
        "https://app.fortiblox.com/",
        "https://app.fortiblox.com/api/x402/discovery",
        "https://app.fortiblox.com/llms.txt",
    ),
    allowed_hosts=("app.fortiblox.com",),
)


class FortiBloxAppWebDiscoveryProvider(CMISWebDiscoveryProvider):
    source = FORTIBLOX_APP_SOURCE


__all__ = ["FORTIBLOX_APP_SOURCE", "FortiBloxAppWebDiscoveryProvider"]
