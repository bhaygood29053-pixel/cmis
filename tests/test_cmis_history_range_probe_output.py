import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import cmis_history_range_probe


class HistoryRangeProbeOutputTests(unittest.TestCase):
    def test_main_prints_and_writes_only_sanitized_artifact(self):
        raw = {
            "service": "history_range_probe",
            "chain": "x1",
            "pools": [{"chain_signature_sample": {"first": ["SECRET_SIG"]}}],
            "summary": {
                "provider_range_contract_verified": False,
                "cmis_window_completion_promoted": False,
            },
        }
        safe = {
            "service": "x1_history_range_evidence",
            "chain": "x1",
            "raw_signatures_retained": False,
            "provider_range_contract_verified": False,
            "cmis_promotable": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "artifact.json"
            argv = [
                "cmis_history_range_probe.py",
                "XENCAT",
                "--window",
                "1h",
                "--max-pools",
                "1",
                "--output",
                str(output),
            ]
            stdout = io.StringIO()
            with (
                patch.object(sys, "argv", argv),
                patch.object(
                    cmis_history_range_probe,
                    "build_history_range_probe_result",
                    return_value=raw,
                ) as build,
                patch.object(
                    cmis_history_range_probe,
                    "sanitize_history_range_probe_result",
                    return_value=safe,
                ) as sanitize,
                redirect_stdout(stdout),
            ):
                cmis_history_range_probe.main()

            build.assert_called_once_with(
                "XENCAT",
                window="1h",
                max_pools=1,
                max_signatures_per_pool=5000,
                page_size=1000,
            )
            sanitize.assert_called_once_with(raw)
            printed = json.loads(stdout.getvalue())
            stored = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(printed, safe)
            self.assertEqual(stored, safe)
            self.assertNotIn("SECRET_SIG", stdout.getvalue())
            self.assertNotIn("SECRET_SIG", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
