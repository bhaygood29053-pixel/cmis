import os
import re
import unittest
from urllib.parse import urljoin, urlparse

import requests


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
APP_URL = "https://app.xdex.xyz/swap"
MAX_SCRIPTS = 80
MAX_BYTES_PER_SCRIPT = 8_000_000


@unittest.skipUnless(RUN_LIVE, "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1")
class XDEXFrontendQuoteBundleLiveTests(unittest.TestCase):
    def test_public_frontend_bundle_localizes_quote_fee_rule(self):
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "LiquidityScout-XDEX-readonly-evidence/1.0",
                "Accept": "text/html,application/javascript,text/javascript,*/*",
            }
        )

        response = session.get(APP_URL, timeout=30, allow_redirects=True)
        self.assertEqual(response.status_code, 200, response.url)
        html = response.text

        script_srcs = re.findall(
            r"<script[^>]+src=[\"']([^\"']+)[\"']",
            html,
            flags=re.IGNORECASE,
        )
        script_urls = []
        for src in script_srcs:
            url = urljoin(response.url, src)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"}:
                continue
            if url not in script_urls:
                script_urls.append(url)

        self.assertTrue(script_urls, "No public frontend script bundles were discovered")
        self.assertLessEqual(len(script_urls), MAX_SCRIPTS)

        needles = (
            "api.xdex.xyz",
            "/api/xendex/swap/quote",
            "xendex/swap/quote",
            "tradeFeeRate",
            "trade_fee_rate",
            "feeRate",
            "fee_rate",
            "slippage",
        )
        numeric_needles = ("3000", "0.003", "0.3")
        strong_rule_patterns = {
            "max_with_3000": re.compile(r"(?:Math\\.max|max)\\([^)]{0,180}3000|3000[^)]{0,180}(?:Math\\.max|max)\\(", re.I),
            "fee_near_3000": re.compile(r"(?:fee|trade)[A-Za-z_$0-9.]{0,80}.{0,180}3000|3000.{0,180}(?:fee|trade)", re.I | re.S),
            "quote_near_3000": re.compile(r"(?:quote|swap)[A-Za-z_$0-9./:-]{0,120}.{0,240}3000|3000.{0,240}(?:quote|swap)", re.I | re.S),
        }

        bundle_findings = []
        total_bytes = 0
        for url in script_urls:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                continue
            content = r.content[:MAX_BYTES_PER_SCRIPT]
            total_bytes += len(content)
            text = content.decode("utf-8", errors="replace")

            found_needles = [needle for needle in needles if needle in text]
            found_numbers = [needle for needle in numeric_needles if needle in text]
            rule_hits = {
                name: bool(pattern.search(text))
                for name, pattern in strong_rule_patterns.items()
            }
            if not found_needles and not any(rule_hits.values()):
                continue

            contexts = []
            focus_terms = (
                "/api/xendex/swap/quote",
                "xendex/swap/quote",
                "tradeFeeRate",
                "trade_fee_rate",
                "feeRate",
                "slippage",
                "3000",
            )
            for term in focus_terms:
                start = 0
                hits = 0
                while hits < 4:
                    idx = text.find(term, start)
                    if idx < 0:
                        break
                    left = max(0, idx - 260)
                    right = min(len(text), idx + len(term) + 260)
                    contexts.append(
                        {
                            "term": term,
                            "offset": idx,
                            "context": text[left:right].replace("\n", " ")[:620],
                        }
                    )
                    hits += 1
                    start = idx + len(term)

            bundle_findings.append(
                {
                    "url": url,
                    "bytes_scanned": len(content),
                    "needles": found_needles,
                    "numeric_needles": found_numbers,
                    "strong_rule_hits": rule_hits,
                    "contexts": contexts,
                }
            )

        print("XDEX deployed frontend bundle quote-localization evidence")
        print(
            {
                "app_url": response.url,
                "script_count": len(script_urls),
                "total_bundle_bytes_scanned": total_bytes,
                "bundles_with_relevant_markers": len(bundle_findings),
            }
        )
        for finding in bundle_findings:
            print(finding)

        quote_bundles = [
            row
            for row in bundle_findings
            if "/api/xendex/swap/quote" in row["needles"]
            or "xendex/swap/quote" in row["needles"]
            or "api.xdex.xyz" in row["needles"]
        ]
        print(
            "Interpretation boundary:",
            "A literal or expression in a deployed public bundle can localize client-side logic, "
            "but absence of a 3000-ppm rule does not prove server implementation details. "
            "This probe performs GET requests only and never calls /swap/prepare.",
        )
        print({"quote_bundle_count": len(quote_bundles)})

        # This is an evidence probe, not an assumption that the endpoint must be emitted literally.
        # Modern bundlers can split strings, proxy through relative routes, or move logic server-side.
        self.assertGreater(total_bytes, 0)


if __name__ == "__main__":
    unittest.main()
