"""X1Report source boundary for CMIS Web Discovery."""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


X1REPORT_SOURCE = WebDiscoverySource(
    source_id="x1report",
    source_name="X1Report",
    source_role="third_party_reporting_discovery",
    base_urls=("https://x1report.com/",),
    allowed_hosts=(
        "x1report.com",
        "www.x1report.com",
    ),
)


class X1ReportDiscoveryProvider(CMISWebDiscoveryProvider):
    source = X1REPORT_SOURCE


__all__ = ["X1REPORT_SOURCE", "X1ReportDiscoveryProvider"]
